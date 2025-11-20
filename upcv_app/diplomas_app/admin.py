from django.contrib import admin
from .models import Firma, Curso, CursoEmpleado, Diploma


# ================
# ADMIN FIRMA
# ================
@admin.register(Firma)
class FirmaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "rol", "creado_en")
    search_fields = ("nombre", "rol")
    list_filter = ("creado_en",)


# ================
# INLINE para ver participantes desde el Curso
# ================
class CursoEmpleadoInline(admin.TabularInline):
    model = CursoEmpleado
    extra = 0
    autocomplete_fields = ("empleado",)


# ================
# ADMIN CURSO
# ================
@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "fecha_inicio", "fecha_fin", "creado_en")
    search_fields = ("codigo", "nombre")
    list_filter = ("fecha_inicio", "fecha_fin")
    filter_horizontal = ("firmas",)      # Para elegir firmas más fácil
    inlines = [CursoEmpleadoInline]       # Muestra participantes dentro del curso

    # Para proteger el campo JSON
    readonly_fields = ("posiciones",)


# ================
# ADMIN CURSO-EMPLEADO
# ================
@admin.register(CursoEmpleado)
class CursoEmpleadoAdmin(admin.ModelAdmin):
    list_display = ("curso", "empleado", "fecha_asignacion")
    search_fields = ("empleado__nombres", "empleado__apellidos", "curso__nombre")
    list_filter = ("curso", "fecha_asignacion")
    autocomplete_fields = ("curso", "empleado")


# ================
# ADMIN DIPLOMA
# ================
@admin.register(Diploma)
class DiplomaAdmin(admin.ModelAdmin):
    list_display = ("numero_diploma", "curso_empleado", "fecha_emision", "generado_en")
    search_fields = ("numero_diploma", "curso_empleado__empleado__nombres",
                     "curso_empleado__empleado__apellidos")
    list_filter = ("fecha_emision", "generado_en")
    autocomplete_fields = ("curso_empleado",)

    # Para que no editen accidentalmente
    readonly_fields = ("generado_en",)
