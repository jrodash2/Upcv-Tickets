from functools import wraps
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import redirect
from django.urls import reverse



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

