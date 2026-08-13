from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from empleados_app.models import Contrato, Empleado


class EstadoPostulacion(models.Model):
    nombre = models.CharField(max_length=60, unique=True)
    orden = models.PositiveSmallIntegerField(default=0)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ("orden", "nombre")
        verbose_name = "estado de postulación"

    def __str__(self):
        return self.nombre


class Postulante(models.Model):
    empleado = models.ForeignKey(Empleado, on_delete=models.PROTECT, null=True, blank=True, related_name="postulaciones")
    cui = models.CharField("DPI / CUI", max_length=15, unique=True)
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    programa_area = models.CharField("programa / área propuesta", max_length=180)
    fecha_solicitud = models.DateField(default=date.today)
    estado_tdr = models.ForeignKey(EstadoPostulacion, on_delete=models.PROTECT, related_name="postulantes")
    ficha_tecnica = models.FileField(upload_to="gestion_empleados/fichas_tecnicas/", blank=True)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="postulantes_responsable")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        permissions = [("continue_postulante", "Puede continuar proceso de postulante")]

    def clean(self):
        if self.empleado_id and self.cui != self.empleado.dpi:
            raise ValidationError({"cui": "El CUI debe coincidir con el DPI del empleado vinculado."})

    def __str__(self):
        return f"{self.nombres} {self.apellidos}"


class HistorialEstadoPostulante(models.Model):
    postulante = models.ForeignKey(Postulante, on_delete=models.CASCADE, related_name="historial_estados")
    estado_anterior = models.ForeignKey(EstadoPostulacion, on_delete=models.PROTECT, null=True, blank=True, related_name="historial_origen")
    estado_nuevo = models.ForeignKey(EstadoPostulacion, on_delete=models.PROTECT, related_name="historial_destino")
    observacion = models.TextField(blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-fecha",)


class CatalogoRequisito(models.Model):
    PRE_AVAL = "PRE_AVAL"
    POST_AVAL = "POST_AVAL"
    FASES = ((PRE_AVAL, "Pre-aval"), (POST_AVAL, "Post-aval"))
    codigo = models.CharField(max_length=10, unique=True)
    descripcion = models.TextField()
    fase = models.CharField(max_length=10, choices=FASES)
    obligatorio = models.BooleanField(default=True)
    orden = models.PositiveSmallIntegerField()
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ("fase", "orden")

    def __str__(self):
        return f"{self.codigo}. {self.descripcion}"


class EvaluacionExpediente(models.Model):
    postulante = models.OneToOneField(Postulante, on_delete=models.CASCADE, related_name="evaluacion")
    completo = models.BooleanField(default=False)
    completado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="evaluaciones_completadas")
    fecha_completado = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def requisitos_obligatorios_pendientes(self):
        return self.detalles.filter(requisito__obligatorio=True, cumple=False).count()

    def clean(self):
        if self.completo and self.pk and self.requisitos_obligatorios_pendientes():
            raise ValidationError("No puede completar el expediente con requisitos obligatorios pendientes.")


class DetalleEvaluacionRequisito(models.Model):
    evaluacion = models.ForeignKey(EvaluacionExpediente, on_delete=models.CASCADE, related_name="detalles")
    requisito = models.ForeignKey(CatalogoRequisito, on_delete=models.PROTECT)
    cumple = models.BooleanField(default=False)
    observacion = models.TextField(blank=True)
    fecha_revision = models.DateTimeField(null=True, blank=True)
    revisado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("evaluacion", "requisito"), name="evaluacion_requisito_unico")]


class HistorialRevisionRequisito(models.Model):
    detalle = models.ForeignKey(DetalleEvaluacionRequisito, on_delete=models.CASCADE, related_name="historial")
    cumple = models.BooleanField()
    observacion = models.TextField(blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fecha = models.DateTimeField(auto_now_add=True)


class PerfilRRHHEmpleado(models.Model):
    empleado = models.OneToOneField(Empleado, on_delete=models.CASCADE, related_name="perfil_rrhh")
    nit = models.CharField(max_length=20, blank=True)
    pertenencia_sociolinguistica = models.CharField(max_length=100, blank=True)
    discapacidad = models.CharField(max_length=180, blank=True)
    municipio_domicilio = models.CharField(max_length=100, blank=True)
    departamento_domicilio = models.CharField(max_length=100, blank=True)
    correo_personal = models.EmailField(blank=True)
    profesion = models.CharField(max_length=150, blank=True)
    numero_colegiado = models.CharField(max_length=40, blank=True)
    cuenta_banrural = models.CharField(max_length=40, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class InformacionContrato029(models.Model):
    contrato = models.OneToOneField(Contrato, on_delete=models.CASCADE, related_name="informacion_029")
    puesto_funcional = models.CharField(max_length=180, blank=True)
    puesto_nominal = models.CharField(max_length=180, blank=True)
    tdr = models.FileField(upload_to="gestion_empleados/tdr/", blank=True)
    codigo_guatenominas = models.CharField(max_length=50, blank=True)
    correo_institucional = models.EmailField(blank=True)
    dependencia = models.CharField(max_length=180, blank=True)
    departamento = models.CharField(max_length=180, blank=True)
    seccion = models.CharField(max_length=180, blank=True)
    programa_area = models.CharField(max_length=180, blank=True)
    departamento_servicios = models.CharField(max_length=180, blank=True)
    numero_contrato = models.CharField(max_length=50, blank=True, db_index=True)
    fecha_primera_contratacion = models.DateField(null=True, blank=True)
    resolucion_aprobacion = models.CharField(max_length=100, blank=True)
    fecha_resolucion = models.DateField(null=True, blank=True)
    numero_fianza = models.CharField(max_length=100, blank=True)
    honorarios_mensuales = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    primer_pago = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    honorarios_totales = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    monto_total_contrato = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    partida_presupuestaria = models.CharField(max_length=100, blank=True)
    partida_repro = models.CharField(max_length=100, blank=True)
    actividad = models.CharField(max_length=180, blank=True)
    actualizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="contratos_029_actualizados")
    updated_at = models.DateTimeField(auto_now=True)


class ExpedienteEmpleado(models.Model):
    """Estado general complementario creado en la primera entrega."""
    ESTADO_PENDIENTE, ESTADO_EN_REVISION, ESTADO_COMPLETO = "pendiente", "revision", "completo"
    ESTADOS = ((ESTADO_PENDIENTE, "Pendiente"), (ESTADO_EN_REVISION, "En revisión"), (ESTADO_COMPLETO, "Completo"))
    empleado = models.OneToOneField(Empleado, on_delete=models.CASCADE, related_name="expediente_rrhh")
    estado = models.CharField(max_length=12, choices=ESTADOS, default=ESTADO_PENDIENTE)
    observaciones = models.TextField(blank=True)
    actualizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="expedientes_rrhh_actualizados")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "expediente de empleado"
        verbose_name_plural = "expedientes de empleados"
        permissions = [
            ("view_gestion_empleados", "Puede ver Gestión de Empleados"), ("manage_preselection", "Puede gestionar preselección"),
            ("review_employee_files", "Puede revisar expedientes"), ("edit_employee_record", "Puede editar la ficha del empleado"),
            ("manage_employee_contracts", "Puede gestionar contratos"), ("rescind_employee_contracts", "Puede rescindir contratos"),
            ("view_contract_information", "Puede consultar información contractual"),
        ]
