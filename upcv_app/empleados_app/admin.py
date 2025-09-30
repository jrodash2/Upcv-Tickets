from django.contrib import admin
from .models import Contrato, Empleado
from .models import ConfiguracionGeneral
from datetime import datetime


class EmpleadoAdmin(admin.ModelAdmin):
    list_display = ('nombres', 'apellidos', 'dpi', 'imagen', 'fecha_vencimiento', 'activo', 'created_at', 'updated_at')
    list_filter = ('activo', 'fecha_vencimiento')
    search_fields = ('nombres', 'apellidos')
    date_hierarchy = 'created_at'
    fields = ('nombres', 'apellidos', 'dpi', 'imagen', 'tipoc', 'fecha_vencimiento', 'activo')


class ConfiguracionGeneralAdmin(admin.ModelAdmin):
    list_display = ('nombre_institucion', 'direccion', 'logotipo')  # Campos a mostrar en la lista
    search_fields = ('nombre_institucion', 'direccion')  # Campos por los que se puede buscar
    list_filter = ('nombre_institucion',)  # Campos por los que se puede filtrar
    readonly_fields = ('id',)  # Solo lectura para el campo ID (si es un campo automático)

class ContratoAdmin(admin.ModelAdmin):
    list_display = ('empleado', 'fecha_inicio', 'fecha_vencimiento', 'activo', 'created_at')
    list_filter = ('activo', 'fecha_inicio', 'fecha_vencimiento')
    search_fields = ('empleado__nombres', 'empleado__apellidos')
    date_hierarchy = 'fecha_inicio'
    autocomplete_fields = ['empleado']
    readonly_fields = ('created_at', 'updated_at')

    def save_model(self, request, obj, form, change):
        """Asegura que la lógica de desactivación se aplique también desde el admin."""
        if obj.fecha_vencimiento and obj.fecha_vencimiento <= datetime.today().date():
            obj.activo = False
        super().save_model(request, obj, form, change)
    
# Registro del modelo, solo una vez
admin.site.register(Empleado, EmpleadoAdmin)
admin.site.register(ConfiguracionGeneral, ConfiguracionGeneralAdmin)
admin.site.register(Contrato, ContratoAdmin)


