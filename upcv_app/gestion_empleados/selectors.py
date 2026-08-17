from datetime import timedelta

from django.db.models import Count, Exists, OuterRef, Q
from django.utils import timezone

from empleados_app.models import Contrato, Empleado

from .models import (
    CatalogoRequisito,
    ControlMensualContrato,
    ExpedienteEmpleado,
    ProcesoContratacion,
)


def contratos_vigentes(fecha=None):
    """Definición única compatible con la lógica contractual del módulo histórico."""
    fecha = fecha or timezone.localdate()
    return Contrato.objects.filter(
        activo=True,
        estado=Contrato.ESTADO_ACTIVO,
        fecha_inicio__lte=fecha,
        fecha_vencimiento__gte=fecha,
    )


def empleados_con_estado_contractual(queryset=None, fecha=None):
    queryset = queryset if queryset is not None else Empleado.objects.all()
    contrato_activo = contratos_vigentes(fecha).filter(empleado_id=OuterRef("pk"))
    # No usar `tiene_contrato_activo`: Empleado ya expone una @property con ese
    # nombre y Django no puede asignarle el valor materializado de annotate().
    return queryset.annotate(tiene_contrato_activo_db=Exists(contrato_activo))


def obtener_dashboard():
    hoy = timezone.localdate()
    vigentes = contratos_vigentes(hoy)
    no_rescindido = ~Q(estado=Contrato.ESTADO_RESCINDIDO)
    proximos = (
        Contrato.objects.filter(
            no_rescindido,
            fecha_vencimiento__gte=hoy,
            fecha_vencimiento__lte=hoy + timedelta(days=90),
        )
        .select_related("empleado", "puesto", "sede")
        .order_by("fecha_vencimiento")
    )
    controles_mes = ControlMensualContrato.objects.filter(anio=hoy.year, mes=hoy.month)
    estados_postulantes = (
        ProcesoContratacion.objects.values("resultado_confiabilidad")
        .annotate(total=Count("id"))
        .order_by("resultado_confiabilidad")
    )

    return {
        "indicadores": {
            "total_empleados": Empleado.objects.count(),
            "empleados_con_contrato_activo": vigentes.values("empleado_id")
            .distinct()
            .count(),
            "contratos_proximos_vencer": proximos.filter(
                fecha_vencimiento__lte=hoy + timedelta(days=30)
            ).count(),
            "contratos_vencidos": Contrato.objects.filter(
                no_rescindido, fecha_vencimiento__lt=hoy
            ).count(),
            "contratos_rescindidos": Contrato.objects.filter(
                estado=Contrato.ESTADO_RESCINDIDO
            ).count(),
            "expedientes_en_proceso": ExpedienteEmpleado.objects.exclude(
                estado=ExpedienteEmpleado.ESTADO_COMPLETO
            ).count(),
            "preseleccion_pendientes": ProcesoContratacion.objects.filter(
                estado__in=(ProcesoContratacion.PRESELECCION, ProcesoContratacion.PRUEBA_CONFIABILIDAD),
                resultado_confiabilidad=ProcesoContratacion.PRUEBA_PENDIENTE).count(),
            "pruebas_aprobadas": ProcesoContratacion.objects.filter(
                resultado_confiabilidad=ProcesoContratacion.PRUEBA_APROBADA,
                estado=ProcesoContratacion.PRUEBA_CONFIABILIDAD).count(),
            "en_reclutamiento": ProcesoContratacion.objects.filter(
                estado__in=(ProcesoContratacion.RECLUTAMIENTO, ProcesoContratacion.EXPEDIENTE_INCOMPLETO)).count(),
            "expedientes_incompletos": ProcesoContratacion.objects.filter(
                estado__in=(ProcesoContratacion.RECLUTAMIENTO, ProcesoContratacion.EXPEDIENTE_INCOMPLETO)
            ).filter(Q(evaluacion__completo=False) | Q(evaluacion__isnull=True)).count(),
            "elegibles": ProcesoContratacion.objects.filter(estado=ProcesoContratacion.ELEGIBLE).count(),
            "renovaciones_en_proceso": ProcesoContratacion.objects.filter(
                tipo_proceso=ProcesoContratacion.RENOVACION, estado__in=ProcesoContratacion.ESTADOS_ABIERTOS).count(),
            "reingresos_en_proceso": ProcesoContratacion.objects.filter(
                tipo_proceso=ProcesoContratacion.REINGRESO, estado__in=ProcesoContratacion.ESTADOS_ABIERTOS).count(),
        },
        "proximos_30": proximos.filter(fecha_vencimiento__lte=hoy + timedelta(days=30)),
        "proximos_60": proximos.filter(
            fecha_vencimiento__gt=hoy + timedelta(days=30),
            fecha_vencimiento__lte=hoy + timedelta(days=60),
        ),
        "proximos_90": proximos.filter(fecha_vencimiento__gt=hoy + timedelta(days=60)),
        "expedientes_pendientes": ControlMensualContrato.objects.exclude(
            estado__es_completo=True
        ).select_related("contrato__empleado", "estado")[:10],
        "postulantes_por_estado": estados_postulantes,
        "entregables_mes": {
            "completos": controles_mes.filter(estado__es_completo=True).count(),
            "pendientes": controles_mes.filter(
                estado__codigo__in=("pendiente", "recibido", "en-revision")
            ).count(),
            "observados": controles_mes.filter(
                estado__codigo="con-observaciones"
            ).count(),
        },
    }


def obtener_indicadores_dashboard(dias_proximos=30):
    """API conservada para compatibilidad con las pruebas y primera entrega."""
    return obtener_dashboard()["indicadores"]


def obtener_resumen_empleado(empleado):
    hoy = timezone.localdate()
    contrato_actual = (
        contratos_vigentes(hoy)
        .filter(empleado=empleado)
        .select_related("puesto", "sede", "informacion_029")
        .first()
    )
    proceso = empleado.procesos_contratacion.filter(evaluacion__isnull=False).select_related("evaluacion").first()
    evaluacion = proceso.evaluacion if proceso else None
    detalles = evaluacion.detalles.select_related("requisito") if evaluacion else None

    def progreso(fase):
        if detalles is None:
            return (0, 0)
        fase_qs = detalles.filter(requisito__fase=fase, requisito__activo=True)
        return (fase_qs.filter(cumple=True).count(), fase_qs.count())

    controles = ControlMensualContrato.objects.filter(
        contrato__empleado=empleado, anio=hoy.year
    )
    return {
        "contrato_actual": contrato_actual,
        "progreso_pre_aval": progreso(CatalogoRequisito.PRE_AVAL),
        "progreso_post_aval": progreso(CatalogoRequisito.POST_AVAL),
        "entregables_anio": controles.count(),
        "entregables_pendientes": controles.exclude(estado__es_completo=True).count(),
        "contratos_historicos": empleado.contratos.count(),
    }
