from django.shortcuts import render

from .permissions import permiso_gestion_requerido
from .selectors import obtener_indicadores_dashboard


@permiso_gestion_requerido()
def dashboard(request):
    return render(
        request,
        "gestion_empleados/dashboard.html",
        {"indicadores": obtener_indicadores_dashboard()},
    )


AREAS = {
    "preseleccion": ("Pre-Selección", "Registro y seguimiento inicial de candidatos."),
    "reclutamiento": ("Reclutamiento y Selección", "Evaluación ordenada del proceso de selección."),
    "ficha_empleado": ("Ficha del Empleado", "Vista integral de la información oficial del empleado."),
    "contratacion_029": ("Contratación 029", "Gestión contractual para el renglón 029."),
    "gestion_personal": ("Gestión de Personal", "Seguimiento administrativo del personal."),
    "casos_judiciales": ("Casos y Demandas Judiciales", "Arquitectura preparada para el seguimiento jurídico."),
}


PERMISOS_AREA = {
    "preseleccion": "gestion_empleados.manage_preselection",
    "reclutamiento": "gestion_empleados.manage_preselection",
    "ficha_empleado": "gestion_empleados.review_employee_files",
    "contratacion_029": "gestion_empleados.manage_employee_contracts",
    "gestion_personal": "gestion_empleados.view_gestion_empleados",
    "casos_judiciales": "gestion_empleados.view_gestion_empleados",
}


def area(request, area_slug):
    titulo, descripcion = AREAS[area_slug]
    permiso = PERMISOS_AREA[area_slug]

    @permiso_gestion_requerido(permiso)
    def render_area(inner_request):
        return render(inner_request, "gestion_empleados/area.html", {
            "area_actual": area_slug,
            "titulo": titulo,
            "descripcion": descripcion,
        })

    return render_area(request)
