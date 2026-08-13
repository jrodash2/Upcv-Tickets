from django.contrib import admin

from .models import ExpedienteEmpleado


@admin.register(ExpedienteEmpleado)
class ExpedienteEmpleadoAdmin(admin.ModelAdmin):
    list_display = ("empleado", "estado", "actualizado_por", "updated_at")
    list_filter = ("estado",)
    search_fields = ("empleado__nombres", "empleado__apellidos", "empleado__dpi")
    autocomplete_fields = ("empleado", "actualizado_por")
    readonly_fields = ("created_at", "updated_at")
