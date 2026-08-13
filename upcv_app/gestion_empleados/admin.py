from django.contrib import admin

from .models import (
    CasoActuacion,
    CasoJudicial,
    CatalogoRequisito,
    ControlMensualContrato,
    DetalleEvaluacionRequisito,
    DocumentoGestion,
    EstadoCasoJudicial,
    EstadoControlMensual,
    EstadoPostulacion,
    EvaluacionExpediente,
    ExpedienteEmpleado,
    HistorialEstadoPostulante,
    HistorialRevisionRequisito,
    InformacionContrato029,
    PerfilRRHHEmpleado,
    Postulante,
    RegistroAuditoria,
    TipoDocumento,
)

admin.site.register(EstadoPostulacion)
admin.site.register(CatalogoRequisito)
admin.site.register(PerfilRRHHEmpleado)
admin.site.register(InformacionContrato029)
admin.site.register(HistorialEstadoPostulante)
admin.site.register(HistorialRevisionRequisito)
admin.site.register(EstadoControlMensual)
admin.site.register(TipoDocumento)
admin.site.register(ControlMensualContrato)
admin.site.register(DocumentoGestion)
admin.site.register(EstadoCasoJudicial)
admin.site.register(CasoJudicial)
admin.site.register(CasoActuacion)


@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("fecha", "usuario", "accion", "content_type", "object_id")
    list_filter = ("accion", "content_type")
    readonly_fields = (
        "usuario",
        "accion",
        "detalle",
        "fecha",
        "content_type",
        "object_id",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Postulante)
class PostulanteAdmin(admin.ModelAdmin):
    list_display = (
        "cui",
        "nombres",
        "apellidos",
        "programa_area",
        "estado_tdr",
        "responsable",
    )
    list_filter = ("estado_tdr",)
    search_fields = ("cui", "nombres", "apellidos")


class DetalleInline(admin.TabularInline):
    model = DetalleEvaluacionRequisito
    extra = 0


@admin.register(EvaluacionExpediente)
class EvaluacionAdmin(admin.ModelAdmin):
    inlines = (DetalleInline,)


@admin.register(ExpedienteEmpleado)
class ExpedienteEmpleadoAdmin(admin.ModelAdmin):
    list_display = ("empleado", "estado", "actualizado_por", "updated_at")
