from django.conf import settings
from django.db import models

from empleados_app.models import Empleado


class ExpedienteEmpleado(models.Model):
    """Información del flujo de RR. HH. que no existe en la ficha oficial."""

    ESTADO_PENDIENTE = "pendiente"
    ESTADO_EN_REVISION = "revision"
    ESTADO_COMPLETO = "completo"
    ESTADOS = [
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_EN_REVISION, "En revisión"),
        (ESTADO_COMPLETO, "Completo"),
    ]

    empleado = models.OneToOneField(
        Empleado,
        on_delete=models.CASCADE,
        related_name="expediente_rrhh",
    )
    estado = models.CharField(max_length=12, choices=ESTADOS, default=ESTADO_PENDIENTE)
    observaciones = models.TextField(blank=True)
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expedientes_rrhh_actualizados",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "expediente de empleado"
        verbose_name_plural = "expedientes de empleados"
        permissions = [
            ("view_gestion_empleados", "Puede ver Gestión de Empleados"),
            ("manage_preselection", "Puede gestionar preselección"),
            ("review_employee_files", "Puede revisar expedientes"),
            ("edit_employee_record", "Puede editar la ficha del empleado"),
            ("manage_employee_contracts", "Puede gestionar contratos"),
            ("rescind_employee_contracts", "Puede rescindir contratos"),
            ("view_contract_information", "Puede consultar información contractual"),
        ]

    def __str__(self):
        return f"Expediente de {self.empleado.nombres} {self.empleado.apellidos}"
