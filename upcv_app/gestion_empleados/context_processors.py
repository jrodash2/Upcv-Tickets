from django.urls import reverse


def menu_gestion_empleados(request):
    """Única definición de navegación para sidebar y menú superior."""
    url_name = getattr(getattr(request, "resolver_match", None), "url_name", "")
    definiciones = (
        ("Dashboard", "dashboard", {"dashboard"}),
        ("Preselección", "preseleccion", {"preseleccion", "postulante_nuevo", "postulante_detalle", "postulante_editar"}),
        ("Reclutamiento y Selección", "reclutamiento", {"reclutamiento", "expediente", "proceso_detalle"}),
        ("Elegibles para Contratación", "elegibles", {"elegibles"}),
        ("Empleados", "empleados", {"empleados", "empleado_ficha", "empleado_editar"}),
        ("Contratación 029", "contratos", {"contratos", "contratacion"}),
        ("Gestión de Personal", "gestion_personal", {"gestion_personal", "control_mensual_detalle", "control_mensual_editar"}),
        ("Casos Judiciales", "casos", {"casos", "caso_detalle", "caso_crear", "caso_editar"}),
    )
    puede_ver_casos = bool(
        request.user.is_authenticated
        and (request.user.is_superuser or request.user.has_perm("gestion_empleados.ver_casos"))
    )
    opciones = []
    for etiqueta, nombre_url, vistas in definiciones:
        if nombre_url == "casos" and not puede_ver_casos:
            continue
        opciones.append({
            "etiqueta": etiqueta,
            "url": reverse(f"gestion_empleados:{nombre_url}"),
            "activa": url_name in vistas,
        })
    return {"menu_gestion_empleados": opciones}
