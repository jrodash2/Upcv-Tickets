from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from empleados_app.models import Contrato, Empleado

from .forms import Contrato029Form, InformacionContrato029Form, PostulanteForm
from .models import EstadoPostulacion, ExpedienteEmpleado, Postulante
from .selectors import obtener_indicadores_dashboard
from .services import convertir_postulante_en_empleado, guardar_contrato_029, guardar_postulante


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
        otro = Empleado.objects.create(dpi="1234567890102", nombres="Luis", apellidos="Prueba", tipoc="Empleado")
        Contrato.objects.create(empleado=otro, fecha_inicio=self.hoy - timedelta(days=30), fecha_vencimiento=self.hoy - timedelta(days=1))
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
        user = get_user_model().objects.create_superuser("rrhh", "rrhh@example.com", "clave-segura")
        self.client.force_login(user)
        response = self.client.get(reverse("gestion_empleados:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gestión de Empleados")


class FlujoRRHHTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser("admin_rrhh", "a@upcv.gob.gt", "clave")
        self.estado = EstadoPostulacion.objects.create(nombre="Pendiente", orden=1)

    def test_postulante_reutiliza_empleado_historico_por_dpi(self):
        empleado = Empleado.objects.create(dpi="1111111111111", nombres="Histórico", apellidos="UPCV", tipoc="029")
        form = PostulanteForm({"cui": empleado.dpi, "nombres": "Nombre distinto", "apellidos": "Otro", "programa_area": "Área", "fecha_solicitud": timezone.localdate(), "estado_tdr": self.estado.pk})
        self.assertTrue(form.is_valid(), form.errors)
        postulante = guardar_postulante(form, self.user)
        self.assertEqual(postulante.empleado, empleado)
        self.assertEqual(postulante.nombres, empleado.nombres)

    def test_conversion_no_duplica_empleado(self):
        postulante = Postulante.objects.create(cui="2222222222222", nombres="Nuevo", apellidos="Postulante", programa_area="Área", estado_tdr=self.estado, responsable=self.user)
        primero = convertir_postulante_en_empleado(postulante, self.user)
        segundo = convertir_postulante_en_empleado(postulante, self.user)
        self.assertEqual(primero.pk, segundo.pk)
        self.assertEqual(Empleado.objects.filter(dpi=postulante.cui).count(), 1)

    def test_no_permite_segundo_contrato_activo(self):
        empleado = Empleado.objects.create(dpi="3333333333333", nombres="Activo", apellidos="UPCV", tipoc="029")
        hoy = timezone.localdate()
        Contrato.objects.create(empleado=empleado, fecha_inicio=hoy, fecha_vencimiento=hoy + timedelta(days=30))
        contrato_form = Contrato029Form({"fecha_inicio": hoy, "fecha_vencimiento": hoy + timedelta(days=60), "tipo_contrato": "Servicios Técnicos", "renglon": "029"})
        info_form = InformacionContrato029Form({})
        self.assertTrue(contrato_form.is_valid(), contrato_form.errors)
        self.assertTrue(info_form.is_valid(), info_form.errors)
        with self.assertRaisesMessage(Exception, "contrato activo"):
            guardar_contrato_029(empleado, contrato_form, info_form, self.user)

    def test_usuario_sin_permiso_no_puede_crear_contrato(self):
        usuario = get_user_model().objects.create_user("consulta", password="clave")
        empleado = Empleado.objects.create(dpi="4444444444444", nombres="Sin", apellidos="Permiso", tipoc="029")
        hoy = timezone.localdate()
        contrato_form = Contrato029Form({"fecha_inicio": hoy, "fecha_vencimiento": hoy + timedelta(days=30), "tipo_contrato": "Servicios Técnicos", "renglon": "029"})
        info_form = InformacionContrato029Form({})
        self.assertTrue(contrato_form.is_valid(), contrato_form.errors)
        self.assertTrue(info_form.is_valid(), info_form.errors)
        with self.assertRaises(PermissionDenied):
            guardar_contrato_029(empleado, contrato_form, info_form, usuario)
