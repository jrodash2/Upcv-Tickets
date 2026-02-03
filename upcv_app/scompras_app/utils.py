from functools import wraps
from django.contrib.auth.views import redirect_to_login
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse


def is_admin(user):
    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name="Administrador").exists()
    )


def is_presupuesto(user):
    return user.is_authenticated and user.groups.filter(name="PRESUPUESTO").exists()


def es_presupuesto(user):
    return user.is_authenticated and user.groups.filter(name="PRESUPUESTO").exists()

def puede_imprimir_cdp(user):
    return user.is_authenticated and (
        user.groups.filter(name="Administrador").exists()
        or user.groups.filter(name="PRESUPUESTO").exists()
    )


def bloquear_presupuesto(view_func):
    """Bloquea acciones específicas para usuarios del grupo PRESUPUESTO."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if es_presupuesto(request.user):
            if request.headers.get("x-requested-with") == "XMLHttpRequest" or request.method == "POST":
                return JsonResponse({"success": False, "error": "No autorizado."}, status=403)
            return redirect(f"/no-autorizado/?next={request.path}")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def admin_only_config(view_func):
    """Restringe las vistas de configuración únicamente a administradores."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if is_admin(request.user):
            return view_func(request, *args, **kwargs)
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"detail": "No autorizado."}, status=403)
        response = redirect(reverse("scompras:acceso_denegado"))
        response.status_code = 403
        return response
    return _wrapped_view


class AdminOnlyConfigMixin:
    """Mixin para asegurar acceso administrativo en vistas de configuración."""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if is_admin(request.user):
            return super().dispatch(request, *args, **kwargs)
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"detail": "No autorizado."}, status=403)
        response = redirect(reverse("scompras:acceso_denegado"))
        response.status_code = 403
        return response


def grupo_requerido(*nombres_grupos):
    def decorador(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_authenticated and (
                request.user.groups.filter(name__in=nombres_grupos).exists() or request.user.is_superuser
            ):
                return view_func(request, *args, **kwargs)
            # Redirigir a la vista de acceso denegado
            return redirect(reverse('scompras:acceso_denegado'))
        return _wrapped_view
    return decorador
