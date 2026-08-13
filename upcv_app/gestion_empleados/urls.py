from django.urls import path
from . import views

app_name = "gestion_empleados"
urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("preseleccion/", views.preseleccion, name="preseleccion"),
    path("preseleccion/nuevo/", views.postulante_editar, name="postulante_nuevo"),
    path("preseleccion/<int:pk>/", views.postulante_detalle, name="postulante_detalle"),
    path("preseleccion/<int:pk>/editar/", views.postulante_editar, name="postulante_editar"),
    path("preseleccion/<int:pk>/convertir/", views.postulante_convertir, name="postulante_convertir"),
    path("reclutamiento/", views.reclutamiento, name="reclutamiento"),
    path("reclutamiento/<int:postulante_id>/expediente/", views.expediente, name="expediente"),
    path("reclutamiento/<int:postulante_id>/expediente/completar/", views.expediente_completar, name="expediente_completar"),
    path("reclutamiento/requisito/<int:pk>/revisar/", views.requisito_revisar, name="requisito_revisar"),
    path("empleados/", views.empleados, name="empleados"),
    path("empleados/<int:pk>/", views.empleado_ficha, name="empleado_ficha"),
    path("empleados/<int:pk>/editar/", views.empleado_editar, name="empleado_editar"),
    path("empleados/<int:empleado_id>/contratacion/", views.contratacion, name="contratacion"),
    path("contratos/", views.contratos, name="contratos"),
]
