from datetime import timedelta

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from empleados_app.models import Contrato, Empleado, Puesto, Sede

from .forms import (
    Contrato029Form,
    FichaEmpleadoForm,
    InformacionContrato029Form,
    PostulanteForm,
    PruebaConfiabilidadForm,
)
from .models import (
    CasoActuacion,
    CasoJudicial,
    ControlMensualContrato,
    EstadoCasoJudicial,
    EstadoControlMensual,
    EstadoPostulacion,
    ExpedienteEmpleado,
    Postulante,
    ProcesoContratacion,
    TipoDocumento,
)
from . import models as gestion_models
from .selectors import (
    empleados_con_estado_contractual,
    obtener_dashboard,
    obtener_indicadores_dashboard,
)
from .services import (
    guardar_contrato_029,
    guardar_postulante,
    registrar_prueba_confiabilidad,
    vincular_empleado_para_contratacion,
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

    def test_ficha_tecnica_y_checkbox_activo_no_aparecen_en_nuevos_formularios(self):
        self.assertNotIn("ficha_tecnica", PostulanteForm().fields)
        self.assertNotIn("activo", FichaEmpleadoForm().fields)

    def test_vinculacion_empleado_solo_desde_elegible_y_sin_duplicar(self):
        postulante = Postulante.objects.create(
            cui="2222222222222",
            nombres="Nuevo",
            apellidos="Postulante",
            programa_area="Área",
            estado_tdr=self.estado,
            responsable=self.user,
        )
        proceso = ProcesoContratacion.objects.create(
            tipo_proceso=ProcesoContratacion.INGRESO,
            estado=ProcesoContratacion.PRESELECCION,
            postulante=postulante, responsable=self.user,
            creado_por=self.user, actualizado_por=self.user,
        )
        with self.assertRaises(ValidationError):
            vincular_empleado_para_contratacion(proceso, self.user)
        proceso.estado = ProcesoContratacion.ELEGIBLE
        proceso.save()
        primero = vincular_empleado_para_contratacion(proceso, self.user)
        segundo = vincular_empleado_para_contratacion(proceso, self.user)
        self.assertEqual(primero.pk, segundo.pk)
        self.assertEqual(Empleado.objects.filter(dpi=postulante.cui).count(), 1)

    def test_url_antigua_de_conversion_no_existe(self):
        postulante = Postulante.objects.create(
            cui="2222222222224", nombres="Sin", apellidos="Conversión",
            programa_area="Área",
            estado_tdr=self.estado,
            responsable=self.user,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            f"/gestion-empleados/preseleccion/{postulante.pk}/convertir/"
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Empleado.objects.filter(dpi=postulante.cui).exists())

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

    def test_formulario_filtra_puestos_por_sede(self):
        central = Sede.objects.create(nombre="Central")
        regional = Sede.objects.create(nombre="Regional")
        puesto_central = Puesto.objects.create(nombre="Analista", sede=central)
        Puesto.objects.create(nombre="Técnico", sede=regional)

        form = Contrato029Form(data={"sede": central.pk})

        self.assertQuerySetEqual(
            form.fields["puesto"].queryset, [puesto_central], ordered=True
        )

    def test_formulario_rechaza_puesto_de_otra_sede(self):
        central = Sede.objects.create(nombre="Central segura")
        regional = Sede.objects.create(nombre="Regional segura")
        puesto_regional = Puesto.objects.create(
            nombre="Técnico regional", sede=regional
        )
        hoy = timezone.localdate()

        form = Contrato029Form(
            data={
                "fecha_inicio": hoy,
                "fecha_vencimiento": hoy + timedelta(days=30),
                "tipo_contrato": "Servicios Técnicos",
                "renglon": "029",
                "sede": central.pk,
                "puesto": puesto_regional.pk,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("puesto", form.errors)

    def test_endpoint_antiguo_devuelve_solo_puestos_de_sede(self):
        central = Sede.objects.create(nombre="Central AJAX")
        regional = Sede.objects.create(nombre="Regional AJAX")
        esperado = Puesto.objects.create(nombre="Analista AJAX", sede=central)
        Puesto.objects.create(nombre="Excluido AJAX", sede=regional)

        response = self.client.get(
            reverse("empleados:ajax_obtener_puestos"), {"sede_id": central.pk}
        )

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content, [{"id": esperado.pk, "nombre": esperado.nombre}]
        )

    def test_crear_sede_antigua_respeta_next_local(self):
        self.client.force_login(self.user)
        destino = reverse("gestion_empleados:contratacion", args=(self.user.pk,))

        response = self.client.post(
            reverse("empleados:crear_sede"),
            {"nombre": "Sede desde contratación", "direccion": "UPCV", "next": destino},
        )

        self.assertRedirects(response, destino, fetch_redirect_response=False)
        self.assertTrue(Sede.objects.filter(nombre="Sede desde contratación").exists())

    def test_crear_puesto_antiguo_respeta_sede_y_next_local(self):
        self.client.force_login(self.user)
        sede = Sede.objects.create(nombre="Sede para puesto")
        destino = reverse("gestion_empleados:preseleccion")

        response = self.client.post(
            reverse("empleados:crear_puesto"),
            {
                "nombre": "Puesto desde contratación",
                "descripcion": "Prueba",
                "sede": sede.pk,
                "next": destino,
            },
        )

        self.assertRedirects(response, destino, fetch_redirect_response=False)
        self.assertTrue(
            Puesto.objects.filter(
                nombre="Puesto desde contratación", sede=sede
            ).exists()
        )

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


class EstadoContractualListadoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            "listado_rrhh", "listado@upcv.gob.gt", "clave"
        )
        self.client.force_login(self.user)
        self.hoy = timezone.localdate()
        self.con_activo = Empleado.objects.create(
            dpi="6666666666661", nombres="Contrato", apellidos="Activo", tipoc="029"
        )
        self.sin_contrato = Empleado.objects.create(
            dpi="6666666666662", nombres="Sin", apellidos="Contrato", tipoc="029"
        )
        self.vencido = Empleado.objects.create(
            dpi="6666666666663", nombres="Contrato", apellidos="Vencido", tipoc="029"
        )
        self.rescindido = Empleado.objects.create(
            dpi="6666666666664", nombres="Contrato", apellidos="Rescindido", tipoc="029"
        )
        Contrato.objects.create(
            empleado=self.con_activo,
            fecha_inicio=self.hoy - timedelta(days=1),
            fecha_vencimiento=self.hoy + timedelta(days=30),
        )
        Contrato.objects.create(
            empleado=self.vencido,
            fecha_inicio=self.hoy - timedelta(days=60),
            fecha_vencimiento=self.hoy - timedelta(days=1),
        )
        contrato_rescindido = Contrato.objects.create(
            empleado=self.rescindido,
            fecha_inicio=self.hoy - timedelta(days=10),
            fecha_vencimiento=self.hoy + timedelta(days=30),
        )
        contrato_rescindido.rescindir(self.hoy, "Terminación", "Prueba", self.user)

    def test_anotacion_contractual_distingue_activo_vencido_rescindido_y_sin_contrato(
        self,
    ):
        estados = dict(
            empleados_con_estado_contractual().values_list(
                "dpi", "tiene_contrato_activo_db"
            )
        )
        self.assertTrue(estados[self.con_activo.dpi])
        self.assertFalse(estados[self.sin_contrato.dpi])
        self.assertFalse(estados[self.vencido.dpi])
        self.assertFalse(estados[self.rescindido.dpi])

    def test_filtros_backend_activo_sin_activo_y_todos(self):
        url = reverse("gestion_empleados:empleados")
        activos = self.client.get(url, {"contrato": "activo"})
        sin_activo = self.client.get(url, {"contrato": "sin_activo"})
        todos = self.client.get(url)

        self.assertQuerySetEqual(activos.context["empleados"], [self.con_activo])
        self.assertNotIn(self.con_activo, list(sin_activo.context["empleados"]))
        self.assertCountEqual(
            list(todos.context["empleados"]),
            [self.con_activo, self.sin_contrato, self.vencido, self.rescindido],
        )

class ProcesoContratacionFlujoTests(TestCase):
    def setUp(self):
        from .models import CatalogoRequisito
        self.user = get_user_model().objects.create_superuser("procesos", "p@upcv.test", "clave")
        self.hoy = timezone.localdate()
        CatalogoRequisito.objects.update(activo=False)
        for numero in range(1, 15):
            CatalogoRequisito.objects.update_or_create(
                codigo=str(numero),
                defaults={
                    "descripcion": f"Requisito {numero}",
                    "fase": "PRE_AVAL" if numero <= 9 else "POST_AVAL",
                    "obligatorio": True, "activo": True, "orden": numero,
                },
            )

    def crear_ingreso(self, dpi="9000000000001"):
        form = PostulanteForm({"cui": dpi, "nombres": "Persona", "apellidos": "Nueva", "programa_area": "UPCV", "fecha_solicitud": self.hoy})
        self.assertTrue(form.is_valid(), form.errors)
        return guardar_postulante(form, self.user)

    def test_guardar_postulante_nuevo_crea_un_ingreso_pendiente(self):
        postulante = self.crear_ingreso("9000000000022")

        proceso = postulante.procesos_contratacion.get()
        self.assertEqual(proceso.tipo_proceso, ProcesoContratacion.INGRESO)
        self.assertEqual(proceso.estado, ProcesoContratacion.PRESELECCION)
        self.assertEqual(
            proceso.resultado_confiabilidad,
            ProcesoContratacion.PRUEBA_PENDIENTE,
        )

    def test_guardar_postulante_existente_no_crea_proceso_implicitamente(self):
        postulante = Postulante.objects.create(
            cui="9000000000023", nombres="Identidad", apellidos="Existente",
            programa_area="Área inicial", responsable=self.user,
        )
        form = PostulanteForm(
            {
                "cui": postulante.cui,
                "nombres": postulante.nombres,
                "apellidos": postulante.apellidos,
                "programa_area": "Área actualizada",
                "fecha_solicitud": self.hoy,
            },
            instance=postulante,
        )
        self.assertTrue(form.is_valid(), form.errors)

        actualizado = guardar_postulante(form, self.user)

        self.assertEqual(actualizado.programa_area, "Área actualizada")
        self.assertFalse(actualizado.procesos_contratacion.exists())

    def test_confiabilidad_pertenece_al_proceso_y_no_se_duplica_en_postulante(self):
        campos_postulante = {campo.name for campo in Postulante._meta.get_fields()}
        campos_proceso = {
            campo.name for campo in ProcesoContratacion._meta.get_fields()
        }

        self.assertNotIn("resultado_confiabilidad", campos_postulante)
        self.assertNotIn("fecha_evaluacion_confiabilidad", campos_postulante)
        self.assertNotIn("evaluado_por", campos_postulante)
        self.assertNotIn("observacion_confiabilidad", campos_postulante)
        self.assertFalse(
            {
                "legado_resultado_confiabilidad",
                "legado_fecha_evaluacion_confiabilidad",
                "legado_evaluado_por",
                "legado_observacion_confiabilidad",
            }.intersection(campos_postulante)
        )
        self.assertTrue(
            {
                "resultado_confiabilidad",
                "fecha_evaluacion_confiabilidad",
                "evaluado_por",
                "observacion_confiabilidad",
            }.issubset(campos_proceso)
        )
        self.assertEqual(
            dict(ProcesoContratacion.RESULTADOS_PRUEBA),
            {
                "PENDIENTE": "Prueba de Confiabilidad pendiente",
                "APROBADA": "Prueba de Confiabilidad aprobada",
                "NO_APROBADA": "Prueba de Confiabilidad no aprobada",
            },
        )
        self.assertEqual(
            gestion_models.RESULTADOS_PRUEBA,
            gestion_models.RESULTADOS_CONFIABILIDAD,
        )
        self.assertEqual(gestion_models.PRUEBA_PENDIENTE, "PENDIENTE")

    def test_ingreso_aprobado_reclutamiento_expediente_y_elegible(self):
        from .models import ProcesoContratacion
        from .services import registrar_prueba_confiabilidad, pasar_a_reclutamiento, iniciar_evaluacion, revisar_requisito, aprobar_pre_aval, aprobar_post_aval, marcar_elegible
        postulante = self.crear_ingreso()
        proceso = registrar_prueba_confiabilidad(postulante.procesos_contratacion.get(), ProcesoContratacion.PRUEBA_APROBADA, "Aprobada", self.user)
        pasar_a_reclutamiento(proceso, self.user)
        evaluacion = iniciar_evaluacion(proceso)
        for detalle in evaluacion.detalles.filter(requisito__fase="PRE_AVAL"): revisar_requisito(detalle, True, "", self.user)
        aprobar_pre_aval(evaluacion, self.user)
        for detalle in evaluacion.detalles.filter(requisito__fase="POST_AVAL"): revisar_requisito(detalle, True, "", self.user)
        aprobar_post_aval(evaluacion, self.user)
        marcar_elegible(proceso, self.user)
        proceso.refresh_from_db()
        self.assertEqual(proceso.estado, ProcesoContratacion.ELEGIBLE)

    def test_etapas_aval_bloquean_edicion_y_elegibilidad_prematura(self):
        from .models import CatalogoRequisito
        from .services import (
            aprobar_post_aval, aprobar_pre_aval, iniciar_evaluacion,
            marcar_elegible, pasar_a_reclutamiento, revisar_requisito,
        )

        postulante = self.crear_ingreso("9000000000024")
        proceso = registrar_prueba_confiabilidad(
            postulante.procesos_contratacion.get(),
            ProcesoContratacion.PRUEBA_APROBADA, "Aprobada", self.user,
        )
        pasar_a_reclutamiento(proceso, self.user)
        evaluacion = iniciar_evaluacion(proceso)
        post = evaluacion.detalles.filter(
            requisito__fase=CatalogoRequisito.POST_AVAL
        ).first()

        with self.assertRaisesMessage(ValidationError, "Post-aval se habilitará"):
            revisar_requisito(post, True, "", self.user)
        with self.assertRaisesMessage(ValidationError, "antes de aprobar Post-aval"):
            aprobar_post_aval(evaluacion, self.user)
        with self.assertRaisesMessage(ValidationError, "deben estar aprobados"):
            marcar_elegible(proceso, self.user)
        self.client.force_login(self.user)
        respuesta = self.client.post(
            reverse("gestion_empleados:expediente_elegible", args=(proceso.pk,))
        )
        proceso.refresh_from_db()
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(proceso.estado, ProcesoContratacion.RECLUTAMIENTO)

        pagina_bloqueada = self.client.get(
            reverse("gestion_empleados:expediente", args=(proceso.pk,))
        )
        self.assertContains(pagina_bloqueada, "Post-aval bloqueado")
        self.assertNotContains(pagina_bloqueada, post.requisito.descripcion)

        for detalle in evaluacion.detalles.filter(
            requisito__fase=CatalogoRequisito.PRE_AVAL
        ):
            revisar_requisito(detalle, True, "", self.user)
        aprobar_pre_aval(evaluacion, self.user)
        evaluacion.refresh_from_db()
        self.assertTrue(evaluacion.pre_aval_aprobado)
        self.assertEqual(evaluacion.pre_aval_aprobado_por, self.user)
        self.assertIsNotNone(evaluacion.pre_aval_aprobado_en)

        with self.assertRaisesMessage(ValidationError, "no admite más cambios"):
            revisar_requisito(
                evaluacion.detalles.filter(
                    requisito__fase=CatalogoRequisito.PRE_AVAL
                ).first(), False, "", self.user,
            )

    def test_post_aval_aprobado_habilita_boton_elegible(self):
        from .models import CatalogoRequisito
        from .services import (
            aprobar_post_aval, aprobar_pre_aval, iniciar_evaluacion,
            pasar_a_reclutamiento, revisar_requisito,
        )

        postulante = self.crear_ingreso("9000000000025")
        proceso = registrar_prueba_confiabilidad(
            postulante.procesos_contratacion.get(),
            ProcesoContratacion.PRUEBA_APROBADA, "Aprobada", self.user,
        )
        pasar_a_reclutamiento(proceso, self.user)
        evaluacion = iniciar_evaluacion(proceso)
        for detalle in evaluacion.detalles.filter(
            requisito__fase=CatalogoRequisito.PRE_AVAL
        ):
            revisar_requisito(detalle, True, "", self.user)
        aprobar_pre_aval(evaluacion, self.user)
        for detalle in evaluacion.detalles.filter(
            requisito__fase=CatalogoRequisito.POST_AVAL
        ):
            revisar_requisito(detalle, True, "", self.user)

        self.client.force_login(self.user)
        antes = self.client.get(reverse("gestion_empleados:expediente", args=(proceso.pk,)))
        self.assertNotContains(antes, "Marcar como elegible para contratación")
        aprobar_post_aval(evaluacion, self.user)
        despues = self.client.get(reverse("gestion_empleados:expediente", args=(proceso.pk,)))
        self.assertContains(despues, "Marcar como elegible para contratación")

    def test_no_aprobado_no_puede_avanzar(self):
        from .services import registrar_prueba_confiabilidad, pasar_a_reclutamiento
        postulante = self.crear_ingreso("9000000000002")
        proceso = registrar_prueba_confiabilidad(postulante.procesos_contratacion.get(), ProcesoContratacion.PRUEBA_NO_APROBADA, "No aprobada", self.user)
        with self.assertRaises(ValidationError): pasar_a_reclutamiento(proceso, self.user)

    def test_pendiente_no_puede_avanzar_a_reclutamiento(self):
        from .services import pasar_a_reclutamiento

        postulante = self.crear_ingreso("9000000000014")
        proceso = postulante.procesos_contratacion.get()

        with self.assertRaisesMessage(ValidationError, "debe estar aprobada"):
            pasar_a_reclutamiento(proceso, self.user)

    def test_bloqueo_de_proceso_no_incluye_outer_join_nullable(self):
        from .services import pasar_a_reclutamiento, registrar_prueba_confiabilidad

        postulante = self.crear_ingreso("9000000000015")
        proceso = registrar_prueba_confiabilidad(
            postulante.procesos_contratacion.get(), ProcesoContratacion.PRUEBA_APROBADA, "", self.user
        )

        with CaptureQueriesContext(connection) as consultas:
            pasar_a_reclutamiento(proceso, self.user)

        consulta_bloqueo = next(
            consulta["sql"]
            for consulta in consultas.captured_queries
            if consulta["sql"].lstrip().upper().startswith("SELECT")
            and "gestion_empleados_procesocontratacion" in consulta["sql"]
        )
        self.assertNotIn(" JOIN ", consulta_bloqueo.upper())

    def test_doble_transicion_a_reclutamiento_crea_un_solo_historial(self):
        from .models import HistorialProcesoContratacion
        from .services import pasar_a_reclutamiento, registrar_prueba_confiabilidad

        postulante = self.crear_ingreso("9000000000016")
        proceso = registrar_prueba_confiabilidad(
            postulante.procesos_contratacion.get(), ProcesoContratacion.PRUEBA_APROBADA, "", self.user
        )

        pasar_a_reclutamiento(proceso, self.user)
        with self.assertRaisesMessage(ValidationError, "ya se encuentra"):
            pasar_a_reclutamiento(proceso, self.user)

        self.assertEqual(
            HistorialProcesoContratacion.objects.filter(
                proceso=proceso, accion="paso_reclutamiento"
            ).count(),
            1,
        )

    def test_renovacion_y_reingreso_reutilizan_empleado_y_contratos(self):
        from .models import ProcesoContratacion
        from .services import iniciar_proceso_empleado
        activo = Empleado.objects.create(dpi="9000000000003", nombres="Activo", apellidos="Histórico", tipoc="029")
        contrato = Contrato.objects.create(empleado=activo, fecha_inicio=self.hoy, fecha_vencimiento=self.hoy + timedelta(days=30))
        renovacion = iniciar_proceso_empleado(activo, ProcesoContratacion.RENOVACION, self.user, self.hoy.year + 1)
        self.assertEqual(renovacion.empleado, activo)
        self.assertEqual(renovacion.estado, ProcesoContratacion.RECLUTAMIENTO)
        self.assertIsNone(renovacion.postulante_id)
        self.assertEqual(activo.contratos.get(), contrato)
        historico = Empleado.objects.create(dpi="9000000000004", nombres="Reingreso", apellidos="Histórico", tipoc="029")
        anterior = Contrato.objects.create(empleado=historico, fecha_inicio=self.hoy - timedelta(days=60), fecha_vencimiento=self.hoy - timedelta(days=30))
        reingreso = iniciar_proceso_empleado(historico, ProcesoContratacion.REINGRESO, self.user)
        self.assertEqual(reingreso.empleado, historico)
        self.assertEqual(Empleado.objects.filter(dpi=historico.dpi).count(), 1)
        self.assertTrue(Contrato.objects.filter(pk=anterior.pk).exists())

    def test_no_permite_proceso_duplicado(self):
        from .models import ProcesoContratacion
        from .services import iniciar_proceso_empleado
        empleado = Empleado.objects.create(dpi="9000000000005", nombres="Duplicado", apellidos="No", tipoc="029")
        Contrato.objects.create(empleado=empleado, fecha_inicio=self.hoy, fecha_vencimiento=self.hoy + timedelta(days=30))
        iniciar_proceso_empleado(empleado, ProcesoContratacion.RENOVACION, self.user, 2030)
        with self.assertRaises(ValidationError): iniciar_proceso_empleado(empleado, ProcesoContratacion.RENOVACION, self.user, 2030)

    def test_url_contratacion_rechaza_expediente_incompleto(self):
        postulante = self.crear_ingreso("9000000000006")
        proceso = postulante.procesos_contratacion.get()
        self.client.force_login(self.user)
        response = self.client.get(reverse("gestion_empleados:contratacion", args=(proceso.pk,)), follow=True)
        self.assertContains(response, "El expediente debe completarse antes de iniciar la contratación.")

    def test_reclutamiento_muestra_progreso_y_accion_al_completar_requisitos(self):
        from .models import ProcesoContratacion
        from .services import iniciar_evaluacion, iniciar_proceso_empleado, revisar_requisito

        empleado = Empleado.objects.create(
            dpi="9000000000007", nombres="Renovación", apellidos="Visible", tipoc="029"
        )
        Contrato.objects.create(
            empleado=empleado,
            fecha_inicio=self.hoy,
            fecha_vencimiento=self.hoy + timedelta(days=30),
        )
        proceso = iniciar_proceso_empleado(
            empleado, ProcesoContratacion.RENOVACION, self.user, 2031
        )
        evaluacion = iniciar_evaluacion(proceso)
        for detalle in evaluacion.detalles.all():
            revisar_requisito(detalle, True, "", self.user)
        self.client.force_login(self.user)

        response = self.client.get(reverse("gestion_empleados:reclutamiento"))

        self.assertContains(response, "14 / 14")
        self.assertContains(response, "Pasar a Elegibles")

    def test_listado_empleados_distingue_renovacion_reingreso_y_sin_historial(self):
        activo = Empleado.objects.create(
            dpi="9000000000008", nombres="Contrato", apellidos="Activo", tipoc="029"
        )
        historico = Empleado.objects.create(
            dpi="9000000000009", nombres="Contrato", apellidos="Histórico", tipoc="029"
        )
        Empleado.objects.create(
            dpi="9000000000010", nombres="Sin", apellidos="Contrato", tipoc="029"
        )
        Contrato.objects.create(
            empleado=activo, fecha_inicio=self.hoy,
            fecha_vencimiento=self.hoy + timedelta(days=30),
        )
        Contrato.objects.create(
            empleado=historico, fecha_inicio=self.hoy - timedelta(days=60),
            fecha_vencimiento=self.hoy - timedelta(days=30),
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("gestion_empleados:empleados"))

        self.assertContains(response, "Renovar contrato", count=1)
        self.assertContains(response, "Iniciar reingreso", count=1)

    def test_resultado_confiabilidad_usa_un_solo_grupo_de_radios(self):
        postulante = self.crear_ingreso("9000000000011")
        proceso = postulante.procesos_contratacion.get()

        form = PruebaConfiabilidadForm(instance=proceso)
        html = str(form["resultado_confiabilidad"])

        self.assertIsInstance(
            form.fields["resultado_confiabilidad"].widget, forms.RadioSelect
        )
        self.assertTrue(form.fields["resultado_confiabilidad"].required)
        self.assertEqual(html.count('type="radio"'), 3)
        self.assertEqual(html.count('name="resultado_confiabilidad"'), 3)
        self.assertEqual(html.count("checked"), 1)
        self.assertIn('value="PENDIENTE"', html)
        self.assertIn('value="APROBADA"', html)
        self.assertIn('value="NO_APROBADA"', html)

    def test_formulario_persiste_aprobada_y_la_muestra_seleccionada_al_editar(self):
        postulante = self.crear_ingreso("9000000000012")
        proceso = postulante.procesos_contratacion.get()
        form = PruebaConfiabilidadForm(
            {
                "resultado_confiabilidad": ProcesoContratacion.PRUEBA_APROBADA,
                "observacion_confiabilidad": "Evaluación satisfactoria",
            },
            instance=proceso,
        )
        self.assertTrue(form.is_valid(), form.errors)

        registrar_prueba_confiabilidad(
            proceso,
            form.cleaned_data["resultado_confiabilidad"],
            form.cleaned_data["observacion_confiabilidad"],
            self.user,
        )
        proceso.refresh_from_db()
        formulario_edicion = PruebaConfiabilidadForm(instance=proceso)

        self.assertEqual(proceso.resultado_confiabilidad, ProcesoContratacion.PRUEBA_APROBADA)
        self.assertEqual(proceso.evaluado_por, self.user)
        self.assertIsNotNone(proceso.fecha_evaluacion_confiabilidad)
        self.assertEqual(
            str(formulario_edicion["resultado_confiabilidad"]).count("checked"), 1
        )
        self.assertRegex(
            str(formulario_edicion["resultado_confiabilidad"]),
            r'value="APROBADA"[^>]*checked',
        )

    def test_formulario_acepta_no_aprobada_y_rechaza_ausente_o_invalida(self):
        postulante = self.crear_ingreso("9000000000013")
        proceso = postulante.procesos_contratacion.get()
        no_aprobada = PruebaConfiabilidadForm(
            {"resultado_confiabilidad": ProcesoContratacion.PRUEBA_NO_APROBADA},
            instance=proceso,
        )
        ausente = PruebaConfiabilidadForm({}, instance=proceso)
        invalida = PruebaConfiabilidadForm(
            {"resultado_confiabilidad": "OTRA"}, instance=proceso
        )

        self.assertTrue(no_aprobada.is_valid(), no_aprobada.errors)
        self.assertFalse(ausente.is_valid())
        self.assertFalse(invalida.is_valid())
        proceso.refresh_from_db()
        self.assertEqual(proceso.resultado_confiabilidad, ProcesoContratacion.PRUEBA_PENDIENTE)

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("gestion_empleados:postulante_editar", args=(postulante.pk,)),
            {"resultado_confiabilidad": "VALOR_INVALIDO"},
        )
        proceso.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertIn("resultado_confiabilidad", response.context["form"].errors)
        self.assertEqual(proceso.resultado_confiabilidad, ProcesoContratacion.PRUEBA_PENDIENTE)

    def test_dpi_existente_muestra_persona_sin_duplicarla(self):
        postulante = self.crear_ingreso("9000000000017")
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("gestion_empleados:postulante_nuevo"),
            {
                "cui": postulante.cui,
                "nombres": "Nombre duplicado",
                "apellidos": "No crear",
                "programa_area": "UPCV",
                "fecha_solicitud": self.hoy,
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertContains(
            response, "Ya existe una persona registrada con este DPI.", status_code=409
        )
        self.assertContains(response, "Ver postulante", status_code=409)
        self.assertEqual(Postulante.objects.filter(cui=postulante.cui).count(), 1)

    def test_no_aprobado_puede_iniciar_nuevo_proceso_sin_perder_historial(self):
        from .services import iniciar_nueva_postulacion

        postulante = self.crear_ingreso("9000000000018")
        anterior = postulante.procesos_contratacion.get()
        registrar_prueba_confiabilidad(
            anterior, ProcesoContratacion.PRUEBA_NO_APROBADA, "2024", self.user
        )

        nuevo = iniciar_nueva_postulacion(postulante, self.user)
        anterior.refresh_from_db()

        self.assertNotEqual(nuevo.pk, anterior.pk)
        self.assertEqual(anterior.estado, ProcesoContratacion.NO_APROBADO)
        self.assertEqual(
            anterior.resultado_confiabilidad,
            ProcesoContratacion.PRUEBA_NO_APROBADA,
        )
        self.assertEqual(nuevo.estado, ProcesoContratacion.PRESELECCION)
        self.assertEqual(
            nuevo.resultado_confiabilidad, ProcesoContratacion.PRUEBA_PENDIENTE
        )
        self.assertEqual(postulante.procesos_contratacion.count(), 2)

    def test_proceso_activo_impide_nueva_postulacion(self):
        from .services import iniciar_nueva_postulacion

        postulante = self.crear_ingreso("9000000000019")
        with self.assertRaisesMessage(ValidationError, "ya tiene un proceso activo"):
            iniciar_nueva_postulacion(postulante, self.user)
        self.assertEqual(postulante.procesos_contratacion.count(), 1)

    def test_empleado_historico_nueva_postulacion_es_reingreso(self):
        from .services import iniciar_nueva_postulacion

        empleado = Empleado.objects.create(
            dpi="9000000000020", nombres="Persona", apellidos="Histórica", tipoc="029"
        )
        contrato = Contrato.objects.create(
            empleado=empleado,
            fecha_inicio=self.hoy - timedelta(days=60),
            fecha_vencimiento=self.hoy - timedelta(days=30),
        )
        postulante = Postulante.objects.create(
            empleado=empleado, cui=empleado.dpi, nombres=empleado.nombres,
            apellidos=empleado.apellidos, programa_area="UPCV", responsable=self.user,
        )

        proceso = iniciar_nueva_postulacion(postulante, self.user)

        self.assertEqual(proceso.tipo_proceso, ProcesoContratacion.REINGRESO)
        self.assertEqual(proceso.empleado, empleado)
        self.assertTrue(Contrato.objects.filter(pk=contrato.pk).exists())

    def test_empleado_activo_debe_usar_renovacion(self):
        from .services import iniciar_nueva_postulacion

        empleado = Empleado.objects.create(
            dpi="9000000000021", nombres="Persona", apellidos="Activa", tipoc="029"
        )
        Contrato.objects.create(
            empleado=empleado, fecha_inicio=self.hoy,
            fecha_vencimiento=self.hoy + timedelta(days=30),
        )
        postulante = Postulante.objects.create(
            empleado=empleado, cui=empleado.dpi, nombres=empleado.nombres,
            apellidos=empleado.apellidos, programa_area="UPCV", responsable=self.user,
        )

        with self.assertRaisesMessage(ValidationError, "debe iniciar una renovación"):
            iniciar_nueva_postulacion(postulante, self.user)
        self.assertFalse(postulante.procesos_contratacion.exists())

    def test_navegacion_superior_y_lateral_comparten_ocho_opciones(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("gestion_empleados:dashboard"))
        etiquetas = (
            "Dashboard", "Preselección", "Reclutamiento y Selección",
            "Elegibles para Contratación", "Empleados", "Contratación 029",
            "Gestión de Personal", "Casos Judiciales",
        )
        self.assertEqual(len(response.context["menu_gestion_empleados"]), 8)
        superior = render_to_string(
            "gestion_empleados/partials/menu_modulo.html",
            {"menu_modo": "superior"}, request=response.wsgi_request,
        )
        lateral = render_to_string(
            "gestion_empleados/partials/menu_modulo.html",
            {"menu_modo": "lateral"}, request=response.wsgi_request,
        )
        for etiqueta in etiquetas:
            self.assertEqual(superior.count(etiqueta), 1)
            self.assertEqual(lateral.count(etiqueta), 1)
