from django.contrib import admin

from .models import (CatalogoRequisito, DetalleEvaluacionRequisito, EstadoPostulacion,
                     EvaluacionExpediente, ExpedienteEmpleado, HistorialEstadoPostulante,
                     HistorialRevisionRequisito, InformacionContrato029, PerfilRRHHEmpleado,
                     Postulante)

admin.site.register(EstadoPostulacion)
admin.site.register(CatalogoRequisito)
admin.site.register(PerfilRRHHEmpleado)
admin.site.register(InformacionContrato029)
admin.site.register(HistorialEstadoPostulante)
admin.site.register(HistorialRevisionRequisito)


@admin.register(Postulante)
class PostulanteAdmin(admin.ModelAdmin):
    list_display = ("cui", "nombres", "apellidos", "programa_area", "estado_tdr", "responsable")
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
