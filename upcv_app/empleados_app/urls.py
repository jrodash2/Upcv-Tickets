from django.urls import path
from . import views

app_name = 'empleados'


urlpatterns = [
    path('crear/', views.crear_empleado, name='crear_empleado'),
    path('signin/', views.signin, name='signin'),
    path('dahsboard/', views.dahsboard, name='dahsboard'), 
    path('config_general/', views.configuracion_general, name='configuracion_general'), 

    path('logout/', views.signout, name='logout',),
    path('lista/', views.lista_empleados, name='empleado_lista'),
    path('lista/<int:e_id>/', views.editar_empleado, name='editar_empleado',),
    path('credencial/', views.credencial_empleados, name='empleado_credencial'),
    path('', views.home, name='home'), 
    path('empleado/<int:id>/', views.empleado_detalle, name='empleado_detalle'),
    path('empleado/<int:empleado_id>/contrato/nuevo/', views.crear_contrato, name='crear_contrato'),
    path('empleado/<int:empleado_id>/contratos/', views.contratos, name='contratos'),
    path('exportar-empleados-excel/', views.exportar_empleados_excel, name='exportar_empleados_excel'),
    path('exportar-empleados-excel_029/', views.exportar_empleados_excel_029, name='exportar_empleados_excel_029'),
    path('exportar-empleados-excel_021/', views.exportar_empleados_excel_021, name='exportar_empleados_excel_021'),
    path('exportar-empleados-no-vigentes-excel/', views.exportar_empleados_no_vigentes_excel, name='exportar_empleados_no_vigentes_excel'),

]
