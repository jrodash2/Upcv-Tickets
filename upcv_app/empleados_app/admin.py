from django.contrib import admin
from .models import Empleado
from .models import ConfiguracionGeneral

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


# Registro del modelo, solo una vez
admin.site.register(Empleado, EmpleadoAdmin)
admin.site.register(ConfiguracionGeneral, ConfiguracionGeneralAdmin)

