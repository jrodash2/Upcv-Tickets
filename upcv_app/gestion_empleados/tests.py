from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from empleados_app.models import Contrato, Empleado

from .forms import Contrato029Form, InformacionContrato029Form, PostulanteForm
from .models import (
    CasoActuacion,
    CasoJudicial,
    ControlMensualContrato,
    EstadoCasoJudicial,
    EstadoControlMensual,
    EstadoPostulacion,
    ExpedienteEmpleado,
    Postulante,
    TipoDocumento,
)
from .selectors import obtener_dashboard, obtener_indicadores_dashboard
from .services import (
    convertir_postulante_en_empleado,
    guardar_contrato_029,
    guardar_postulante,
)


class IndicadoresDashboardTests(TestCase):
    def setUp(self):
        self.hoy = timezone.localdate()
        self.empleado = Empleado.objects.create(
            dpi="1234567890101",
            nombres="Ana",
            apellidos="Prueba",
            tipoc="Empleado",
        )

    def crear_contrato(self, inicio, vencimiento, estado=Contrato.ESTADO_ACTIVO):
        contrato = Contrato.objects.create(
            empleado=self.empleado,
            fecha_inicio=inicio,
            fecha_vencimiento=vencimiento,
        )
        if estado == Contrato.ESTADO_RESCINDIDO:
            contrato.rescindir(self.hoy, "Prueba", "", None)
        return contrato

    def test_calcula_indicadores_con_datos_reales(self):
        self.crear_contrato(self.hoy - timedelta(days=1), self.hoy + timedelta(days=10))
        otro = Empleado.objects.create(
            dpi="1234567890102", nombres="Luis", apellidos="Prueba", tipoc="Empleado"
        )
        Contrato.objects.create(
            empleado=otro,
            fecha_inicio=self.hoy - timedelta(days=30),
            fecha_vencimiento=self.hoy - timedelta(days=1),
        )
        ExpedienteEmpleado.objects.create(empleado=self.empleado)

        indicadores = obtener_indicadores_dashboard()

        self.assertEqual(indicadores["total_empleados"], 2)
        self.assertEqual(indicadores["empleados_con_contrato_activo"], 1)
        self.assertEqual(indicadores["contratos_vencidos"], 1)
        self.assertEqual(indicadores["contratos_proximos_vencer"], 1)
        self.assertEqual(indicadores["expedientes_en_proceso"], 1)


class AccesoGestionTests(TestCase):
    def test_usuario_anonimo_es_redirigido(self):
        response = self.client.get(reverse("gestion_empleados:dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_superusuario_puede_ver_dashboard(self):
        user = get_user_model().objects.create_superuser(
            "rrhh", "rrhh@example.com", "clave-segura"
        )
        self.client.force_login(user)
        response = self.client.get(reverse("gestion_empleados:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gestión de Empleados")


class FlujoRRHHTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            "admin_rrhh", "a@upcv.gob.gt", "clave"
        )
        self.estado, _ = EstadoPostulacion.objects.get_or_create(
            nombre="Pendiente", defaults={"orden": 1}
        )

    def test_postulante_reutiliza_empleado_historico_por_dpi(self):
        empleado = Empleado.objects.create(
            dpi="1111111111111", nombres="Histórico", apellidos="UPCV", tipoc="029"
        )
        form = PostulanteForm(
            {
                "cui": empleado.dpi,
                "nombres": "Nombre distinto",
                "apellidos": "Otro",
                "programa_area": "Área",
                "fecha_solicitud": timezone.localdate(),
                "estado_tdr": self.estado.pk,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        postulante = guardar_postulante(form, self.user)
        self.assertEqual(postulante.empleado, empleado)
        self.assertEqual(postulante.nombres, empleado.nombres)

    def test_conversion_no_duplica_empleado(self):
        postulante = Postulante.objects.create(
            cui="2222222222222",
            nombres="Nuevo",
            apellidos="Postulante",
            programa_area="Área",
            estado_tdr=self.estado,
            responsable=self.user,
        )
        primero = convertir_postulante_en_empleado(postulante, self.user)
        segundo = convertir_postulante_en_empleado(postulante, self.user)
        self.assertEqual(primero.pk, segundo.pk)
        self.assertEqual(Empleado.objects.filter(dpi=postulante.cui).count(), 1)

    def test_conversion_bloquea_postulante_sin_join_nullable(self):
        postulante = Postulante.objects.create(
            cui="2222222222223",
            nombres="Concurrente",
            apellidos="Seguro",
            programa_area="Área",
            estado_tdr=self.estado,
            responsable=self.user,
        )

        empleado = convertir_postulante_en_empleado(postulante, self.user)

        self.assertEqual(empleado.dpi, postulante.cui)
        postulante.refresh_from_db()
        self.assertEqual(postulante.empleado_id, empleado.pk)

    def test_vista_informa_si_postulante_ya_estaba_convertido(self):
        empleado = Empleado.objects.create(
            dpi="2222222222224", nombres="Ya", apellidos="Convertido", tipoc="029"
        )
        postulante = Postulante.objects.create(
            cui=empleado.dpi,
            nombres=empleado.nombres,
            apellidos=empleado.apellidos,
            programa_area="Área",
            estado_tdr=self.estado,
            responsable=self.user,
            empleado=empleado,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("gestion_empleados:postulante_convertir", args=(postulante.pk,)),
            follow=True,
        )

        self.assertRedirects(
            response, reverse("gestion_empleados:empleado_ficha", args=(empleado.pk,))
        )
        self.assertContains(response, "ya estaba vinculado")
        self.assertEqual(Empleado.objects.filter(dpi=empleado.dpi).count(), 1)

    def test_no_permite_segundo_contrato_activo(self):
        empleado = Empleado.objects.create(
            dpi="3333333333333", nombres="Activo", apellidos="UPCV", tipoc="029"
        )
        hoy = timezone.localdate()
        Contrato.objects.create(
            empleado=empleado,
            fecha_inicio=hoy,
            fecha_vencimiento=hoy + timedelta(days=30),
        )
        contrato_form = Contrato029Form(
            {
                "fecha_inicio": hoy,
                "fecha_vencimiento": hoy + timedelta(days=60),
                "tipo_contrato": "Servicios Técnicos",
                "renglon": "029",
            }
        )
        info_form = InformacionContrato029Form({})
        self.assertTrue(contrato_form.is_valid(), contrato_form.errors)
        self.assertTrue(info_form.is_valid(), info_form.errors)
        with self.assertRaisesMessage(Exception, "contrato activo"):
            guardar_contrato_029(empleado, contrato_form, info_form, self.user)

    def test_usuario_sin_permiso_no_puede_crear_contrato(self):
        usuario = get_user_model().objects.create_user("consulta", password="clave")
        empleado = Empleado.objects.create(
            dpi="4444444444444", nombres="Sin", apellidos="Permiso", tipoc="029"
        )
        hoy = timezone.localdate()
        contrato_form = Contrato029Form(
            {
                "fecha_inicio": hoy,
                "fecha_vencimiento": hoy + timedelta(days=30),
                "tipo_contrato": "Servicios Técnicos",
                "renglon": "029",
            }
        )
        info_form = InformacionContrato029Form({})
        self.assertTrue(contrato_form.is_valid(), contrato_form.errors)
        self.assertTrue(info_form.is_valid(), info_form.errors)
        with self.assertRaises(PermissionDenied):
            guardar_contrato_029(empleado, contrato_form, info_form, usuario)


class PersonalCasosDashboardTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            "juridico", "j@upcv.gob.gt", "clave"
        )
        self.hoy = timezone.localdate()
        self.empleado = Empleado.objects.create(
            dpi="5555555555555", nombres="Flujo", apellidos="Completo", tipoc="029"
        )
        self.contrato = Contrato.objects.create(
            empleado=self.empleado,
            fecha_inicio=self.hoy,
            fecha_vencimiento=self.hoy + timedelta(days=20),
        )
        self.estado_control, _ = EstadoControlMensual.objects.get_or_create(
            codigo="pendiente", defaults={"nombre": "Pendiente"}
        )

    def test_no_duplica_control_mensual(self):
        ControlMensualContrato.objects.create(
            contrato=self.contrato,
            mes=self.hoy.month,
            anio=self.hoy.year,
            estado=self.estado_control,
            responsable=self.user,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            ControlMensualContrato.objects.create(
                contrato=self.contrato,
                mes=self.hoy.month,
                anio=self.hoy.year,
                estado=self.estado_control,
                responsable=self.user,
            )

    def test_control_incompleto_no_puede_marcarse_completo(self):
        TipoDocumento.objects.get_or_create(
            codigo="obligatorio-prueba",
            defaults={
                "nombre": "Obligatorio",
                "obligatorio": True,
                "aplica_control_mensual": True,
            },
        )
        completo, _ = EstadoControlMensual.objects.get_or_create(
            codigo="completo", defaults={"nombre": "Completo", "es_completo": True}
        )
        control = ControlMensualContrato.objects.create(
            contrato=self.contrato,
            mes=self.hoy.month,
            anio=self.hoy.year,
            estado=self.estado_control,
            responsable=self.user,
        )
        control.estado = completo
        with self.assertRaises(ValidationError):
            control.full_clean()

    def test_caso_con_actuacion_no_se_elimina(self):
        estado, _ = EstadoCasoJudicial.objects.get_or_create(
            codigo="abierto", defaults={"nombre": "Abierto"}
        )
        caso = CasoJudicial.objects.create(
            numero_caso="CASO-001",
            tipo="Laboral",
            empleado=self.empleado,
            organo_competente="Juzgado",
            fecha_inicio=self.hoy,
            estado=estado,
            responsable=self.user,
            creado_por=self.user,
            actualizado_por=self.user,
        )
        CasoActuacion.objects.create(
            caso=caso,
            tipo_actuacion="Notificación",
            detalle="Recibida",
            usuario=self.user,
        )
        with self.assertRaises(ValidationError):
            caso.delete()
        self.assertTrue(CasoJudicial.objects.filter(pk=caso.pk).exists())

    def test_usuario_sin_permiso_no_ve_casos(self):
        usuario = get_user_model().objects.create_user(
            "rrhh_sin_juridico", password="clave"
        )
        self.client.force_login(usuario)
        self.assertEqual(
            self.client.get(reverse("gestion_empleados:casos")).status_code, 403
        )

    def test_rescision_conserva_historial_y_sale_de_activos(self):
        self.contrato.rescindir(self.hoy, "Terminación", "Prueba", self.user)
        self.assertTrue(
            Contrato.objects.filter(
                pk=self.contrato.pk, estado=Contrato.ESTADO_RESCINDIDO
            ).exists()
        )
        self.assertEqual(
            obtener_dashboard()["indicadores"]["empleados_con_contrato_activo"], 0
        )

    def test_dashboard_usa_datos_reales(self):
        ControlMensualContrato.objects.create(
            contrato=self.contrato,
            mes=self.hoy.month,
            anio=self.hoy.year,
            estado=self.estado_control,
            responsable=self.user,
        )
        contexto = obtener_dashboard()
        self.assertEqual(contexto["indicadores"]["total_empleados"], 1)
        self.assertEqual(contexto["indicadores"]["empleados_con_contrato_activo"], 1)
        self.assertEqual(contexto["entregables_mes"]["pendientes"], 1)
