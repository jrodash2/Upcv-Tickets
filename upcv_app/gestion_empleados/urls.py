from django.urls import path

from . import views

app_name = "gestion_empleados"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("pre-seleccion/", views.area, {"area_slug": "preseleccion"}, name="preseleccion"),
    path("reclutamiento-seleccion/", views.area, {"area_slug": "reclutamiento"}, name="reclutamiento"),
    path("ficha-empleado/", views.area, {"area_slug": "ficha_empleado"}, name="ficha_empleado"),
    path("contratacion-029/", views.area, {"area_slug": "contratacion_029"}, name="contratacion_029"),
    path("gestion-personal/", views.area, {"area_slug": "gestion_personal"}, name="gestion_personal"),
    path("casos-demandas-judiciales/", views.area, {"area_slug": "casos_judiciales"}, name="casos_judiciales"),
]
