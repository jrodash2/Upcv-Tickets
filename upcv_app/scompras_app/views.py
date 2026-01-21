from datetime import datetime, timezone
from django.utils.timezone import localtime
from venv import logger
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.forms import IntegerField
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import Group, User
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.urls import reverse
import openpyxl
from django.views.decorators.csrf import csrf_exempt
import pandas as pd
from .form import (
    ExcelUploadForm,
    SeccionForm,
    FechaInsumoForm,
    PerfilForm,
    SolicitudCompraForm,
    SolicitudCompraFormcrear,
    UserCreateForm,
    UserEditForm,
    UserCreateForm,
    DepartamentoForm,
    UsuarioDepartamentoForm,
    InstitucionForm,
    CDPForm,
    PresupuestoRenglonForm,
    PresupuestoAnualForm,
    PresupuestoCargaMasivaForm,
    EjecutarCDPForm,
    LiberarCDPForm,
    LiberarCDPSolicitudForm,
    TransferenciaPresupuestariaForm,
)
from .models import (
    FechaInsumo,
    Producto,
    Insumo,
    InsumoSolicitud,
    Perfil,
    Departamento,
    Seccion,
    SolicitudCompra,
    Subproducto,
    UsuarioDepartamento,
    Institucion,
    Servicio,
    ServicioSolicitud,
    CDP,
    CDO,
    PresupuestoRenglon,
    PresupuestoAnual,
    TransferenciaPresupuestaria,
    KardexPresupuesto,
)
from django.views.generic import CreateView
from django.views.generic import ListView
from django.urls import reverse_lazy
from django.http import Http404, HttpResponseNotAllowed, JsonResponse
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.db import models
from django.db.models import Sum, F, Value, Count, Q, Case, When, OuterRef, Subquery, IntegerField, DecimalField, ExpressionWrapper
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import redirect_to_login
from collections import defaultdict
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
import json
from django.contrib.auth.models import Group
from .utils import grupo_requerido
from .services.presupuesto_import import import_rows, read_rows
from django.views.decorators.http import require_GET
from django.db.models.functions import Coalesce
from django.db import transaction, IntegrityError
from django.db.models import Sum
from django.shortcuts import render
from django.template.loader import render_to_string
from django.template.loader import get_template
from django.http import HttpResponse
from xhtml2pdf import pisa
from weasyprint import HTML
from django.db.models.functions import Cast, TruncWeek
from django.utils import timezone
from datetime import timedelta
from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
import datetime
from django.core.mail import send_mail
from django.conf import settings
from django.utils.html import strip_tags
from decimal import Decimal
from datetime import datetime  
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Alignment, Font
import re
from django.views.generic.detail import DetailView
from django.core.mail import BadHeaderError
from smtplib import SMTPException
from django.db.models import Count
from django.db.models.functions import ExtractYear, ExtractMonth
from datetime import date
from xhtml2pdf import pisa
from io import BytesIO
from django.contrib.auth.backends import ModelBackend
from django.db import connections


class TicketsAuthBackend(ModelBackend):
    """
    Backend que permite autenticar usuarios desde la base de datos de Tickets.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            # Conexión al alias 'tickets_db'
            with connections['tickets_db'].cursor() as cursor:
                user = User.objects.using('tickets_db').get(username=username)
                if user.check_password(password) and user.is_active:
                    return user
        except User.DoesNotExist:
            return None
        return None

    def get_user(self, user_id):
        try:
            return User.objects.using('tickets_db').get(pk=user_id)
        except User.DoesNotExist:
            return None

@login_required
@grupo_requerido('Administrador')
def editar_institucion(request):
    institucion = Institucion.objects.first()  # Solo debería haber una

    if request.method == 'POST':
        form = InstitucionForm(request.POST, request.FILES, instance=institucion)
        if form.is_valid():
            form.save()
            messages.success(request, "Datos institucionales actualizados correctamente.")
            return redirect('scompras:editar_institucion')  # Reemplaza con la URL real
    else:
        form = InstitucionForm(instance=institucion)

    return render(request, 'scompras/editar_institucion.html', {'form': form})


from django.db import IntegrityError

from scompras_app.models_empleados import Empleado  # 🔹 modelo de empleados (Ticktes)

# ... imports iguales
from scompras_app.models_empleados import Empleado

@login_required
@grupo_requerido('Administrador', 'scompras')
def asignar_departamento_usuario(request):

    if request.method == 'POST':
        form = UsuarioDepartamentoForm(request.POST)
        if form.is_valid():
            UsuarioDepartamento.objects.create(
                usuario_id=form.cleaned_data['usuario'].id,   # ← solo el ID!
                departamento=form.cleaned_data['departamento'],
                seccion=form.cleaned_data['seccion']
            )
            messages.success(request, "Departamento asignado correctamente")
            return redirect("scompras:asignar_departamento")
        else:
            messages.error(request, "Corrige los errores del formulario.")
    else:
        form = UsuarioDepartamentoForm()

    # Asignaciones
    asignaciones = UsuarioDepartamento.objects.select_related('departamento', 'seccion')

    # Mapa empleados
    empleados_map = {
        e.user_id: e for e in Empleado.objects.using('tickets_db').all()
    }

    filas = []
    agrupado = {}

    for a in asignaciones:
        agrupado.setdefault(a.usuario_id, []).append(a)

    for uid, asigns in agrupado.items():
        user = User.objects.using('tickets_db').filter(id=uid).first()
        filas.append({
            'usuario': user,
            'empleado': empleados_map.get(uid),
            'asignaciones': asigns
        })

    return render(request, "scompras/asignar_departamento.html", {
        "form": form,
        "filas": filas
    })

    return render(request, 'scompras/asignar_departamento.html', context)




def eliminar_asignacion(request, usuario_id, departamento_id, seccion_id):
    """
    Elimina una asignación usuario-departamento-sección.
    """
    if request.method == 'POST':
        asignacion = get_object_or_404(
            UsuarioDepartamento,
            usuario_id=usuario_id,
            departamento_id=departamento_id,
            seccion_id=seccion_id
        )
        asignacion.delete()
        messages.success(request, 'Asignación eliminada correctamente.')
    else:
        messages.error(request, 'Método no permitido.')
    return redirect('scompras:asignar_departamento')


@login_required
@require_GET
def cargar_secciones(request):
    """
    Carga dinámica de secciones por departamento.
    """
    departamento_id = request.GET.get('departamento_id')
    secciones = Seccion.objects.filter(departamento_id=departamento_id).values('id', 'nombre').order_by('nombre')
    return JsonResponse({'secciones': list(secciones)}, safe=False)

def ajax_cargar_secciones(request):
    departamento_id = request.GET.get('departamento_id')
    secciones = Seccion.objects.filter(departamento_id=departamento_id).values('id', 'nombre')
    secciones_list = list(secciones)
    return JsonResponse({'secciones': secciones_list})

@login_required
def lista_departamentos(request):
    user = request.user
    grupos_usuario = list(user.groups.values_list('name', flat=True))

    es_admin = 'Administrador' in grupos_usuario
    es_departamento = 'Departamento' in grupos_usuario
    es_scompras = 'scompras' in grupos_usuario

    if es_admin:
        # Admin ve todo y tiene acceso completo
        departamentos = Departamento.objects.all()
        departamentos_usuario_ids = list(departamentos.values_list('id', flat=True))
    elif es_departamento or es_scompras:
        # Solo departamentos asignados
        departamentos_usuario_ids = list(
            UsuarioDepartamento.objects.filter(usuario=user)
            .values_list('departamento_id', flat=True)
            .distinct()
        )
        departamentos = Departamento.objects.filter(id__in=departamentos_usuario_ids)
    else:
        # No tiene grupo válido
        departamentos_usuario_ids = []
        departamentos = Departamento.objects.none()

    return render(request, 'scompras/lista_departamentos.html', {
        'departamentos': departamentos,
        'departamentos_usuario_ids': departamentos_usuario_ids,
        'es_departamento': es_departamento,
        'es_admin': es_admin,
    })




@login_required
def detalle_seccion(request, departamento_id, seccion_id):
    seccion = get_object_or_404(Seccion, pk=seccion_id, departamento__id=departamento_id)
    user = request.user

    grupos_usuario = list(user.groups.values_list('name', flat=True))
    es_admin = 'Administrador' in grupos_usuario
    es_scompras = 'scompras' in grupos_usuario

    if not (es_admin or es_scompras):
        tiene_acceso = UsuarioDepartamento.objects.filter(
            usuario=user,
            departamento=seccion.departamento,
            seccion=seccion
        ).exists()
        if not tiene_acceso:
            return render(request, 'scompras/403.html', status=403)

    # Manejo del formulario
    if request.method == 'POST':
        form = SolicitudCompraFormcrear(request.POST)
        if form.is_valid():
            solicitud = form.save(commit=False)
            solicitud.usuario = user
            solicitud.departamento = seccion.departamento
            solicitud.seccion = seccion
            solicitud.save()
            messages.success(request, "Solicitud creada exitosamente.")
            return redirect('scompras:detalle_seccion', departamento_id=departamento_id, seccion_id=seccion_id)
        else:
            # Debug: errores en consola
            print(form.errors)
            messages.error(request, "Por favor corrige los errores en el formulario.")
    else:
        form = SolicitudCompraFormcrear()

    solicitudes = SolicitudCompra.objects.filter(seccion=seccion).order_by('-fecha_solicitud')[:10]
    secciones = seccion.departamento.secciones.filter(activo=True)
    todas_solicitudes = SolicitudCompra.objects.filter(seccion=seccion).order_by('-fecha_solicitud')


    context = {
        'seccion': seccion,
        'form': form,
        'solicitudes': solicitudes,
        'todas_solicitudes': todas_solicitudes, 
        'secciones': secciones,
    }
    return render(request, 'scompras/detalle_seccion.html', context)


@login_required
def detalle_seccion_usuario(request):
    user = request.user

    # Validar si pertenece al grupo "scompras"
    if not user.groups.filter(name='scompras').exists():
        return render(request, 'scompras/403.html', status=403)

    # Buscar la asignación del usuario a una sección
    asignacion = UsuarioDepartamento.objects.filter(usuario=user).select_related('departamento', 'seccion').first()
    
    if not asignacion or not asignacion.seccion:
        messages.warning(request, "No tienes asignada ninguna sección.")
        return render(request, 'scompras/sin_seccion.html')

    seccion = asignacion.seccion
    departamento = asignacion.departamento

    # Formulario para crear solicitudes
    if request.method == 'POST':
        form = SolicitudCompraFormcrear(request.POST)
        if form.is_valid():
            solicitud = form.save(commit=False)
            solicitud.usuario = user
            solicitud.departamento = departamento
            solicitud.seccion = seccion
            solicitud.save()
            messages.success(request, "Solicitud creada exitosamente.")
            return redirect('scompras:detalle_seccion_usuario')
        else:
            print(form.errors)
            messages.error(request, "Por favor corrige los errores en el formulario.")
    else:
        form = SolicitudCompraFormcrear()

    # Datos a mostrar
    solicitudes = SolicitudCompra.objects.filter(seccion=seccion).order_by('-fecha_solicitud')[:10]
    todas_solicitudes = SolicitudCompra.objects.filter(seccion=seccion).order_by('-fecha_solicitud')
    secciones = departamento.secciones.filter(activo=True)

    context = {
        'seccion': seccion,
        'departamento': departamento,
        'form': form,
        'solicitudes': solicitudes,
        'todas_solicitudes': todas_solicitudes,
        'secciones': secciones,
    }

    return render(request, 'scompras/detalle_seccion_usuario.html', context)


def ajax_cargar_subproductos(request):
    producto_id = request.GET.get('producto_id')
    print("Producto ID recibido en AJAX:", producto_id)
    if producto_id:
        subproductos = Subproducto.objects.filter(producto_id=producto_id).values('id', 'nombre')
        data = list(subproductos)
    else:
        data = []
    return JsonResponse(data, safe=False)


@login_required
@grupo_requerido('Administrador', 'scompras')
def subproductos_por_producto(request):
    producto_id = request.GET.get('producto_id')
    subproductos = Subproducto.objects.none()
    if producto_id:
        subproductos = Subproducto.objects.filter(producto_id=producto_id, activo=True).order_by('codigo', 'nombre')
    data = [
        {
            'id': subproducto.id,
            'label': f"{subproducto.codigo} - {subproducto.nombre}" if subproducto.codigo else subproducto.nombre,
        }
        for subproducto in subproductos
    ]
    return JsonResponse({'results': data})


# Views for Departamento
@login_required
@grupo_requerido('Administrador', 'scompras')
def crear_departamento(request):
    departamentos = Departamento.objects.all()  # Obtener todos los departamentos
    form = DepartamentoForm(request.POST or None)  # Crear el formulario
    if form.is_valid():
        form.save()  # Guardar el nuevo departamento
        return redirect('scompras:crear_departamento')  # Redirige a la misma página para mostrar el nuevo departamento
    return render(request, 'scompras/crear_departamento.html', {'form': form, 'departamentos': departamentos})

@login_required
@grupo_requerido('Administrador', 'scompras')
def editar_departamento(request, pk):
    departamento = get_object_or_404(Departamento, pk=pk)  # Obtener el departamento por su PK
    form = DepartamentoForm(request.POST or None, instance=departamento)  # Rellenar el formulario con los datos existentes
    if form.is_valid():
        form.save()  # Guardar los cambios en el departamento
        return redirect('scompras:crear_departamento')  # Redirige a la vista de creación (o a donde desees)
    return render(request, 'scompras/editar_departamento.html', {'form': form, 'departamentos': Departamento.objects.all()})


def crear_seccion(request, pk=None):
    if pk:
        seccion = get_object_or_404(Seccion, pk=pk)
        form = SeccionForm(request.POST or None, instance=seccion)
        mensaje_exito = "Sección actualizada correctamente."
    else:
        seccion = None
        form = SeccionForm(request.POST or None)
        mensaje_exito = "Sección creada correctamente."

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, mensaje_exito)
        return redirect('scompras:crear_seccion')

    secciones = Seccion.objects.select_related('departamento').all()

    context = {
        'form': form,
        'secciones': secciones,
    }
    return render(request, 'scompras/crear_seccion.html', context)

@login_required
@grupo_requerido('Administrador', 'scompras')
def user_create(request):
    if request.method == 'POST':
        form = UserCreateForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save(commit=False)
            password = form.cleaned_data.get('new_password')
            user.set_password(password)
            user.save()

            group = form.cleaned_data.get('group')
            user.groups.add(group)

            # ✅ Espera a que la señal cree el perfil automáticamente
            foto = form.cleaned_data.get('foto')
            try:
                perfil = user.perfil  # accede al perfil creado por la señal
                if foto:
                    perfil.foto = foto
                    perfil.save()
            except Perfil.DoesNotExist:
                # Fallback solo si la señal falló (raro)
                Perfil.objects.create(user=user, foto=foto)

            messages.success(request, 'Usuario creado correctamente.')
            return redirect('scompras:user_create')
    else:
        form = UserCreateForm()

    users = User.objects.all()
    return render(request, 'scompras/user_form_create.html', {'form': form, 'users': users})

@login_required
@grupo_requerido('Administrador', 'scompras')
def user_edit(request, user_id):
    user = get_object_or_404(User, pk=user_id)

    if request.method == 'POST':
        form = UserEditForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Usuario editado correctamente.')
            return redirect('scompras:user_edit', user_id=user.id)
    else:
        form = UserEditForm(instance=user)

    context = {
        'form': form,
        'user': user,
        'users': User.objects.all(),
    }
    return render(request, 'scompras/user_form_edit.html', context)

from django.utils.timezone import localtime
from django.template.defaultfilters import date as django_date


@login_required
@grupo_requerido('Administrador', 'scompras')
def presupuesto_anual_list(request):
    presupuestos = (
        PresupuestoAnual.objects.prefetch_related('renglones')
        .annotate(total_renglones=Count('renglones'))
        .order_by('-anio')
    )
    return render(
        request,
        'scompras/presupuestos_list.html',
        {
            'presupuestos': presupuestos,
            # Simplify template conditions by passing a boolean flag instead of calling
            # queryset methods from the template engine.
            'es_admin': request.user.is_superuser
            or request.user.groups.filter(name='Administrador').exists(),
        },
    )


@login_required
@grupo_requerido('Administrador', 'scompras')
def presupuesto_anual_crear(request):
    if request.method == 'POST':
        form = PresupuestoAnualForm(request.POST)
        if form.is_valid():
            presupuesto = form.save()
            messages.success(request, 'Presupuesto anual creado correctamente.')
            return redirect('scompras:presupuesto_anual_detalle', presupuesto_id=presupuesto.id)
    else:
        form = PresupuestoAnualForm()

    return render(
        request,
        'scompras/presupuesto_form.html',
        {
            'form': form,
        },
    )


@login_required
@grupo_requerido('Administrador', 'scompras')
def presupuesto_anual_detalle(request, presupuesto_id):
    presupuesto = get_object_or_404(PresupuestoAnual.objects.prefetch_related('renglones'), pk=presupuesto_id)
    user = request.user
    es_admin = user.is_superuser or user.groups.filter(name='Administrador').exists()
    renglones = presupuesto.renglones.select_related('producto', 'subproducto').all()

    if request.method == 'POST':
        if not presupuesto.activo:
            messages.error(request, 'Solo el presupuesto activo permite crear renglones. Active este presupuesto primero.')
            return redirect('scompras:presupuesto_anual_detalle', presupuesto_id=presupuesto.id)
        form = PresupuestoRenglonForm(request.POST, presupuesto_anual=presupuesto)
        if form.is_valid():
            renglon = form.save(commit=False)
            renglon.presupuesto_anual = presupuesto
            try:
                renglon.save()
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, 'Renglón creado correctamente.')
                return redirect('scompras:presupuesto_anual_detalle', presupuesto_id=presupuesto.id)
    else:
        form = PresupuestoRenglonForm(presupuesto_anual=presupuesto)

    resumen = renglones.aggregate(
        total_inicial=Coalesce(Sum('monto_inicial'), Value(0, output_field=models.DecimalField(max_digits=14, decimal_places=2))),
        total_modificado=Coalesce(Sum('monto_modificado'), Value(0, output_field=models.DecimalField(max_digits=14, decimal_places=2))),
        total_reservado=Coalesce(Sum('monto_reservado'), Value(0, output_field=models.DecimalField(max_digits=14, decimal_places=2))),
        total_ejecutado=Coalesce(Sum('monto_ejecutado'), Value(0, output_field=models.DecimalField(max_digits=14, decimal_places=2))),
    )
    resumen['total_disponible'] = (resumen['total_inicial'] + resumen['total_modificado']) - (
        resumen['total_reservado'] + resumen['total_ejecutado']
    )

    return render(
        request,
        'scompras/presupuesto_detalle.html',
        {
            'presupuesto': presupuesto,
            'renglones': renglones,
            'form': form,
            'resumen': resumen,
            'es_admin': es_admin,
        },
    )


@login_required
@grupo_requerido('Administrador', 'scompras')
def presupuesto_renglon_carga_masiva(request, presupuesto_id):
    presupuesto = get_object_or_404(PresupuestoAnual, pk=presupuesto_id)
    resultado = None

    if request.method == 'POST':
        form = PresupuestoCargaMasivaForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = form.cleaned_data['archivo']
            modo = form.cleaned_data.get('modo') or 'solo_crear'
            try:
                filas = read_rows(archivo)
                resultado = import_rows(
                    presupuesto=presupuesto,
                    rows=filas,
                    filename=archivo.name,
                    modo=modo,
                )
                messages.success(
                    request,
                    (
                        f"Carga finalizada. Filas: {resultado['total']}, "
                        f"creados: {resultado['creados']}, "
                        f"duplicados: {resultado['duplicados']}, "
                        f"actualizados: {resultado['actualizados']}."
                    ),
                )
            except ValidationError as exc:
                form.add_error('archivo', exc)
    else:
        form = PresupuestoCargaMasivaForm()

    return render(
        request,
        'scompras/presupuesto_carga_masiva.html',
        {
            'presupuesto': presupuesto,
            'form': form,
            'resultado': resultado,
        },
    )


@login_required
@grupo_requerido('Administrador')
def transferencias_list(request):
    presupuesto_activo = PresupuestoAnual.presupuesto_activo()
    transferencias = TransferenciaPresupuestaria.objects.select_related(
        'renglon_origen',
        'renglon_origen__producto',
        'renglon_origen__subproducto',
        'renglon_destino',
        'renglon_destino__producto',
        'renglon_destino__subproducto',
        'presupuesto_anual',
    )
    if presupuesto_activo:
        transferencias = transferencias.filter(presupuesto_anual=presupuesto_activo)
    else:
        messages.warning(request, 'No hay presupuesto activo para listar transferencias.')
        transferencias = transferencias.none()

    return render(
        request,
        'scompras/transferencias_list.html',
        {
            'transferencias': transferencias,
            'presupuesto_activo': presupuesto_activo,
        },
    )


@login_required
@grupo_requerido('Administrador')
def transferencia_crear(request):
    presupuesto_activo = PresupuestoAnual.presupuesto_activo()
    if not presupuesto_activo:
        messages.error(request, 'No hay presupuesto activo. Active un presupuesto para crear transferencias.')
        return redirect('scompras:presupuesto_anual_list')

    origen_param = request.GET.get('origen')
    origen_inicial = None
    if origen_param:
        try:
            origen_inicial = PresupuestoRenglon.objects.get(pk=origen_param)
            if origen_inicial.presupuesto_anual_id != presupuesto_activo.id:
                messages.warning(request, 'Solo se pueden transferir renglones del presupuesto activo.')
                origen_inicial = None
        except PresupuestoRenglon.DoesNotExist:
            messages.warning(request, 'El renglón origen indicado no existe o no pertenece al presupuesto activo.')

    if request.method == 'POST':
        form = TransferenciaPresupuestariaForm(request.POST, presupuesto_activo=presupuesto_activo)
        if form.is_valid():
            try:
                form.save()
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, 'Transferencia realizada y registrada en el kardex.')
                return redirect('scompras:presupuesto_anual_detalle', presupuesto_id=presupuesto_activo.id)
    else:
        initial = {}
        if origen_inicial:
            initial['renglon_origen'] = origen_inicial
        form = TransferenciaPresupuestariaForm(presupuesto_activo=presupuesto_activo, initial=initial)

    return render(
        request,
        'scompras/transferencia_form.html',
        {
            'form': form,
            'presupuesto_activo': presupuesto_activo,
        },
    )


@login_required
@grupo_requerido('Administrador', 'scompras')
@require_POST
def activar_presupuesto(request, presupuesto_id):
    presupuesto = get_object_or_404(PresupuestoAnual, pk=presupuesto_id)
    presupuesto.activar()
    messages.success(request, f'Presupuesto {presupuesto.anio} activado. Los demás presupuestos han sido desactivados.')
    return redirect('scompras:presupuesto_anual_detalle', presupuesto_id=presupuesto.id)


@login_required
@grupo_requerido('Administrador', 'scompras')
def kardex_renglon(request, renglon_id):
    renglon = get_object_or_404(
        PresupuestoRenglon.objects.select_related(
            'presupuesto_anual',
            'producto',
            'subproducto',
        ),
        pk=renglon_id,
    )
    titulo_detallado = f"Kardex del renglón {renglon.label_compacto} ({renglon.presupuesto_anual.anio})"

    movimientos = renglon.kardex.select_related(
        'solicitud',
        'transferencia',
        'transferencia__renglon_origen',
        'transferencia__renglon_origen__producto',
        'transferencia__renglon_origen__subproducto',
        'transferencia__renglon_destino',
        'transferencia__renglon_destino__producto',
        'transferencia__renglon_destino__subproducto',
    ).order_by('fecha', 'id')
    tipo = request.GET.get('tipo')
    if tipo:
        movimientos = movimientos.filter(tipo=tipo)
    return render(
        request,
        'scompras/kardex_renglon.html',
        {
            'renglon': renglon,
            'movimientos': movimientos,
            'tipos': KardexPresupuesto.TipoMovimiento.choices,
            'tipo_filtrado': tipo,
            'titulo_detallado': titulo_detallado,
        },
    )

class SolicitudCompraDetailView(DetailView):
    model = SolicitudCompra
    template_name = 'scompras/detalle_solicitud.html'
    context_object_name = 'solicitud'


    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        solicitud = self.get_object()

        user = self.request.user
        es_admin = user.is_superuser or user.groups.filter(name='Administrador').exists()
        es_scompras = user.groups.filter(name='scompras').exists()
        estado_finalizada = solicitud.estado == 'Finalizada'
        estado_rechazada = solicitud.estado == 'Rechazada'

        # Convertir la fecha de solicitud a la zona horaria local
        solicitud.fecha_solicitud = localtime(solicitud.fecha_solicitud)

        # Formatear la fecha y agregarla al contexto
        context['fecha_solicitud_formateada'] = django_date(solicitud.fecha_solicitud, 'j \\d\\e F \\d\\e Y')

        context['insumos'] = Insumo.objects.all()
        context['detalles'] = InsumoSolicitud.objects.filter(solicitud=solicitud)
        context['servicios'] = ServicioSolicitud.objects.filter(solicitud=solicitud)
        context['ultima_fecha_insumo'] = FechaInsumo.objects.last()
        context['productos'] = Producto.objects.filter(activo=True)
        context['subproductos'] = Subproducto.objects.filter(activo=True)
        cdps = solicitud.cdps.select_related('renglon', 'renglon__presupuesto_anual', 'cdo').all()
        context['cdps'] = cdps
        context['tiene_cdo'] = cdps.filter(cdo__isnull=False).exists()
        context['cdps_reservados'] = cdps.filter(estado=CDP.Estado.RESERVADO)
        context['cdps_ejecutados'] = cdps.filter(estado=CDP.Estado.EJECUTADO)

        if cdps:
            cdp_principal = cdps.first()
            context['cdp_principal'] = cdp_principal
            total_cdp = cdps.aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
            if cdps.filter(estado=CDP.Estado.EJECUTADO).exists():
                estado_resumen = CDP.Estado.EJECUTADO
            elif cdps.filter(estado=CDP.Estado.RESERVADO).exists():
                estado_resumen = CDP.Estado.RESERVADO
            elif cdps.filter(estado=CDP.Estado.LIBERADO).exists():
                estado_resumen = CDP.Estado.LIBERADO
            else:
                estado_resumen = None
            context['cdp_resumen'] = {
                'id': cdp_principal.id,
                'estado': estado_resumen,
                'estado_display': dict(CDP.Estado.choices).get(estado_resumen, 'Sin estado'),
                'monto_total': total_cdp,
            }
            context['cdp_reservado_para_accion'] = cdps.filter(estado=CDP.Estado.RESERVADO).first()
            context['cdp_totales'] = {
                'total_reservado': cdps.aggregate(total=Sum('monto', filter=Q(estado=CDP.Estado.RESERVADO)))['total']
                or Decimal('0.00'),
                'total_ejecutado': cdps.aggregate(total=Sum('monto', filter=Q(estado=CDP.Estado.EJECUTADO)))['total']
                or Decimal('0.00'),
            }

        usuario_puede_presupuesto = (
            es_admin
        )

        presupuesto_activo = PresupuestoAnual.presupuesto_activo()
        context['presupuesto_activo'] = presupuesto_activo

        context['puede_crear_cdp'] = (
            usuario_puede_presupuesto
            and not context['tiene_cdo']
            and presupuesto_activo is not None
            and not estado_rechazada
        )
        context['puede_gestionar_cdp'] = usuario_puede_presupuesto
        context['estado_finalizada'] = estado_finalizada
        context['estado_rechazada'] = estado_rechazada
        context['es_admin'] = es_admin
        context['es_scompras'] = es_scompras
        context['mostrar_acciones_solicitud'] = not (estado_finalizada or estado_rechazada)
        context['mostrar_liberar_todos'] = (
            es_admin
            and not context['tiene_cdo']
            and context['cdps_reservados'].exists()
        )
        context['puede_editar_caracteristica'] = solicitud.estado in ['Creada', 'Finalizada']

        return context


@login_required
@grupo_requerido('Administrador')
def crear_cdp_solicitud(request, solicitud_id):
    solicitud = get_object_or_404(SolicitudCompra, pk=solicitud_id)

    presupuesto_activo = PresupuestoAnual.presupuesto_activo()
    if not presupuesto_activo:
        messages.error(request, 'No hay presupuesto activo. Active un presupuesto anual antes de crear un CDP.')
        return redirect('scompras:detalle_solicitud', pk=solicitud.id)

    if solicitud.cdps.filter(cdo__isnull=False).exists():
        messages.error(request, 'La solicitud ya cuenta con un CDO generado, no puede crear nuevos CDP.')
        return redirect('scompras:detalle_solicitud', pk=solicitud.id)

    if request.method == 'POST':
        form = CDPForm(solicitud, request.POST)
        if form.is_valid():
            cdp = form.save(commit=False)
            cdp.solicitud = solicitud
            try:
                cdp.save()
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, 'CDP creado y presupuesto reservado correctamente.')
                return redirect('scompras:detalle_solicitud', pk=solicitud.id)
    else:
        form = CDPForm(solicitud)

    renglones_disponibles = form.fields['renglon'].queryset

    return render(
        request,
        'scompras/cdp_form.html',
        {
            'form': form,
            'solicitud': solicitud,
        'renglones_disponibles': renglones_disponibles,
        },
    )


@login_required
@grupo_requerido('Administrador')
def ejecutar_cdp(request, cdp_id):
    cdp = get_object_or_404(
        CDP.objects.select_related('solicitud', 'renglon', 'renglon__presupuesto_anual'), pk=cdp_id
    )

    presupuesto_activo = PresupuestoAnual.presupuesto_activo()
    if not presupuesto_activo:
        messages.error(request, 'No hay presupuesto activo. Active un presupuesto anual antes de ejecutar un CDP.')
        return redirect('scompras:detalle_solicitud', pk=cdp.solicitud_id)
    if cdp.renglon.presupuesto_anual_id != presupuesto_activo.id:
        messages.error(request, 'Solo se pueden ejecutar CDP del presupuesto activo.')
        return redirect('scompras:detalle_solicitud', pk=cdp.solicitud_id)

    if cdp.estado != CDP.Estado.RESERVADO or hasattr(cdp, 'cdo'):
        messages.error(request, 'El CDP no está en estado Reservado o ya fue ejecutado.')
        return redirect('scompras:detalle_solicitud', pk=cdp.solicitud_id)

    if request.method == 'POST':
        form = EjecutarCDPForm(cdp, request.POST)
        if form.is_valid():
            try:
                form.save()
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, 'CDP ejecutado y CDO generado correctamente.')
                return redirect('scompras:detalle_solicitud', pk=cdp.solicitud_id)
    else:
        form = EjecutarCDPForm(cdp)

    return render(
        request,
        'scompras/cdo_form.html',
        {
            'form': form,
            'cdp': cdp,
        },
    )


@login_required
@grupo_requerido('Administrador')
def liberar_cdp(request, cdp_id):
    cdp = get_object_or_404(
        CDP.objects.select_related('solicitud', 'renglon', 'renglon__presupuesto_anual'), pk=cdp_id
    )

    presupuesto_activo = PresupuestoAnual.presupuesto_activo()
    if not presupuesto_activo:
        messages.error(request, 'No hay presupuesto activo. Active un presupuesto anual antes de liberar un CDP.')
        return redirect('scompras:detalle_solicitud', pk=cdp.solicitud_id)
    if cdp.renglon.presupuesto_anual_id != presupuesto_activo.id:
        messages.error(request, 'Solo se pueden liberar CDP del presupuesto activo.')
        return redirect('scompras:detalle_solicitud', pk=cdp.solicitud_id)

    if cdp.estado != CDP.Estado.RESERVADO:
        messages.error(request, 'Solo los CDP en estado Reservado pueden liberarse.')
        return redirect('scompras:detalle_solicitud', pk=cdp.solicitud_id)

    # Contexto ampliado de la solicitud y sus CDP para dar trazabilidad al usuario
    cdps_solicitud = (
        cdp.solicitud.cdps.select_related('renglon', 'renglon__presupuesto_anual')
        .annotate(
            monto_reservado_renglon=F('renglon__monto_reservado'),
            monto_disponible_renglon=F('renglon__monto_inicial')
            + F('renglon__monto_modificado')
            - F('renglon__monto_reservado')
            - F('renglon__monto_ejecutado'),
        )
        .order_by('id')
    )
    cdps_reservados = [c for c in cdps_solicitud if c.estado == CDP.Estado.RESERVADO]
    cdps_ejecutados = [c for c in cdps_solicitud if c.estado == CDP.Estado.EJECUTADO]
    cdps_liberados = [c for c in cdps_solicitud if c.estado == CDP.Estado.LIBERADO]

    totales_solicitud = cdps_solicitud.aggregate(
        total_reservado=Coalesce(Sum('monto', filter=Q(estado=CDP.Estado.RESERVADO)), Decimal('0.00')),
        total_ejecutado=Coalesce(Sum('monto', filter=Q(estado=CDP.Estado.EJECUTADO)), Decimal('0.00')),
    )

    if request.method == 'POST':
        form = LiberarCDPForm(cdp, request.POST)
        if form.is_valid():
            try:
                form.save()
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, 'Reserva liberada y presupuesto devuelto correctamente.')
                return redirect('scompras:detalle_solicitud', pk=cdp.solicitud_id)
    else:
        form = LiberarCDPForm(cdp)

    return render(
        request,
        'scompras/cdp_liberar.html',
        {
            'form': form,
            'cdp': cdp,
            'cdps_solicitud': cdps_solicitud,
            'cdps_reservados': cdps_reservados,
            'cdps_ejecutados': cdps_ejecutados,
            'cdps_liberados': cdps_liberados,
            'totales_solicitud': totales_solicitud,
        },
    )


@login_required
@grupo_requerido('Administrador')
def liberar_cdps_solicitud(request, solicitud_id):
    solicitud = get_object_or_404(SolicitudCompra, pk=solicitud_id)
    presupuesto_activo = PresupuestoAnual.presupuesto_activo()

    if not presupuesto_activo:
        messages.error(request, 'No hay presupuesto activo. Active un presupuesto anual antes de liberar CDP.')
        return redirect('scompras:detalle_solicitud', pk=solicitud.id)

    cdps_solicitud = solicitud.cdps.select_related('renglon', 'renglon__presupuesto_anual').order_by('id')
    cdps_ejecutados = cdps_solicitud.filter(estado=CDP.Estado.EJECUTADO)
    cdps_reservados = cdps_solicitud.filter(estado=CDP.Estado.RESERVADO)

    if cdps_ejecutados.exists():
        messages.error(request, 'La solicitud tiene CDP ejecutados; no es posible liberar todos en bloque.')
        return redirect('scompras:detalle_solicitud', pk=solicitud.id)

    if not cdps_reservados.exists():
        messages.info(request, 'La solicitud no tiene CDP en estado Reservado para liberar.')
        return redirect('scompras:detalle_solicitud', pk=solicitud.id)

    totales_solicitud = cdps_solicitud.aggregate(
        total_reservado=Coalesce(Sum('monto', filter=Q(estado=CDP.Estado.RESERVADO)), Decimal('0.00')),
        total_ejecutado=Coalesce(Sum('monto', filter=Q(estado=CDP.Estado.EJECUTADO)), Decimal('0.00')),
    )

    if request.method == 'POST':
        form = LiberarCDPSolicitudForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    for cdp in cdps_reservados.select_for_update():
                        cdp.liberar()
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, 'Todos los CDP reservados de la solicitud fueron liberados correctamente.')
                return redirect('scompras:detalle_solicitud', pk=solicitud.id)
    else:
        form = LiberarCDPSolicitudForm()

    return render(
        request,
        'scompras/cdp_liberar_todos.html',
        {
            'solicitud': solicitud,
            'form': form,
            'cdps_reservados': cdps_reservados,
            'totales_solicitud': totales_solicitud,
            'presupuesto_activo': presupuesto_activo,
        },
    )


from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.db.models import Count

@receiver(pre_save, sender=SolicitudCompra)
def generar_codigo_correlativo(sender, instance, **kwargs):
    # Solo generar el correlativo en creación o si quedó vacío, nunca en edición.
    if instance.pk and instance.codigo_correlativo:
        return
    # Asegurarse de que 'fecha_solicitud' esté definida antes de acceder al año
    if not instance.fecha_solicitud:
        return  # Si no hay fecha, no generar el código

    año = instance.fecha_solicitud.year

    # Obtener la abreviatura del departamento y sección
    dept_abrev = instance.seccion.departamento.abreviatura if instance.seccion else "GEN"
    secc_abrev = instance.seccion.abreviatura if instance.seccion else None

    # Contar solicitudes existentes en esa sección y año
    if instance.seccion:
        count = SolicitudCompra.objects.filter(
            seccion=instance.seccion,
            fecha_solicitud__year=año
        ).exclude(id=instance.id).count() + 1
    else:
        # Si no hay sección, contar solicitudes sin sección en ese año
        count = SolicitudCompra.objects.filter(
            seccion__isnull=True,
            usuario__usuario_departamento__departamento=instance.usuario.usuario_departamento_set.first().departamento,
            fecha_solicitud__year=año
        ).exclude(id=instance.id).count() + 1

    # Generar el código correlativo
    if secc_abrev and secc_abrev != dept_abrev:
        # Si la sección tiene una abreviatura diferente al departamento, incluir la abreviatura de la sección
        instance.codigo_correlativo = f'UPCV-{dept_abrev}-{secc_abrev}-{count:03d}-{año}'
    else:
        # Si la sección es igual al departamento o no existe sección, solo usar la abreviatura del departamento
        instance.codigo_correlativo = f'UPCV-{dept_abrev}-{count:03d}-{año}'


@require_POST
def eliminar_detalle_solicitud(request, detalle_id):
    """
    Elimina un InsumoSolicitud (detalle de insumo) de una solicitud de compra.
    """
    try:
        # Usamos InsumoSolicitud en lugar de DetalleSolicitud
        detalle = get_object_or_404(InsumoSolicitud, pk=detalle_id)
        
        # Lógica de eliminación
        detalle.delete()

        return JsonResponse({'success': True})
    
    # Asegúrate de atrapar la excepción correcta (InsumoSolicitud.DoesNotExist)
    except InsumoSolicitud.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'El insumo no existe.'}, status=404)
    
    except Exception as e:
        print("ERROR EN LA VISTA DE ELIMINACIÓN:", e) 
        return JsonResponse({'success': False, 'error': str(e)}, status=500)



from django.views.decorators.http import require_POST

@require_POST
def eliminar_servicio_solicitud(request, servicio_id):
    try:
        servicio = ServicioSolicitud.objects.get(id=servicio_id)
        servicio.delete()
        return JsonResponse({"success": True})
    except ServicioSolicitud.DoesNotExist:
        return JsonResponse({"success": False, "error": "Servicio no encontrado"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


def _es_peticion_ajax(request):
    return (
        request.headers.get("x-requested-with") == "XMLHttpRequest"
        or request.accepts("application/json")
    )


def _usuario_puede_editar(request):
    user = request.user
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name__in=['Administrador', 'scompras']).exists()


def _respuesta_sin_permiso(request, mensaje):
    if _es_peticion_ajax(request):
        return JsonResponse({'success': False, 'error': mensaje}, status=403)
    return redirect(reverse('scompras:acceso_denegado'))


def _respuesta_no_autenticado(request):
    if _es_peticion_ajax(request):
        return JsonResponse({'success': False, 'error': 'Debe iniciar sesión.'}, status=403)
    return redirect_to_login(request.get_full_path())


@require_POST
def actualizar_caracteristica_insumo(request, detalle_id):
    if not request.user.is_authenticated:
        return _respuesta_no_autenticado(request)
    if not _usuario_puede_editar(request):
        return _respuesta_sin_permiso(request, 'No tiene permisos para editar.')
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Solicitud inválida.'})
    else:
        data = request.POST

    caracteristica_especial = data.get('caracteristica_especial', '')
    if caracteristica_especial is None:
        caracteristica_especial = ''
    caracteristica_especial = caracteristica_especial.strip()

    if len(caracteristica_especial) > 1000:
        return JsonResponse({'success': False, 'error': 'La característica especial supera el máximo permitido.'})

    try:
        detalle = InsumoSolicitud.objects.select_related('solicitud').get(id=detalle_id)
        solicitud = detalle.solicitud
        if solicitud.estado not in ['Creada', 'Finalizada']:
            return JsonResponse(
                {'success': False, 'error': 'Solo se permite editar en estado Creada o Finalizada.'}
            )
        detalle.caracteristica_especial = caracteristica_especial
        detalle.save(update_fields=['caracteristica_especial'])
    except InsumoSolicitud.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Registro no encontrado.'})
    except ValidationError as exc:
        mensaje = exc.messages[0] if hasattr(exc, "messages") else str(exc)
        return JsonResponse({'success': False, 'error': mensaje})
    except Exception as exc:
        return JsonResponse({'success': False, 'error': str(exc)})

    return JsonResponse(
        {'success': True, 'caracteristica_especial': caracteristica_especial}
    )


@require_POST
def actualizar_caracteristica_servicio(request, servicio_id):
    if not request.user.is_authenticated:
        return _respuesta_no_autenticado(request)
    if not _usuario_puede_editar(request):
        return _respuesta_sin_permiso(request, 'No tiene permisos para editar.')
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Solicitud inválida.'})
    else:
        data = request.POST

    caracteristica_especial = data.get('caracteristica_especial', '')
    if caracteristica_especial is None:
        caracteristica_especial = ''
    caracteristica_especial = caracteristica_especial.strip()

    if len(caracteristica_especial) > 1000:
        return JsonResponse({'success': False, 'error': 'La característica especial supera el máximo permitido.'})

    try:
        servicio_solicitud = ServicioSolicitud.objects.select_related('solicitud').get(id=servicio_id)
        solicitud = servicio_solicitud.solicitud
        if solicitud.estado not in ['Creada', 'Finalizada']:
            return JsonResponse(
                {'success': False, 'error': 'Solo se permite editar en estado Creada o Finalizada.'}
            )
        servicio_solicitud.caracteristica_especial = caracteristica_especial
        servicio_solicitud.save(update_fields=['caracteristica_especial'])
    except ServicioSolicitud.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Registro no encontrado.'})
    except ValidationError as exc:
        mensaje = exc.messages[0] if hasattr(exc, "messages") else str(exc)
        return JsonResponse({'success': False, 'error': mensaje})
    except Exception as exc:
        return JsonResponse({'success': False, 'error': str(exc)})

    return JsonResponse(
        {'success': True, 'caracteristica_especial': caracteristica_especial}
    )


@require_POST
def actualizar_caracteristica_especial(request):
    if not request.user.is_authenticated:
        return _respuesta_no_autenticado(request)
    if not _usuario_puede_editar(request):
        return _respuesta_sin_permiso(request, 'No tiene permisos para editar.')
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Solicitud inválida.'})
    else:
        data = request.POST

    tipo = data.get('tipo')
    registro_id = data.get('id')
    if not tipo or not registro_id:
        return JsonResponse({'success': False, 'error': 'Parámetros incompletos.'})

    if tipo == 'insumo':
        return actualizar_caracteristica_insumo(request, registro_id)
    if tipo == 'servicio':
        return actualizar_caracteristica_servicio(request, registro_id)
    return JsonResponse({'success': False, 'error': 'Tipo inválido.'})


@require_POST
def agregar_insumo_solicitud(request):
    solicitud_id = request.POST.get('solicitud_id')
    codigo_presentacion = request.POST.get('codigo_presentacion', '').strip()
    cantidad = request.POST.get('cantidad')
    caracteristica = request.POST.get('caracteristica', '').strip()
    renglon = request.POST.get('renglon', '').strip()  # <-- Nuevo

    try:
        solicitud = SolicitudCompra.objects.get(id=solicitud_id)

        insumos = Insumo.objects.filter(codigo_presentacion__iexact=codigo_presentacion)
        if not insumos.exists():
            return JsonResponse({'success': False, 'error': 'Insumo no encontrado por código de presentación.'})

        insumo = insumos.first()

        if InsumoSolicitud.objects.filter(solicitud=solicitud, insumo=insumo).exists():
            return JsonResponse({'success': False, 'error': 'Este insumo ya está agregado.'})

        try:
            cantidad = int(cantidad)
            if cantidad <= 0:
                cantidad = 1
        except (TypeError, ValueError):
            cantidad = 1

        insumo_solicitud = InsumoSolicitud.objects.create(
            solicitud=solicitud,
            insumo=insumo,
            cantidad=cantidad,
            caracteristica_especial=caracteristica,
            renglon=renglon
        )

        detalle_id = insumo_solicitud.id 

        insumo_data = {
            'codigo_insumo': insumo.codigo_insumo,
            'nombre': insumo.nombre,
            'caracteristicas': insumo.caracteristicas or '-',
            'caracteristica_especial': caracteristica,
            'nombre_presentacion': insumo.nombre_presentacion,
            'cantidad_unidad_presentacion': insumo.cantidad_unidad_presentacion,
            'codigo_presentacion': insumo.codigo_presentacion,
            'cantidad': insumo_solicitud.cantidad,
            'renglon': insumo_solicitud.renglon,

        }

        return JsonResponse({'success': True, 'insumo': insumo_data, 'detalle_id': detalle_id})

    except SolicitudCompra.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Solicitud no encontrada.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})



def detalle_solicitud(request, solicitud_id):
    solicitud = SolicitudCompra.objects.get(id=solicitud_id)
    detalles = InsumoSolicitud.objects.filter(solicitud=solicitud)
    servicios = ServicioSolicitud.objects.filter(solicitud=solicitud)  # 👈 ESTA LÍNEA ES CLAVE
    productos = Producto.objects.filter(activo=True)
    subproductos = Subproducto.objects.filter(activo=True)

    return render(request, 'scompras/detalle_solicitud.html', {
        'solicitud': solicitud,
        'detalles': detalles,
        'productos': productos,
        'subproductos': subproductos,
        'servicios': servicios,
        'puede_editar_caracteristica': solicitud.estado in ['Creada', 'Finalizada'],
    })

def obtener_subproductos(request, producto_id):
    subproductos = Subproducto.objects.filter(producto_id=producto_id, activo=True)
    data = [{'id': s.id, 'nombre': s.nombre} for s in subproductos]
    return JsonResponse({'subproductos': data})


@require_POST
def editar_solicitud(request):
    try:
        solicitud = SolicitudCompra.objects.get(id=request.POST.get('solicitud_id'))
    except SolicitudCompra.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Solicitud no encontrada.'})

    form = SolicitudCompraForm(request.POST, instance=solicitud)

    if form.is_valid():
        try:
            solicitud_actualizada = form.save(commit=False)
            # Preservar el correlativo original en edición para evitar regeneración.
            solicitud_actualizada.codigo_correlativo = solicitud.codigo_correlativo
            solicitud_actualizada.save()
        except IntegrityError:
            return JsonResponse(
                {'success': False, 'error': 'Ya existe una solicitud con ese correlativo.'}
            )
        except ValidationError as exc:
            errores = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            return JsonResponse({'success': False, 'errors': errores})
        return JsonResponse({'success': True})

    return JsonResponse({'success': False, 'errors': form.errors})

@login_required
@csrf_exempt
def finalizar_solicitud(request):
    if request.method == "POST":
        try:
            # Cargar los datos JSON del cuerpo de la solicitud
            data = json.loads(request.body)
            solicitud_id = data.get("solicitud_id")

            if not solicitud_id:
                return JsonResponse({"success": False, "error": "ID de solicitud no proporcionado"})

            # Obtener la solicitud con el ID proporcionado, si no existe, devolver un error 404
            solicitud = get_object_or_404(SolicitudCompra, id=solicitud_id)

            # Verificar si la solicitud tiene un estado válido para ser finalizada
            if solicitud.estado != 'Creada':
                return JsonResponse({"success": False, "error": "La solicitud solo puede finalizarse desde estado 'Creada'."})

            # Actualizar el estado a "Finalizada"
            solicitud.estado = "Finalizada"
            # Guardar solo el campo 'estado' sin afectar otros campos como el 'codigo_correlativo'
            solicitud.save(update_fields=['estado'])

            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Método no permitido"})


@login_required
@csrf_exempt
def rechazar_solicitud(request):
    if request.method == "POST":
        try:
            if not (
                request.user.is_superuser
                or request.user.groups.filter(name__in=['Administrador', 'scompras']).exists()
            ):
                return JsonResponse({"success": False, "error": "No tiene permisos para rechazar la solicitud."}, status=403)
            # Cargar los datos JSON del cuerpo de la solicitud
            data = json.loads(request.body)
            solicitud_id = data.get("solicitud_id")

            if not solicitud_id:
                return JsonResponse({"success": False, "error": "ID de solicitud no proporcionado"})

            # Obtener la solicitud con el ID proporcionado, si no existe, devolver un error 404
            solicitud = get_object_or_404(SolicitudCompra, id=solicitud_id)

           # Verificar si la solicitud tiene un estado válido para ser rechazada
            if solicitud.estado not in ['Creada', 'Finalizada']:
                return JsonResponse({
                    "success": False,
                    "error": "La solicitud solo puede anularse desde estado 'Creada' o 'Finalizada'."
                })

            # Actualizar el estado a "Rechazada"
            solicitud.estado = "Rechazada"
            # Guardar solo el campo 'estado' sin afectar otros campos como el 'codigo_correlativo'
            solicitud.save(update_fields=['estado'])

            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Método no permitido"})


import os
from django.conf import settings
from django.contrib.staticfiles import finders

def link_callback(uri, rel):
    """
    Convierte URIs /static/.. y /media/.. en rutas absolutas del sistema de archivos
    para que xhtml2pdf pueda cargar imágenes.
    """
    # STATIC
    if uri.startswith(settings.STATIC_URL):
        path = uri.replace(settings.STATIC_URL, "")
        absolute_path = finders.find(path)
        if absolute_path:
            return absolute_path

    # MEDIA
    if uri.startswith(settings.MEDIA_URL):
        path = uri.replace(settings.MEDIA_URL, "")
        absolute_path = os.path.join(settings.MEDIA_ROOT, path)
        if os.path.isfile(absolute_path):
            return absolute_path

    # Si ya es un path absoluto y existe
    if os.path.isfile(uri):
        return uri

    return uri
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils.timezone import localtime
from django.template.defaultfilters import date as django_date
from xhtml2pdf import pisa

def generar_pdf_solicitud(request, solicitud_id):
    solicitud = get_object_or_404(SolicitudCompra, id=solicitud_id)

    # Igual que la DetailView (zona horaria + formato)
    solicitud.fecha_solicitud = localtime(solicitud.fecha_solicitud)
    fecha_solicitud_formateada = django_date(solicitud.fecha_solicitud, 'j \\d\\e F \\d\\e Y')

    detalles = (
        InsumoSolicitud.objects
        .filter(solicitud=solicitud)
        .select_related('insumo')
    )
    servicios = (
        ServicioSolicitud.objects
        .filter(solicitud=solicitud)
        .select_related('servicio')
    )

    institucion = Institucion.objects.first()

    context = {
        'solicitud': solicitud,
        'fecha_solicitud_formateada': fecha_solicitud_formateada,
        'detalles': detalles,
        'servicios': servicios,
        'institucion': institucion,
        # DEBUG opcional: te sirve para confirmar conteos en PDF
        # 'debug_detalles_count': detalles.count(),
        # 'debug_servicios_count': servicios.count(),
    }

    html = render_to_string('scompras/solicitud_pdf.html', context)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="solicitud.pdf"'

    pisa_status = pisa.CreatePDF(
        src=html,
        dest=response,
        encoding='utf-8',
        link_callback=link_callback  # ✅ CLAVE para static/media
    )

    if pisa_status.err:
        return HttpResponse("Error al generar el PDF", status=500)

    return response



@login_required
@grupo_requerido('Administrador', 'scompras')
def user_delete(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        user.delete()
        return redirect('scompras:user_create')  # Redirige a la misma página para mostrar la lista actualizada
    return render(request, 'scompras/user_confirm_delete.html', {'user': user})


def home(request):
    return render(request, 'scompras/login.html')

from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Q, Sum
import json


@login_required
@grupo_requerido('Administrador')
def dashboard_admin(request):
    """Dashboard consolidado para administradores con métricas institucionales."""

    solicitudes_estado = list(
        SolicitudCompra.objects.values('estado').annotate(total=Count('id')).order_by('estado')
    )

    solicitudes_anio = list(
        SolicitudCompra.objects
        .annotate(anio=ExtractYear('fecha_solicitud'))
        .values('anio')
        .annotate(total=Count('id'))
        .order_by('anio')
    )

    solicitudes_departamento = list(
        SolicitudCompra.objects
        .values('seccion__departamento__nombre')
        .annotate(total=Count('id'))
        .order_by('seccion__departamento__nombre')
    )

    presupuesto_activo = PresupuestoAnual.presupuesto_activo()
    presupuesto_resumen = None
    renglones_resumen = []

    if presupuesto_activo:
        renglones_qs = presupuesto_activo.renglones.select_related(
            'producto',
            'subproducto',
        ).annotate(
            disponible=ExpressionWrapper(
                F('monto_inicial') + F('monto_modificado') - (F('monto_reservado') + F('monto_ejecutado')),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )
        )
        totales = renglones_qs.aggregate(
            total_inicial=Sum('monto_inicial'),
            total_modificado=Sum('monto_modificado'),
            total_reservado=Sum('monto_reservado'),
            total_ejecutado=Sum('monto_ejecutado'),
        )

        total_inicial = totales.get('total_inicial') or Decimal('0.00')
        total_modificado = totales.get('total_modificado') or Decimal('0.00')
        total_reservado = totales.get('total_reservado') or Decimal('0.00')
        total_ejecutado = totales.get('total_ejecutado') or Decimal('0.00')
        total_disponible = (total_inicial + total_modificado) - (total_reservado + total_ejecutado)

        presupuesto_resumen = {
            'anio': presupuesto_activo.anio,
            'total_inicial': total_inicial,
            'total_modificado': total_modificado,
            'total_reservado': total_reservado,
            'total_ejecutado': total_ejecutado,
            'total_disponible': total_disponible,
        }

        renglones_resumen = [
            {
                'label': renglon.label_compacto,
                'monto_inicial': renglon.monto_inicial,
                'monto_modificado': renglon.monto_modificado,
                'monto_reservado': renglon.monto_reservado,
                'monto_ejecutado': renglon.monto_ejecutado,
                'disponible': renglon.disponible,
            }
            for renglon in renglones_qs
        ]

    context = {
        'solicitudes_estado_json': json.dumps(solicitudes_estado),
        'solicitudes_anio_json': json.dumps(solicitudes_anio),
        'solicitudes_departamento_json': json.dumps(solicitudes_departamento),
        'presupuesto_resumen': presupuesto_resumen,
        'renglones_resumen_json': json.dumps(renglones_resumen, default=str),
    }

    return render(request, 'scompras/dashboard_admin.html', context)


from django.db.models import Count
from django.db.models.functions import ExtractYear, ExtractMonth
from datetime import date

@login_required
@grupo_requerido('scompras')
def dashboard_scompras(request):
    """Dashboard operativo para usuarios de compras sin mostrar cifras presupuestarias."""

    asignacion = (
        UsuarioDepartamento.objects
        .filter(usuario=request.user)
        .select_related('seccion', 'departamento')
        .first()
    )

    if not asignacion or not asignacion.seccion:
        messages.warning(request, 'No tienes una sección asignada, no es posible calcular tus métricas.')
        return render(request, 'scompras/sin_seccion.html', {'mensaje': 'No tienes asignada ninguna sección.'})

    solicitudes_qs = SolicitudCompra.objects.filter(seccion=asignacion.seccion)
    total_solicitudes = solicitudes_qs.count()
    solicitudes_estado = list(
        solicitudes_qs.values('estado').annotate(total=Count('id')).order_by('estado')
    )

    context = {
        'seccion': asignacion.seccion,
        'departamento': asignacion.departamento,
        'total_solicitudes': total_solicitudes,
        'solicitudes_estado_json': json.dumps(solicitudes_estado),
    }

    return render(request, 'scompras/dashboard_scompras.html', context)



def acceso_denegado(request, exception=None):
    return render(request, 'scompras/403.html', status=403)

@login_required
def detalle_departamento(request, pk):
    departamento = get_object_or_404(Departamento, pk=pk)
    user = request.user

    # Verificar si es administrador
    es_admin = user.groups.filter(name='Administrador').exists()

    # Si NO es admin, verificar si tiene asignado el departamento
    if not es_admin and not UsuarioDepartamento.objects.filter(usuario=user, departamento=departamento).exists():
        return render(request, 'scompras/403.html', status=403)

    # Obtener todas las secciones del departamento
    secciones_departamento = Seccion.objects.filter(departamento=departamento)

    # Si es admin, tiene acceso a todas las secciones
    if es_admin:
        secciones_usuario_ids = list(secciones_departamento.values_list('id', flat=True))
    else:
        # Filtrar secciones según permisos
        secciones_usuario_ids = UsuarioDepartamento.objects.filter(
            usuario=user,
            departamento=departamento
        ).values_list('seccion_id', flat=True)

    if request.method == 'POST':
        form = SolicitudCompraForm(request.POST)
        if form.is_valid():
            solicitud = form.save(commit=False)
            solicitud.usuario = user

            # Validar acceso a la sección
            if solicitud.seccion.id not in secciones_usuario_ids:
                return render(request, 'scompras/403.html', status=403)

            solicitud.departamento = departamento
            solicitud.save()
            return redirect('scompras:detalle_departamento', pk=departamento.pk)
    else:
        form = SolicitudCompraForm()

    solicitudes = SolicitudCompra.objects.filter(
        seccion__departamento=departamento
    ).order_by('-fecha_solicitud')

    return render(request, 'scompras/detalle_departamento.html', {
        'departamento': departamento,
        'secciones': secciones_departamento,
        'secciones_usuario_ids': list(secciones_usuario_ids),
        'form': form,
        'solicitudes': solicitudes,
    })




def signout(request):
    logout(request)
    return redirect('scompras:signin')


def signin(request):  
    institucion = Institucion.objects.first()
    if request.method == 'GET':
        # Deberías instanciar el AuthenticationForm correctamente
        return render(request, 'scompras/login.html', {
            'form': AuthenticationForm(),
            'institucion': institucion,
        })
    else:
        # Se instancia AuthenticationForm con los datos del POST para mantener el estado
        form = AuthenticationForm(request, data=request.POST)
        
        if form.is_valid():
            # El método authenticate devuelve el usuario si es válido
            user = form.get_user()
            
            # Si el usuario es encontrado, se inicia sesión
            auth_login(request, user)
            
            # Ahora verificamos los grupos
            for g in user.groups.all():
                print(g.name)
                if g.name == 'Administrador':
                    return redirect('scompras:dahsboard')
                elif g.name == 'Departamento':
                    return redirect('scompras:crear_requerimiento')
                elif g.name == 'scompras':
                    return redirect('scompras:dashboard_usuario')
            # Si no se encuentra el grupo adecuado, se redirige a una página por defecto
            return redirect('scompras:signin')
        else:
            # Si el formulario no es válido, se retorna con el error
            return render(request, 'scompras/login.html', {
                'form': form,  # Pasamos el formulario con los errores
                'error': 'Usuario o contraseña incorrectos',
                'institucion': institucion,
            })





def descargar_insumos_excel(request):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Insumos"

    # Escribir encabezados
    encabezados = [
        'Renglón', 'Código de Insumo', 'Nombre', 'Características',
        'Nombre de Presentación', 'Cantidad y Unidad de Medida de Presentación',
        'Código de Presentación'
    ]
    ws.append(encabezados)

    # Escribir datos
    for insumo in Insumo.objects.all():
        ws.append([
            insumo.renglon,
            insumo.codigo_insumo,
            insumo.nombre,
            insumo.caracteristicas,
            insumo.nombre_presentacion,
            insumo.cantidad_unidad_presentacion,
            insumo.codigo_presentacion,

        ])

    # Preparar la respuesta HTTP
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename=insumos.xlsx'
    wb.save(response)
    return response

def insumos_disponibles_json(request):
    """
    Retorna la lista completa de insumos disponibles en formato JSON.
    Ideal para cargar una tabla simple o un DataTables sin server-side processing
    si la cantidad de datos es manejable (cientos o pocos miles).
    """
    insumos_queryset = Insumo.objects.all().order_by('nombre')
    
    data = []
    for insumo in insumos_queryset:
        data.append({
            'codigo_insumo': insumo.codigo_insumo,
            'nombre': insumo.nombre,
            'caracteristicas': insumo.caracteristicas if insumo.caracteristicas else '-',
            'nombre_presentacion': insumo.nombre_presentacion,
            'cantidad_unidad_presentacion': insumo.cantidad_unidad_presentacion,
            'codigo_presentacion': insumo.codigo_presentacion,
        })

    return JsonResponse({'data': data})

@csrf_exempt
def agregar_servicio_solicitud(request):
    if request.method == "POST":
        try:
            solicitud_id = request.POST.get("solicitud_id")
            cantidad = int(request.POST.get("cantidad"))
            concepto = request.POST.get("concepto")
            renglon = request.POST.get("renglon")
            unidad_medida = request.POST.get("unidad_medida")
            caracteristica_especial = request.POST.get("caracteristica_especial", "").strip()

            solicitud = SolicitudCompra.objects.get(id=solicitud_id)

            # Crear el servicio con todos los campos
            servicio = Servicio.objects.create(
                concepto=concepto.strip(),
                renglon=renglon.strip(),
                caracteristica_especial=caracteristica_especial or None,
                unidad_medida=unidad_medida.strip(),
            )

            ServicioSolicitud.objects.create(
                solicitud=solicitud,
                servicio=servicio,
                cantidad=cantidad,
                caracteristica_especial=caracteristica_especial or None,
            )

            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Método no permitido"})



@csrf_exempt
def insumos_json(request):
    draw = int(request.GET.get('draw', 1))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    search_value = request.GET.get('search[value]', '').strip()

    # 🔍 Filtros personalizados que vienen del frontend
    renglon = request.GET.get('renglon', '').strip()
    codigo_insumo = request.GET.get('codigo_insumo', '').strip()
    codigo_presentacion = request.GET.get('codigo_presentacion', '').strip()

    queryset = Insumo.objects.all()

    # 🔹 Filtros personalizados individuales
    if renglon:
        queryset = queryset.filter(renglon__icontains=renglon)
    if codigo_insumo:
        queryset = queryset.filter(codigo_insumo__icontains=codigo_insumo)
    if codigo_presentacion:
        queryset = queryset.filter(codigo_presentacion__icontains=codigo_presentacion)

    # 🔹 Búsqueda global de DataTables
    if search_value:
        queryset = queryset.filter(
            Q(renglon__icontains=search_value) |
            Q(codigo_insumo__icontains=search_value) |
            Q(nombre__icontains=search_value) |
            Q(caracteristicas__icontains=search_value) |
            Q(nombre_presentacion__icontains=search_value) |
            Q(cantidad_unidad_presentacion__icontains=search_value) |
            Q(codigo_presentacion__icontains=search_value)
        )

    total_count = Insumo.objects.count()
    filtered_count = queryset.count()
    queryset = queryset[start:start + length]

    data = [
        [
            insumo.renglon,
            insumo.codigo_insumo,
            insumo.nombre,
            insumo.caracteristicas,
            insumo.nombre_presentacion,
            insumo.cantidad_unidad_presentacion,
            insumo.codigo_presentacion
        ]
        for insumo in queryset
    ]

    return JsonResponse({
        'draw': draw,
        'recordsTotal': total_count,
        'recordsFiltered': filtered_count,
        'data': data
    })

def importar_excel(request):
    if request.method == 'POST':
        form = ExcelUploadForm(request.POST, request.FILES)
        fecha_form = FechaInsumoForm(request.POST)  # Formulario para la fecha

        if form.is_valid() and fecha_form.is_valid():  # Validar ambos formularios
            archivo = request.FILES['archivo_excel']
            df = pd.read_excel(archivo)

            # Eliminar los datos anteriores
            Insumo.objects.all().delete()

            # Crear una lista para guardar los objetos que se crearán
            nuevos_insumos = []

            for _, row in df.iterrows():
                insumo = Insumo(
                    renglon=row['RENGLÓN'],
                    codigo_insumo=row['CÓDIGO DE INSUMO'],
                    nombre=row['NOMBRE'],
                    caracteristicas=row['CARACTERÍSTICAS'],
                    nombre_presentacion=row['NOMBRE DE LA PRESENTACIÓN'],
                    cantidad_unidad_presentacion=row['CANTIDAD Y UNIDAD DE MEDIDA DE LA PRESENTACIÓN'],
                    codigo_presentacion=row['CÓDIGO DE PRESENTACIÓN'],
                    fecha_actualizacion=timezone.now()
                )
                nuevos_insumos.append(insumo)

            # Guardar todos los nuevos insumos de una vez
            Insumo.objects.bulk_create(nuevos_insumos)

            # Aquí es donde se captura la fecha del formulario de fecha
            fecha_in = fecha_form.save(commit=False)
            # La fecha capturada será la fecha proporcionada por el formulario (no la actual)
            fecha_in.fechainsumo = fecha_form.cleaned_data['fechainsumo']
            fecha_in.save()

            # Redirigir con un parámetro de sesión para pasar los últimos insumos
            request.session['importados'] = True
            return redirect('scompras:catalogo_insumos_view')
    else:
        form = ExcelUploadForm()
        fecha_form = FechaInsumoForm()  # Iniciar el formulario de fecha

    return render(request, 'scompras/importar_excel.html', {'form': form, 'fecha_form': fecha_form})



def catalogo_insumos_view(request):
    # Obtener los insumos
    insumos = Insumo.objects.all().order_by('-fecha_actualizacion')
    
    # Obtener la última fecha de insumo (último registro de fechainsumo)
    ultima_fecha_insumo = FechaInsumo.objects.last()  # Obtiene el último registro de la tabla fechainsumo
    
    return render(request, 'scompras/confirmacion.html', {
        'insumos': insumos,
        'ultima_fecha_insumo': ultima_fecha_insumo
    })
