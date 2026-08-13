from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

GRUPOS_ADMINISTRATIVOS = ("Admin_gafetes", "Administrador")


def puede_acceder(user, permiso="gestion_empleados.view_gestion_empleados"):
    return user.is_authenticated and (
        user.is_superuser
        or user.has_perm(permiso)
        or user.groups.filter(name__in=GRUPOS_ADMINISTRATIVOS).exists()
    )


def permiso_gestion_requerido(permiso="gestion_empleados.view_gestion_empleados"):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not puede_acceder(request.user, permiso):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator


def permiso_estricto_requerido(permiso):
    """No concede acceso por pertenecer a grupos generales; se usa para datos jurídicos."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not (request.user.is_superuser or request.user.has_perm(permiso)):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator
