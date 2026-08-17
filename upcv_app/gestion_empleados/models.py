from datetime import date

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models

from empleados_app.models import Contrato, Empleado


# Catálogo único de la Prueba de Confiabilidad. Se define a nivel de módulo para
# que siempre exista antes de construir los campos de los modelos y para evitar
# referencias parciales entre Postulante y ProcesoContratacion.
CONFIABILIDAD_PENDIENTE = "PENDIENTE"
CONFIABILIDAD_APROBADA = "APROBADA"
CONFIABILIDAD_NO_APROBADA = "NO_APROBADA"
RESULTADOS_CONFIABILIDAD = (
    (CONFIABILIDAD_PENDIENTE, "Prueba de Confiabilidad pendiente"),
    (CONFIABILIDAD_APROBADA, "Prueba de Confiabilidad aprobada"),
    (CONFIABILIDAD_NO_APROBADA, "Prueba de Confiabilidad no aprobada"),
)

# Alias de compatibilidad para instalaciones que aún cargan el estado previo a
# las migraciones 0006/0007 o para ramas con una resolución parcial del refactor.
# Se definen antes de Postulante para que una referencia histórica nunca cause
# NameError durante django.setup(). El modelo vigente no almacena estos campos.
PRUEBA_PENDIENTE = CONFIABILIDAD_PENDIENTE
PRUEBA_APROBADA = CONFIABILIDAD_APROBADA
PRUEBA_NO_APROBADA = CONFIABILIDAD_NO_APROBADA
RESULTADOS_PRUEBA = RESULTADOS_CONFIABILIDAD


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
    # Copia histórica de compatibilidad. El flujo nuevo lee y escribe únicamente
    # la evaluación perteneciente a cada ProcesoContratacion.
    legado_resultado_confiabilidad = models.CharField(
        max_length=15, default=CONFIABILIDAD_PENDIENTE, editable=False
    )
    legado_fecha_evaluacion_confiabilidad = models.DateTimeField(
        null=True, blank=True, editable=False
    )
    legado_evaluado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        editable=False, related_name="pruebas_confiabilidad_legadas",
    )
    legado_observacion_confiabilidad = models.TextField(blank=True, editable=False)
    empleado = models.ForeignKey(
        Empleado,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="postulaciones",
    )
    cui = models.CharField("DPI / CUI", max_length=15, unique=True)
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    programa_area = models.CharField("programa / área propuesta", max_length=180)
    fecha_solicitud = models.DateField(default=date.today)
    estado_tdr = models.ForeignKey(
        EstadoPostulacion, on_delete=models.PROTECT, related_name="postulantes",
        null=True, blank=True,
    )
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="postulantes_responsable",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resultado_confiabilidad = models.CharField(
        max_length=15, choices=RESULTADOS_PRUEBA, default=PRUEBA_PENDIENTE
    )
    fecha_evaluacion_confiabilidad = models.DateTimeField(null=True, blank=True)
    evaluado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="pruebas_confiabilidad_registradas",
    )
    observacion_confiabilidad = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)
        permissions = [("continue_postulante", "Puede continuar proceso de postulante")]

    def clean(self):
        if self.empleado_id and self.cui != self.empleado.dpi:
            raise ValidationError(
                {"cui": "El CUI debe coincidir con el DPI del empleado vinculado."}
            )

    def __str__(self):
        return f"{self.nombres} {self.apellidos}"


class ProcesoContratacion(models.Model):
    INGRESO, RENOVACION, REINGRESO = "INGRESO", "RENOVACION", "REINGRESO"
    TIPOS = ((INGRESO, "Ingreso"), (RENOVACION, "Renovación"), (REINGRESO, "Reingreso"))
    PRESELECCION = "PRESELECCION"
    PRUEBA_CONFIABILIDAD = "PRUEBA_CONFIABILIDAD"
    RECLUTAMIENTO = "RECLUTAMIENTO"
    EXPEDIENTE_INCOMPLETO = "EXPEDIENTE_INCOMPLETO"
    ELEGIBLE = "ELEGIBLE"
    CONTRATACION = "CONTRATACION"
    CONTRATADO = "CONTRATADO"
    NO_APROBADO = "NO_APROBADO"
    CANCELADO = "CANCELADO"
    ESTADOS = tuple((estado, estado.replace("_", " ").title()) for estado in (
        PRESELECCION, PRUEBA_CONFIABILIDAD, RECLUTAMIENTO,
        EXPEDIENTE_INCOMPLETO, ELEGIBLE, CONTRATACION, CONTRATADO,
        NO_APROBADO, CANCELADO,
    ))
    ESTADOS_ABIERTOS = (
        PRESELECCION, PRUEBA_CONFIABILIDAD, RECLUTAMIENTO,
        EXPEDIENTE_INCOMPLETO, ELEGIBLE, CONTRATACION,
    )
    PRUEBA_PENDIENTE = CONFIABILIDAD_PENDIENTE
    PRUEBA_APROBADA = CONFIABILIDAD_APROBADA
    PRUEBA_NO_APROBADA = CONFIABILIDAD_NO_APROBADA
    RESULTADOS_PRUEBA = RESULTADOS_CONFIABILIDAD

    tipo_proceso = models.CharField(max_length=12, choices=TIPOS)
    estado = models.CharField(max_length=24, choices=ESTADOS)
    resultado_confiabilidad = models.CharField(
        max_length=15,
        choices=RESULTADOS_CONFIABILIDAD,
        default=CONFIABILIDAD_PENDIENTE,
    )
    fecha_evaluacion_confiabilidad = models.DateTimeField(null=True, blank=True)
    evaluado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="procesos_confiabilidad_evaluados",
    )
    observacion_confiabilidad = models.TextField(blank=True)
    empleado = models.ForeignKey(
        Empleado, on_delete=models.PROTECT, null=True, blank=True,
        related_name="procesos_contratacion",
    )
    postulante = models.ForeignKey(
        Postulante, on_delete=models.PROTECT, null=True, blank=True,
        related_name="procesos_contratacion",
    )
    contrato_resultante = models.OneToOneField(
        Contrato, on_delete=models.PROTECT, null=True, blank=True,
        related_name="proceso_contratacion",
    )
    periodo = models.PositiveSmallIntegerField(default=date.today().year)
    fecha_inicio = models.DateField(default=date.today)
    fecha_finalizacion = models.DateTimeField(null=True, blank=True)
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="procesos_contratacion_responsable",
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="procesos_contratacion_creados",
    )
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="procesos_contratacion_actualizados",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-fecha_inicio", "-created_at")
        permissions = [("manage_hiring_process", "Puede gestionar procesos de contratación")]
        constraints = [
            models.UniqueConstraint(
                fields=("empleado", "tipo_proceso", "periodo"),
                condition=models.Q(estado__in=(
                    "PRESELECCION", "PRUEBA_CONFIABILIDAD", "RECLUTAMIENTO",
                    "EXPEDIENTE_INCOMPLETO", "ELEGIBLE", "CONTRATACION",
                )),
                name="proceso_abierto_empleado_tipo_periodo_unico",
            )
        ]

    @property
    def persona(self):
        return self.empleado or self.postulante

    def __str__(self):
        return f"{self.get_tipo_proceso_display()} {self.periodo} - {self.persona}"


class HistorialProcesoContratacion(models.Model):
    proceso = models.ForeignKey(
        ProcesoContratacion, on_delete=models.PROTECT, related_name="historial"
    )
    accion = models.CharField(max_length=80)
    estado_anterior = models.CharField(max_length=24, blank=True)
    estado_nuevo = models.CharField(max_length=24)
    detalle = models.TextField(blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-fecha",)


class HistorialEstadoPostulante(models.Model):
    postulante = models.ForeignKey(
        Postulante, on_delete=models.CASCADE, related_name="historial_estados"
    )
    estado_anterior = models.ForeignKey(
        EstadoPostulacion,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="historial_origen",
    )
    estado_nuevo = models.ForeignKey(
        EstadoPostulacion, on_delete=models.PROTECT, related_name="historial_destino"
    )
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
    postulante = models.ForeignKey(
        Postulante, on_delete=models.PROTECT, related_name="evaluaciones"
    )
    proceso = models.OneToOneField(
        ProcesoContratacion, on_delete=models.PROTECT, null=True, blank=True,
        related_name="evaluacion",
    )
    completo = models.BooleanField(default=False)
    completado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="evaluaciones_completadas",
    )
    fecha_completado = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def requisitos_obligatorios_pendientes(self):
        return self.detalles.filter(requisito__obligatorio=True, cumple=False).count()

    def clean(self):
        if self.completo and self.pk and self.requisitos_obligatorios_pendientes():
            raise ValidationError(
                "No puede completar el expediente con requisitos obligatorios pendientes."
            )


class DetalleEvaluacionRequisito(models.Model):
    evaluacion = models.ForeignKey(
        EvaluacionExpediente, on_delete=models.CASCADE, related_name="detalles"
    )
    requisito = models.ForeignKey(CatalogoRequisito, on_delete=models.PROTECT)
    cumple = models.BooleanField(default=False)
    observacion = models.TextField(blank=True)
    fecha_revision = models.DateTimeField(null=True, blank=True)
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("evaluacion", "requisito"), name="evaluacion_requisito_unico"
            )
        ]


class HistorialRevisionRequisito(models.Model):
    detalle = models.ForeignKey(
        DetalleEvaluacionRequisito, on_delete=models.CASCADE, related_name="historial"
    )
    cumple = models.BooleanField()
    observacion = models.TextField(blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fecha = models.DateTimeField(auto_now_add=True)


class PerfilRRHHEmpleado(models.Model):
    empleado = models.OneToOneField(
        Empleado, on_delete=models.CASCADE, related_name="perfil_rrhh"
    )
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
    contrato = models.OneToOneField(
        Contrato, on_delete=models.CASCADE, related_name="informacion_029"
    )
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
    honorarios_mensuales = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    primer_pago = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    honorarios_totales = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    monto_total_contrato = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    partida_presupuestaria = models.CharField(max_length=100, blank=True)
    partida_repro = models.CharField(max_length=100, blank=True)
    actividad = models.CharField(max_length=180, blank=True)
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="contratos_029_actualizados",
    )
    updated_at = models.DateTimeField(auto_now=True)


class ExpedienteEmpleado(models.Model):
    """Estado general complementario creado en la primera entrega."""

    ESTADO_PENDIENTE, ESTADO_EN_REVISION, ESTADO_COMPLETO = (
        "pendiente",
        "revision",
        "completo",
    )
    ESTADOS = (
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_EN_REVISION, "En revisión"),
        (ESTADO_COMPLETO, "Completo"),
    )
    empleado = models.OneToOneField(
        Empleado, on_delete=models.CASCADE, related_name="expediente_rrhh"
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
            ("view_personnel_management", "Puede ver gestión de personal"),
            ("manage_monthly_deliverables", "Puede gestionar entregables mensuales"),
            ("validate_monthly_deliverables", "Puede validar entregables mensuales"),
            ("ver_casos", "Puede ver casos judiciales"),
            ("crear_casos", "Puede crear casos judiciales"),
            ("editar_casos", "Puede editar casos judiciales"),
            ("cerrar_casos", "Puede cerrar o archivar casos judiciales"),
        ]


class EstadoControlMensual(models.Model):
    nombre = models.CharField(max_length=60, unique=True)
    codigo = models.SlugField(max_length=30, unique=True)
    orden = models.PositiveSmallIntegerField(default=0)
    es_completo = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ("orden", "nombre")

    def __str__(self):
        return self.nombre


class ControlMensualContrato(models.Model):
    contrato = models.ForeignKey(
        Contrato, on_delete=models.PROTECT, related_name="controles_mensuales"
    )
    mes = models.PositiveSmallIntegerField()
    anio = models.PositiveSmallIntegerField()
    fecha_recepcion = models.DateField(null=True, blank=True)
    observaciones = models.TextField(blank=True)
    estado = models.ForeignKey(
        EstadoControlMensual, on_delete=models.PROTECT, related_name="controles"
    )
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="controles_mensuales_responsable",
    )
    fecha_revision = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    documentos = GenericRelation(
        "DocumentoGestion", related_query_name="control_mensual"
    )

    class Meta:
        ordering = ("-anio", "-mes")
        constraints = [
            models.UniqueConstraint(
                fields=("contrato", "mes", "anio"), name="control_mensual_periodo_unico"
            ),
            models.CheckConstraint(
                condition=models.Q(mes__gte=1, mes__lte=12), name="control_mes_valido"
            ),
        ]

    @property
    def empleado(self):
        return self.contrato.empleado

    def documentos_obligatorios_pendientes(self):
        requeridos = TipoDocumento.objects.filter(
            aplica_control_mensual=True, obligatorio=True, activo=True
        )
        cargados = self.documentos.filter(
            estado=DocumentoGestion.ESTADO_VALIDADO
        ).values_list("tipo_id", flat=True)
        return requeridos.exclude(pk__in=cargados)

    def clean(self):
        if self.estado_id and self.estado.es_completo:
            if not self.pk or self.documentos_obligatorios_pendientes().exists():
                raise ValidationError(
                    "No puede completar o validar el control si falta documentación obligatoria validada."
                )


class TipoDocumento(models.Model):
    codigo = models.SlugField(max_length=50, unique=True)
    nombre = models.CharField(max_length=120)
    obligatorio = models.BooleanField(default=False)
    aplica_control_mensual = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class DocumentoGestion(models.Model):
    ESTADO_RECIBIDO = "recibido"
    ESTADO_REVISION = "revision"
    ESTADO_OBSERVADO = "observado"
    ESTADO_VALIDADO = "validado"
    ESTADOS = (
        (ESTADO_RECIBIDO, "Recibido"),
        (ESTADO_REVISION, "En revisión"),
        (ESTADO_OBSERVADO, "Observado"),
        (ESTADO_VALIDADO, "Validado"),
    )
    tipo = models.ForeignKey(
        TipoDocumento, on_delete=models.PROTECT, related_name="documentos"
    )
    archivo = models.FileField(upload_to="gestion_empleados/documentos/%Y/%m/")
    estado = models.CharField(max_length=12, choices=ESTADOS, default=ESTADO_RECIBIDO)
    observacion = models.TextField(blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="documentos_gestion_cargados",
    )
    fecha = models.DateTimeField(auto_now_add=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    expediente = GenericForeignKey("content_type", "object_id")

    class Meta:
        indexes = [
            models.Index(
                fields=("content_type", "object_id"), name="documento_expediente_idx"
            )
        ]


class EstadoCasoJudicial(models.Model):
    nombre = models.CharField(max_length=60, unique=True)
    codigo = models.SlugField(max_length=30, unique=True)
    cerrado = models.BooleanField(default=False)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("orden", "nombre")

    def __str__(self):
        return self.nombre


class CasoJudicial(models.Model):
    numero_caso = models.CharField(max_length=80, unique=True)
    tipo = models.CharField(max_length=100)
    empleado = models.ForeignKey(
        Empleado,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="casos_judiciales",
    )
    contrato = models.ForeignKey(
        Contrato,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="casos_judiciales",
    )
    organo_competente = models.CharField(max_length=180)
    fecha_inicio = models.DateField()
    estado = models.ForeignKey(
        EstadoCasoJudicial, on_delete=models.PROTECT, related_name="casos"
    )
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="casos_judiciales_responsable",
    )
    fecha_ultima_actuacion = models.DateField(null=True, blank=True)
    observaciones = models.TextField(blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="casos_judiciales_creados",
    )
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="casos_judiciales_actualizados",
    )
    updated_at = models.DateTimeField(auto_now=True)
    documentos = GenericRelation(DocumentoGestion, related_query_name="caso_judicial")

    class Meta:
        ordering = ("-fecha_inicio",)

    def clean(self):
        if (
            self.contrato_id
            and self.empleado_id
            and self.contrato.empleado_id != self.empleado_id
        ):
            raise ValidationError(
                {"contrato": "El contrato no pertenece al empleado seleccionado."}
            )

    def delete(self, *args, **kwargs):
        if self.actuaciones.exists():
            raise ValidationError(
                "Un caso con actuaciones no puede eliminarse; ciérrelo o archívelo."
            )
        return super().delete(*args, **kwargs)


class CasoActuacion(models.Model):
    caso = models.ForeignKey(
        CasoJudicial, on_delete=models.PROTECT, related_name="actuaciones"
    )
    fecha = models.DateField(default=date.today)
    tipo_actuacion = models.CharField(max_length=120)
    detalle = models.TextField()
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="actuaciones_judiciales",
    )
    documento = models.FileField(upload_to="gestion_empleados/casos/%Y/%m/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-fecha", "-created_at")


class RegistroAuditoria(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="auditoria_gestion_empleados",
    )
    accion = models.CharField(max_length=80)
    detalle = models.TextField(blank=True)
    fecha = models.DateTimeField(auto_now_add=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id = models.PositiveBigIntegerField()
    objeto = GenericForeignKey("content_type", "object_id")

    class Meta:
        ordering = ("-fecha",)
        indexes = [
            models.Index(
                fields=("content_type", "object_id"), name="auditoria_objeto_idx"
            )
        ]
