from django.urls import path
from . import views

app_name = "diplomas"

urlpatterns = [
    path("cursos/", views.cursos_lista, name="cursos_lista"),
    path("cursos/crear/", views.crear_curso_modal, name="crear_curso_modal"),
    path("agregar-empleado/", views.agregar_empleado_a_curso, name="agregar_empleado_curso"),
    path("ajax/buscar-empleado/", views.buscar_empleado_por_dpi, name="buscar_empleado_por_dpi"),
    path("curso/<int:curso_id>/", views.detalle_curso, name="detalle_curso"),
    path("curso/<int:curso_id>/agregar/", views.agregar_empleado_detalle, name="agregar_empleado_detalle"),
    path("ajax/buscar-empleado/", views.buscar_empleado_por_dpi, name="buscar_empleado_por_dpi"),
    path("curso/<int:curso_id>/editar/", views.editar_curso, name="editar_curso"),
    path("firmas/", views.firmas_lista, name="firmas_lista"),
    path("firmas/crear/", views.crear_firma, name="crear_firma"),




]
