"""Administración excepcional de solicitudes, separada del flujo operativo."""
import logging
from datetime import datetime
from functools import wraps

from django.core import signing
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import DatabaseError, transaction
from django.db.models import Case, CharField, F, Func, Q, Value, When
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect

from .form import SolicitudAdministracionForm
from .models import AuditoriaSolicitudCompra, CDP, SolicitudCompra
from .permissions import is_admin_group

logger = logging.getLogger(__name__)
SALT = 'scompras.solicitud.administracion.v2'
SIN_SECCION = '__sin_seccion__'
CAMPOS = ('institucion', 'departamento', 'seccion', 'numero', 'anio')
REGEX_CINCO = r'^[^-]+-[^-]+-[^-]+-[0-9]+-[0-9]{4}$'
REGEX_CUATRO = r'^[^-]+-[^-]+-[0-9]+-[0-9]{4}$'


def error(mensaje, status=400, code='invalid', **extra):
    return JsonResponse({'success': False, 'error': mensaje, 'code': code, **extra}, status=status)


def protegido(method='GET', pagina=False):
    def decorator(view):
        @wraps(view)
        @never_cache
        def wrapped(request, *args, **kwargs):
            # Intencionalmente no concede bypass por is_superuser ni otros grupos.
            if not is_admin_group(request.user):
                if pagina:
                    return render(request, 'scompras/403.html', status=403)
                return error('Acceso exclusivo para el grupo Administrador.', 403, 'forbidden')
            if request.method != method:
                response = error('Método no permitido.', 405, 'method_not_allowed')
                response['Allow'] = method
                return response
            try:
                return view(request, *args, **kwargs)
            except DatabaseError:
                logger.exception('Error de base de datos en administración de solicitudes')
                return error('No fue posible consultar la base de datos. Intente nuevamente.', 503, 'database_error')
        return wrapped
    return decorator


def correlativos():
    """Split en PostgreSQL, sólo tras validar el formato; nunca cambia códigos."""
    def parte(n):
        return Func(F('codigo_correlativo'), Value('-'), Value(n), function='split_part', output_field=CharField())

    return SolicitudCompra.objects.filter(
        Q(codigo_correlativo__regex=REGEX_CINCO) | Q(codigo_correlativo__regex=REGEX_CUATRO)
    ).annotate(
        componente_institucion=parte(1), componente_departamento=parte(2),
        componente_seccion=Case(When(codigo_correlativo__regex=REGEX_CINCO, then=parte(3)), default=Value(SIN_SECCION)),
        componente_numero=Case(When(codigo_correlativo__regex=REGEX_CINCO, then=parte(4)), default=parte(3)),
        componente_anio=Case(When(codigo_correlativo__regex=REGEX_CINCO, then=parte(5)), default=parte(4)),
    )


def filtrados(params, nivel):
    qs = correlativos()
    for campo in CAMPOS[:nivel]:
        valor = params.get(campo, '')
        if not valor or len(valor) > 50:
            raise ValueError('Complete las selecciones anteriores.')
        qs = qs.filter(**{f'componente_{campo}': valor})
    return qs


def auditoria(solicitud):
    return AuditoriaSolicitudCompra.objects.filter(solicitud_id=solicitud.pk)


def version(solicitud):
    return {
        'id': solicitud.pk, 'fecha': solicitud.fecha_solicitud.isoformat(),
        'estado': solicitud.estado, 'correlativo': solicitud.codigo_correlativo,
        'auditoria': auditoria(solicitud).order_by('-pk').values_list('pk', flat=True).first(),
    }


def estados_permitidos(solicitud):
    # Corrección administrativa explícita: estados del modelo, sin efectos operativos.
    permitidos = {valor for valor, _ in SolicitudCompra.ESTADOS}
    motivo = ''
    if solicitud.cdps.filter(estado__in=[CDP.Estado.RESERVADO, CDP.Estado.EJECUTADO]).exists():
        permitidos.clear()
        motivo = 'El estado requiere gestionar primero los CDP reservados o ejecutados por el flujo operativo.'
    if solicitud.pasos_estado.filter(completado=True).exists():
        permitidos.clear()
        motivo = 'Existen pasos completados. Gestione el estado desde el proceso operativo.'
    permitidos.add(solicitud.estado)
    return [{'value': valor, 'label': etiqueta} for valor, etiqueta in SolicitudCompra.ESTADOS if valor in permitidos], motivo


def detalle_data(solicitud):
    estados, motivo = estados_permitidos(solicitud)
    fecha = timezone.localtime(solicitud.fecha_solicitud)
    return {
        'id': solicitud.pk, 'correlativo': solicitud.codigo_correlativo,
        'fecha_solicitud': fecha.date().isoformat(), 'fecha_hora': fecha.isoformat(),
        'estado': solicitud.estado, 'estado_label': solicitud.get_estado_display(),
        'estado_badge': {'Creada': 'bg-primary', 'Finalizada': 'bg-success', 'Rechazada': 'bg-danger'}.get(solicitud.estado, 'bg-secondary'), 'usuario': solicitud.usuario.get_full_name() or solicitud.usuario.get_username(),
        'departamento': solicitud.seccion.departamento.nombre, 'seccion': solicitud.seccion.nombre,
        'prioridad': solicitud.get_prioridad_display(), 'descripcion': solicitud.descripcion,
        'estados_permitidos': estados, 'restriccion_estado': motivo,
        'version': signing.dumps(version(solicitud), salt=SALT, compress=True),
        'insumos': [{
            'nombre': d.insumo.nombre, 'codigo': d.insumo.codigo_insumo, 'cantidad': d.cantidad,
            'caracteristicas': d.insumo.caracteristicas or '', 'especiales': d.caracteristica_especial or '',
            'presentacion': d.insumo.nombre_presentacion,
        } for d in solicitud.insumos_solicitud.all()],
        'servicios': [{
            'nombre': d.nombre_override or d.servicio.concepto, 'cantidad': d.cantidad,
            'caracteristicas': d.caracteristica_especial or d.servicio.caracteristica_especial or '',
            'observacion': d.observacion or '',
        } for d in solicitud.servicios_solicitud.all()],
    }


def solicitudes_detalle():
    from django.db.models import Prefetch
    from .models import InsumoSolicitud, ServicioSolicitud
    return SolicitudCompra.objects.select_related('usuario', 'seccion__departamento').prefetch_related(
        Prefetch('insumos_solicitud', queryset=InsumoSolicitud.objects.select_related('insumo').order_by('pk')),
        Prefetch('servicios_solicitud', queryset=ServicioSolicitud.objects.select_related('servicio').order_by('pk')),
    )


@protegido(pagina=True)
def pagina(request):
    return render(request, 'scompras/administracion_solicitudes.html')


@protegido()
def opciones(request):
    campo = request.GET.get('nivel', 'institucion')
    if campo not in CAMPOS:
        return error('Selector no válido.')
    try:
        qs = filtrados(request.GET, CAMPOS.index(campo))
    except ValueError as exc:
        return error(str(exc))
    valores = list(qs.order_by(f'componente_{campo}').values_list(f'componente_{campo}', flat=True).distinct())
    valores.sort(key=(lambda x: (int(x), x)) if campo in ('numero', 'anio') else str)
    data = {'success': True, 'opciones': [
        {'value': v, 'label': 'Sin componente de sección' if campo == 'seccion' and v == SIN_SECCION else v}
        for v in valores
    ]}
    if campo == 'institucion':
        data['historicos'] = SolicitudCompra.objects.exclude(
            Q(codigo_correlativo__regex=REGEX_CINCO) | Q(codigo_correlativo__regex=REGEX_CUATRO)
        ).exclude(codigo_correlativo__isnull=True).exclude(codigo_correlativo='').count()
    return JsonResponse(data)


@protegido()
def detalle(request):
    historico = request.GET.get('historico')
    if historico is not None:
        if not historico or len(historico) > 50:
            return error('Indique un correlativo completo de hasta 50 caracteres.')
        ids = SolicitudCompra.objects.filter(codigo_correlativo=historico).values_list('pk', flat=True)
    else:
        try:
            ids = filtrados(request.GET, len(CAMPOS)).values_list('pk', flat=True)
        except ValueError as exc:
            return error(str(exc))
    candidatos = list(ids[:2])
    if not candidatos:
        return error('No existe una solicitud con esa combinación.', 404, 'not_found')
    if len(candidatos) != 1:
        return error('El correlativo es ambiguo; no se seleccionó ninguna solicitud.', 409, 'ambiguous')
    solicitud = solicitudes_detalle().filter(pk=candidatos[0]).first()
    if solicitud is None:
        return error('La solicitud ya no existe.', 404, 'not_found')
    return JsonResponse({'success': True, 'solicitud': detalle_data(solicitud)})


@protegido()
def historial(request, pk):
    solicitud = SolicitudCompra.objects.filter(pk=pk).first()
    if solicitud is None:
        return error('Solicitud no encontrada.', 404, 'not_found')
    try:
        page = Paginator(auditoria(solicitud).select_related('usuario').order_by('-fecha', '-pk'), 10).page(request.GET.get('page', 1))
    except (EmptyPage, PageNotAnInteger, ValueError):
        return error('Página de historial no válida.')
    # El historial sólo expone entradas creadas por esta operación.
    registros = []
    for registro in page:
        cambios = [
            ('Fecha de solicitud', registro.fecha_anterior.isoformat(), registro.fecha_nueva.isoformat()),
            ('Estado', registro.estado_anterior, registro.estado_nuevo),
        ]
        for campo, anterior, nuevo in cambios:
            if anterior != nuevo:
                registros.append({
                    'fecha': timezone.localtime(registro.fecha).isoformat(),
                    'usuario': registro.usuario.get_full_name() or registro.usuario.get_username(),
                    'campo': campo, 'anterior': anterior, 'nuevo': nuevo,
                })
    return JsonResponse({'success': True, 'registros': registros, 'page': page.number, 'pages': page.paginator.num_pages})


@protegido('POST')
@csrf_protect
def actualizar(request, pk):
    form = SolicitudAdministracionForm(request.POST)
    if not form.is_valid():
        return error('Revise la fecha, el estado y la versión de la solicitud.', fields=form.errors.get_json_data())
    try:
        esperada = signing.loads(form.cleaned_data['version'], salt=SALT, max_age=3600)
    except signing.BadSignature:
        return error('La consulta venció o fue alterada. Consulte de nuevo la solicitud.', 409, 'stale')
    with transaction.atomic():
        solicitud = SolicitudCompra.objects.select_for_update().filter(pk=pk).first()
        if solicitud is None:
            return error('Solicitud no encontrada.', 404, 'not_found')
        if esperada != version(solicitud):
            return error('Otro usuario modificó la solicitud. Consulte sus datos actuales antes de guardar.', 409, 'stale')
        nueva_fecha, nuevo_estado = form.cleaned_data['fecha_solicitud'], form.cleaned_data['estado']
        local = timezone.localtime(solicitud.fecha_solicitud)
        cambios = []
        if nueva_fecha != local.date():
            cambios.append('fecha_solicitud')
        if nuevo_estado != solicitud.estado:
            permitidos, motivo = estados_permitidos(solicitud)
            if nuevo_estado not in {e['value'] for e in permitidos}:
                return error(motivo or 'Transición de estado no permitida por el flujo actual.', 409, 'transition_blocked')
            cambios.append('estado')
        if not cambios:
            return JsonResponse({'success': True, 'changed': False, 'message': 'No hay cambios para guardar.'})
        anterior_fecha, anterior_estado = solicitud.fecha_solicitud, solicitud.estado
        if 'fecha_solicitud' in cambios:
            solicitud.fecha_solicitud = timezone.make_aware(datetime.combine(nueva_fecha, local.time()), timezone.get_current_timezone())
        solicitud.estado = nuevo_estado
        # Un UPDATE acotado evita regenerar correlativos vacíos/históricos por pre_save.
        SolicitudCompra.objects.filter(pk=pk).update(**{campo: getattr(solicitud, campo) for campo in cambios})
        AuditoriaSolicitudCompra.objects.create(
            solicitud=solicitud, solicitud_pk=solicitud.pk, usuario=request.user,
            correlativo=solicitud.codigo_correlativo, fecha_anterior=anterior_fecha,
            fecha_nueva=solicitud.fecha_solicitud, estado_anterior=anterior_estado,
            estado_nuevo=solicitud.estado,
        )
    return JsonResponse({'success': True, 'changed': True, 'message': 'Cambios guardados correctamente.'})
