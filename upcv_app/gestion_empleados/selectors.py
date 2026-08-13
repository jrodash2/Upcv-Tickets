from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from empleados_app.models import Contrato, Empleado

from .models import ExpedienteEmpleado


def obtener_indicadores_dashboard(dias_proximos=30):
    """Calcula indicadores con las fuentes oficiales, sin alterar sus estados."""
    hoy = timezone.localdate()
    limite = hoy + timedelta(days=dias_proximos)
    no_rescindido = ~Q(estado=Contrato.ESTADO_RESCINDIDO)
    vigencia = Q(fecha_inicio__lte=hoy, fecha_vencimiento__gte=hoy)

    return {
        "total_empleados": Empleado.objects.count(),
        "empleados_con_contrato_activo": Contrato.objects.filter(
            no_rescindido, vigencia
        ).values("empleado_id").distinct().count(),
        "contratos_vencidos": Contrato.objects.filter(
            no_rescindido, fecha_vencimiento__lt=hoy
        ).count(),
        "contratos_rescindidos": Contrato.objects.filter(
            estado=Contrato.ESTADO_RESCINDIDO
        ).count(),
        "contratos_proximos_vencer": Contrato.objects.filter(
            no_rescindido,
            fecha_vencimiento__gte=hoy,
            fecha_vencimiento__lte=limite,
        ).count(),
        "expedientes_en_proceso": ExpedienteEmpleado.objects.exclude(
            estado=ExpedienteEmpleado.ESTADO_COMPLETO
        ).count(),
    }
