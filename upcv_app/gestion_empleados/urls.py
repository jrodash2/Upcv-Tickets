from django.urls import path
from . import views

app_name = "gestion_empleados"
urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("preseleccion/", views.preseleccion, name="preseleccion"),
    path("preseleccion/nuevo/", views.postulante_editar, name="postulante_nuevo"),
    path("preseleccion/<int:pk>/", views.postulante_detalle, name="postulante_detalle"),
    path(
        "preseleccion/<int:pk>/editar/",
        views.postulante_editar,
        name="postulante_editar",
    ),
    path(
        "preseleccion/<int:pk>/convertir/",
        views.postulante_convertir,
        name="postulante_convertir",
    ),
    path("reclutamiento/", views.reclutamiento, name="reclutamiento"),
    path("elegibles/", views.elegibles, name="elegibles"),
    path("procesos/<int:pk>/reclutamiento/", views.proceso_reclutamiento, name="proceso_reclutamiento"),
    path("procesos/<int:pk>/", views.proceso_detalle, name="proceso_detalle"),
    path(
        "reclutamiento/<int:proceso_id>/expediente/",
        views.expediente,
        name="expediente",
    ),
    path(
        "reclutamiento/<int:proceso_id>/expediente/completar/",
        views.expediente_completar,
        name="expediente_completar",
    ),
    path("reclutamiento/<int:proceso_id>/expediente/elegible/", views.expediente_elegible, name="expediente_elegible"),
    path(
        "reclutamiento/requisito/<int:pk>/revisar/",
        views.requisito_revisar,
        name="requisito_revisar",
    ),
    path("empleados/", views.empleados, name="empleados"),
    path("empleados/<int:pk>/", views.empleado_ficha, name="empleado_ficha"),
    path("empleados/<int:pk>/editar/", views.empleado_editar, name="empleado_editar"),
    path("empleados/<int:empleado_id>/<str:tipo>/iniciar/", views.iniciar_proceso, name="iniciar_proceso"),
    path(
        "procesos/<int:proceso_id>/contratacion/",
        views.contratacion,
        name="contratacion",
    ),
    path("contratos/", views.contratos, name="contratos"),
    path("gestion-personal/", views.gestion_personal, name="gestion_personal"),
    path(
        "gestion-personal/nuevo/",
        views.control_mensual_editar,
        name="control_mensual_nuevo",
    ),
    path(
        "gestion-personal/<int:pk>/",
        views.control_mensual_detalle,
        name="control_mensual_detalle",
    ),
    path(
        "gestion-personal/<int:pk>/editar/",
        views.control_mensual_editar,
        name="control_mensual_editar",
    ),
    path(
        "gestion-personal/<int:pk>/documentos/",
        views.control_documento_agregar,
        name="control_documento_agregar",
    ),
    path("casos/", views.casos, name="casos"),
    path("casos/nuevo/", views.caso_crear, name="caso_crear"),
    path("casos/<int:pk>/", views.caso_detalle, name="caso_detalle"),
    path("casos/<int:pk>/editar/", views.caso_editar, name="caso_editar"),
    path(
        "casos/<int:pk>/actuaciones/",
        views.caso_actuacion_agregar,
        name="caso_actuacion_agregar",
    ),
    path(
        "casos/<int:pk>/documentos/",
        views.caso_documento_agregar,
        name="caso_documento_agregar",
    ),
]
