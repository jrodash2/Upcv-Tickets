from django.contrib import admin
from .models import Empleado

class EmpleadoAdmin(admin.ModelAdmin):
    list_display = ('nombres', 'apellidos', 'dpi', 'imagen', 'fecha_vencimiento', 'activo', 'created_at', 'updated_at')
    list_filter = ('activo', 'fecha_vencimiento')
    search_fields = ('nombres', 'apellidos')
    date_hierarchy = 'created_at'
    fields = ('nombres', 'apellidos', 'dpi', 'imagen', 'tipoc', 'fecha_vencimiento', 'activo')

# Registro del modelo, solo una vez
admin.site.register(Empleado, EmpleadoAdmin)
