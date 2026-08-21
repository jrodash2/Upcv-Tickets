
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.utils import timezone
from django.contrib.auth.models import Group, User
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Ticket
from .forms import TicketForm
from .forms import TickettecForm
from django.db.models import Case, When, IntegerField
from .forms import TicketForm
from .models import Oficina
from .models import FechaInsumo
from .forms import OficinaForm
from .models import TipoEquipo
from .forms import TipoEquipoForm
from .forms import UserForm
from .forms import FechaInsumoForm
from openpyxl import Workbook
from django.http import JsonResponse
from django.db.models import Count
from django.db.models.functions import ExtractYear, TruncMonth, TruncWeek
from django.utils import timezone
import datetime
from django.http import HttpResponse
from django.db.models import Q
import pandas as pd
from .forms import ExcelUploadForm
from .models import Insumo # Cambia esto por tu modelo real
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

# tickets/views.py
from django.http import JsonResponse
from empleados_app.models import Empleado  # 👈 importante, viene de la otra app

def buscar_empleado_dpi(request):
    dpi = request.GET.get("dpi", "").strip()

    if not dpi:
        return JsonResponse({"error": "Debe proporcionar un DPI."}, status=400)

    try:
        empleado = Empleado.objects.get(dpi=dpi)
    except Empleado.DoesNotExist:
        return JsonResponse({"error": "Empleado no encontrado."}, status=404)

    username = (empleado.nombres.split()[0][0] + empleado.apellidos.replace(" ", "")).lower()

    return JsonResponse({
        "nombres": empleado.nombres,
        "apellidos": empleado.apellidos,
        "foto": empleado.imagen.url if empleado.imagen else None,
        "username": username
    })

def _obtener_anio(request):
    """Devuelve un año válido para filtros de dashboard y exportación."""
    anio_actual = timezone.now().year
    try:
        anio = int(request.GET.get('anio', anio_actual))
    except (TypeError, ValueError):
        return anio_actual
    return anio if 1900 <= anio <= anio_actual else anio_actual


def exportar_excel_tickets(request):
    anio = _obtener_anio(request)
    wb = Workbook()
    ws = wb.active
    ws.title = f"Tickets {anio}"

    # Encabezados
    ws.append([
        "ID", "Oficina", "Vía de Contacto", "Tipo de Equipo", "Problema",
        "Responsable", "Teléfono", "Correo", "Detalle del Problema",
        "Solución", "Técnico Asignado", "Estado", "Prioridad",
        "Fecha de Creación", "Fecha de Actualización"
    ])

    # Datos
    tickets = (
        Ticket.objects.filter(fecha_creacion__year=anio)
        .select_related('oficina', 'tipo_equipo', 'tecnico_asignado')
        .order_by('fecha_creacion')
    )
    for ticket in tickets:
        ws.append([
            ticket.id,
            ticket.oficina.nombre if ticket.oficina else "Sin oficina",
            ticket.via_contacto,
            ticket.tipo_equipo.nombre if ticket.tipo_equipo else "Sin tipo",
            ticket.problema,
            ticket.responsable,
            ticket.telefono,
            ticket.correo,
            ticket.detalle_problema,
            ticket.solucion_problema,
            ticket.tecnico_asignado.get_full_name() if ticket.tecnico_asignado else "No asignado",
            ticket.estado,
            ticket.prioridad,
            ticket.fecha_creacion.strftime('%Y-%m-%d %H:%M'),
            ticket.fecha_actualizacion.strftime('%Y-%m-%d %H:%M'),
        ])

    # Respuesta HTTP para descarga
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="tickets_upcv_{anio}.xlsx"'
    wb.save(response)
    return response

@login_required
def dashboard_view(request):
    """Dashboard anual, partiendo siempre del queryset permitido al usuario.

    El dashboard existente estaba disponible para cualquier usuario autenticado y
    mostraba todos los tickets. Se conserva exactamente ese alcance; centralizarlo
    aquí evita que una métrica futura omita accidentalmente el filtro de permisos.
    """
    tickets_permitidos = Ticket.objects.all()
    anio = _obtener_anio(request)

    anios_disponibles = list(
        tickets_permitidos.annotate(anio_ticket=ExtractYear('fecha_creacion'))
        .values_list('anio_ticket', flat=True).distinct().order_by('-anio_ticket')
    )
    if anio not in anios_disponibles:
        anios_disponibles.append(anio)
        anios_disponibles.sort(reverse=True)

    tickets_anio = tickets_permitidos.filter(fecha_creacion__year=anio)
    tickets_anio_anterior = tickets_permitidos.filter(fecha_creacion__year=anio - 1)
    estados = list(Ticket.ESTADO_CHOICES)

    def resumen(queryset):
        return queryset.aggregate(
            total=Count('id'),
            **{
                codigo: Count('id', filter=Q(estado=codigo))
                for codigo, _nombre in estados
            },
        )

    conteos = resumen(tickets_anio)
    conteos_anteriores = resumen(tickets_anio_anterior)

    def comparacion(actual, anterior):
        if anterior == 0:
            return {
                'tipo': 'neutral',
                'texto': 'Sin datos comparables' if actual == 0 else 'Sin tickets el año anterior',
            }
        variacion = ((actual - anterior) / anterior) * 100
        return {
            'tipo': 'up' if variacion > 0 else ('down' if variacion < 0 else 'neutral'),
            'texto': f'{abs(variacion):.1f}% respecto a {anio - 1}',
        }

    cards = [{
        'titulo': 'Total de tickets', 'valor': conteos['total'],
        'icono': 'activity', 'color': 'bg-dark',
        'comparacion': comparacion(conteos['total'], conteos_anteriores['total']),
    }]
    estilos_estado = {
        'abierto': ('people', 'bg-primary'),
        'en_proceso': ('tasks', 'bg-warning'),
        'cerrado': ('task-square', 'bg-success'),
        'pendiente': ('clock', 'bg-info'),
    }
    for codigo, nombre in estados:
        icono, color = estilos_estado.get(codigo, ('activity', 'bg-secondary'))
        cards.append({
            'titulo': nombre, 'valor': conteos[codigo], 'icono': icono, 'color': color,
            'comparacion': comparacion(conteos[codigo], conteos_anteriores[codigo]),
        })

    por_estado_db = dict(tickets_anio.values_list('estado').annotate(total=Count('id')))
    tickets_por_estado = [
        {'estado': nombre, 'total': por_estado_db.get(codigo, 0)}
        for codigo, nombre in estados
    ]
    por_mes_db = {
        fila['mes'].month: fila['total']
        for fila in tickets_anio.annotate(mes=TruncMonth('fecha_creacion'))
        .values('mes').annotate(total=Count('id')).order_by('mes')
    }
    meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
             'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    tickets_por_mes = [{'mes': nombre, 'total': por_mes_db.get(numero, 0)}
                       for numero, nombre in enumerate(meses, 1)]
    tickets_por_categoria = list(
        tickets_anio.values('tipo_equipo__nombre').annotate(total=Count('id'))
        .order_by('-total', 'tipo_equipo__nombre')
    )
    tickets_por_oficina = list(
        tickets_anio.values('oficina__nombre').annotate(total=Count('id'))
        .order_by('-total', 'oficina__nombre')[:10]
    )
    rendimiento_tecnicos = list(
        tickets_anio.filter(tecnico_asignado__isnull=False)
        .values('tecnico_asignado__username', 'tecnico_asignado__first_name',
                'tecnico_asignado__last_name')
        .annotate(
            asignados=Count('id'),
            abiertos=Count('id', filter=Q(estado='abierto')),
            cerrados=Count('id', filter=Q(estado='cerrado')),
            pendientes=Count('id', filter=Q(estado='pendiente')),
            en_proceso=Count('id', filter=Q(estado='en_proceso')),
        ).order_by('-asignados', 'tecnico_asignado__username')
    )
    ultimos_tickets = (
        tickets_anio.select_related('oficina', 'tipo_equipo', 'tecnico_asignado')
        .order_by('-fecha_creacion')[:10]
    )

    return render(request, 'tickets/dashboard.html', {
        'anio': anio, 'anio_anterior': anio - 1,
        'anios_disponibles': anios_disponibles, 'cards': cards,
        'total_tickets': conteos['total'], 'tickets_por_estado': tickets_por_estado,
        'tickets_por_mes': tickets_por_mes,
        'tickets_por_categoria': tickets_por_categoria,
        'tickets_por_oficina': tickets_por_oficina,
        'rendimiento_tecnicos': rendimiento_tecnicos,
        'ultimos_tickets': ultimos_tickets,
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


@csrf_exempt  # Si estás teniendo problemas con CSRF en peticiones Ajax, puedes usar esto temporalmente
def insumos_json(request):
    draw = int(request.GET.get('draw', 1))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    search_value = request.GET.get('search[value]', '').strip()

    queryset = Insumo.objects.all()

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

    data = []
    for insumo in queryset:
        data.append([
            insumo.renglon,
            insumo.codigo_insumo,
            insumo.nombre,
            insumo.caracteristicas,
            insumo.nombre_presentacion,
            insumo.cantidad_unidad_presentacion,
            insumo.codigo_presentacion
        ])

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
            return redirect('tickets:catalogo_insumos_view')
    else:
        form = ExcelUploadForm()
        fecha_form = FechaInsumoForm()  # Iniciar el formulario de fecha

    return render(request, 'tickets/importar_excel.html', {'form': form, 'fecha_form': fecha_form})



def catalogo_insumos_view(request):
    # Obtener los insumos
    insumos = Insumo.objects.all().order_by('-fecha_actualizacion')
    
    # Obtener la última fecha de insumo (último registro de fechainsumo)
    ultima_fecha_insumo = FechaInsumo.objects.last()  # Obtiene el último registro de la tabla fechainsumo
    
    return render(request, 'tickets/confirmacion.html', {
        'insumos': insumos,
        'ultima_fecha_insumo': ultima_fecha_insumo
    })

from django.contrib import messages

@login_required
def user_create(request):
    if request.method == 'POST':
        form = UserForm(request.POST)
        print("POST FORM:", form.__class__)

        if form.is_valid():
            form.save()
            messages.success(request, "Usuario creado exitosamente.")
            return redirect('tickets:user_create')
        else:
            print("ERRORES:", form.errors)  # 👈 Esto te mostrará si hay algo mal
            messages.error(request, "Corrige los errores del formulario.")
    else:
        form = UserForm()
        print("GET FORM:", form.__class__)

    users = User.objects.all()
    return render(request, 'tickets/user_form.html', {'form': form, 'users': users})

@login_required
def user_delete(request, user_id):
    user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        from empleados_app.models import Empleado
        
        # Desvincular empleados ANTES de borrar usuario
        Empleado.objects.filter(user=user).update(user=None)

        user.delete()
        return redirect('tickets:user_create')

    return render(request, 'tickets/user_confirm_delete.html', {'user': user})


@login_required
def oficina_create(request):
    if request.method == 'POST':
        form = OficinaForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('tickets:oficina_create')  # Redirige a la misma página para mostrar la lista actualizada
    else:
        form = OficinaForm()
    
    oficinas = Oficina.objects.all()  # Obtener todas las oficinas
    return render(request, 'tickets/oficina_form_adm.html', {'form': form, 'oficinas': oficinas})


@login_required
def tipo_equipo_create(request):
    if request.method == 'POST':
        form = TipoEquipoForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('tickets:tipo_equipo_create') 
    else:
        form = TipoEquipoForm()
    
    tipos_equipo = TipoEquipo.objects.all()  
    return render(request, 'tickets/tipo_equipo_form_adm.html', {'form': form, 'tipos_equipo': tipos_equipo})

@login_required
def tickets_dahsboard(request):
    tickets = Ticket.objects.filter(tecnico_asignado=request.user).annotate(
        estado_order=Case(
            When(estado='abierto', then=0),
            When(estado='en_proceso', then=1),
            When(estado='cerrado', then=2),
            When(estado='pendiente', then=3),
            output_field=IntegerField(),
        )
    ).order_by('estado_order', '-fecha_creacion')
    return render(request, 'tickets/tickets_dahsboard.html', {'tickets': tickets})



@login_required
def tickets_dahsboard_adm(request):
    # Obtener todos los tickets ordenados por estado
    tickets = Ticket.objects.all().annotate(
        estado_order=Case(
            When(estado='abierto', then=0),
            When(estado='en_proceso', then=1),
            When(estado='cerrado', then=2),
            When(estado='pendiente', then=3),
            output_field=IntegerField(),
        )
    ).order_by('estado_order', '-fecha_creacion')

    # Verificar el conteo de tickets
    print(f"Total de tickets encontrados: {tickets.count()}")

    # Estadísticas de tickets
    total_tickets = tickets.count()
    tickets_abiertos = tickets.filter(estado='abierto').count()
    tickets_cerrados = tickets.filter(estado='cerrado').count()
    tickets_en_proceso = tickets.filter(estado='en_proceso').count()
    tickets_pendientes = tickets.filter(estado='pendiente').count()

    tickets_alta_prioridad = tickets.filter(prioridad='alta').count()
    tickets_media_prioridad = tickets.filter(prioridad='media').count()
    tickets_baja_prioridad = tickets.filter(prioridad='baja').count()

    # Generar fechas para las semanas del mes actual
    today = timezone.now().date()
    first_day_of_month = today.replace(day=1)
    last_day_of_month = today.replace(day=28) + datetime.timedelta(days=4)  # Último día del mes

    weeks = []
    current_date = first_day_of_month

    while current_date <= last_day_of_month:
        sunday = current_date + datetime.timedelta(days=(6 - current_date.weekday()))
        weeks.append(sunday.strftime('%B %d, %Y'))
        current_date = sunday + datetime.timedelta(days=1)  # Avanzar al lunes de la siguiente semana

    # Obtener el conteo de tickets por semana (utilizando TruncWeek para truncar por semana)
    tickets_por_semana = tickets.annotate(week=TruncWeek('fecha_creacion')) \
        .filter(fecha_creacion__gte=first_day_of_month, fecha_creacion__lte=last_day_of_month) \
        .values('week') \
        .annotate(ticket_count=Count('id')) \
        .order_by('week')

    semanas = [ticket['week'].strftime('%B %d, %Y') for ticket in tickets_por_semana]
    cantidad_tickets = [ticket['ticket_count'] for ticket in tickets_por_semana]

    # Datos para los gráficos
    estado_labels = ['Abiertos', 'Cerrados', 'En Proceso', 'Pendientes']
    estado_data = [tickets_abiertos, tickets_cerrados, tickets_en_proceso, tickets_pendientes]

    prioridad_labels = ['Alta', 'Media', 'Baja']
    prioridad_data = [tickets_alta_prioridad, tickets_media_prioridad, tickets_baja_prioridad]

    context = {
        'total_tickets': total_tickets,
        'tickets_abiertos': tickets_abiertos,
        'tickets_cerrados': tickets_cerrados,
        'tickets_en_proceso': tickets_en_proceso,
        'tickets_pendientes': tickets_pendientes,
        'tickets_alta_prioridad': tickets_alta_prioridad,
        'tickets_media_prioridad': tickets_media_prioridad,
        'tickets_baja_prioridad': tickets_baja_prioridad,
        'estado_labels': estado_labels,
        'estado_data': estado_data,
        'prioridad_labels': prioridad_labels,
        'prioridad_data': prioridad_data,
        'semanas': semanas,
        'cantidad_tickets': cantidad_tickets,
        'tickets': tickets,  # Asegúrate de pasar los tickets a la plantilla
    }

    return render(request, 'tickets/tickets_dahsboard_adm.html', context)



@login_required
def tickets_abiertos(request):
    tickets = Ticket.objects.filter(tecnico_asignado=request.user, estado='abierto').annotate(
        estado_order=Case(
            When(estado='abierto', then=0),
            When(estado='en_proceso', then=1),
            When(estado='cerrado', then=2),
            When(estado='pendiente', then=3),
            output_field=IntegerField(),
        )
    ).order_by('estado_order', '-fecha_creacion')
    return render(request, 'tickets/tickets_abiertos.html', {'tickets': tickets})


@login_required
def tickets_abiertos_adm(request):
    tickets = Ticket.objects.filter(estado='abierto').annotate(
        estado_order=Case(
            When(estado='abierto', then=0),
            When(estado='en_proceso', then=1),
            When(estado='cerrado', then=2),
            When(estado='pendiente', then=3),
            output_field=IntegerField(),
        )
    ).order_by('estado_order', '-fecha_creacion')
    return render(request, 'tickets/tickets_abiertos_adm.html', {'tickets': tickets})

@login_required
def tickets_proceso(request):
    tickets = Ticket.objects.filter(tecnico_asignado=request.user, estado='en_proceso').annotate(
        estado_order=Case(
            When(estado='abierto', then=0),
            When(estado='en_proceso', then=1),
            When(estado='cerrado', then=2),
            When(estado='pendiente', then=3),
            output_field=IntegerField(),
        )
    ).order_by('estado_order', '-fecha_creacion')
    return render(request, 'tickets/tickets_proceso.html', {'tickets': tickets})


@login_required
def tickets_proceso_adm(request):
    tickets = Ticket.objects.filter(estado='en_proceso').annotate(
        estado_order=Case(
            When(estado='abierto', then=0),
            When(estado='en_proceso', then=1),
            When(estado='cerrado', then=2),
            When(estado='pendiente', then=3),
            output_field=IntegerField(),
        )
    ).order_by('estado_order', '-fecha_creacion')
    return render(request, 'tickets/tickets_proceso_adm.html', {'tickets': tickets})


@login_required
def tickets_cerrado_adm(request):
    tickets = Ticket.objects.filter(estado='cerrado').annotate(
        estado_order=Case(
            When(estado='abierto', then=0),
            When(estado='en_proceso', then=1),
            When(estado='cerrado', then=2),
            When(estado='pendiente', then=3),
            output_field=IntegerField(),
        )
    ).order_by('estado_order', '-fecha_creacion')
    return render(request, 'tickets/tickets_cerrado_adm.html', {'tickets': tickets})


@login_required
def tickets_cerrado(request):
    tickets = Ticket.objects.filter(tecnico_asignado=request.user, estado='cerrado').annotate(
        estado_order=Case(
            When(estado='abierto', then=0),
            When(estado='en_proceso', then=1),
            When(estado='cerrado', then=2),
            When(estado='pendiente', then=3),
            output_field=IntegerField(),
        )
    ).order_by('estado_order', '-fecha_creacion')
    return render(request, 'tickets/tickets_cerrado.html', {'tickets': tickets})



@login_required
def tickets_pendiente_adm(request):
    tickets = Ticket.objects.filter(estado='pendiente').annotate(
        estado_order=Case(
            When(estado='abierto', then=0),
            When(estado='en_proceso', then=1),
            When(estado='cerrado', then=2),
            When(estado='pendiente', then=3),
            output_field=IntegerField(),
        )
    ).order_by('estado_order', '-fecha_creacion')
    return render(request, 'tickets/tickets_pendiente_adm.html', {'tickets': tickets})



@login_required
def tickets_pendiente(request):
    tickets = Ticket.objects.filter(tecnico_asignado=request.user, estado='pendiente').annotate(
        estado_order=Case(
            When(estado='abierto', then=0),
            When(estado='en_proceso', then=1),
            When(estado='cerrado', then=2),
            When(estado='pendiente', then=3),
            output_field=IntegerField(),
        )
    ).order_by('estado_order', '-fecha_creacion')
    return render(request, 'tickets/tickets_pendiente.html', {'tickets': tickets})


@login_required
def ticket_detail(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    return render(request, 'tickets/ticket_detail.html', {'ticket': ticket})


@login_required
def ticket_detail_tec(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    return render(request, 'tickets/ticket_detail_tec.html', {'ticket': ticket})

@login_required
def ticket_update(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    if request.method == 'POST':
        form = TickettecForm(request.POST, instance=ticket)
        if form.is_valid():
            form.save()
            return redirect('tickets:tickets_dahsboard')
    else:
        form = TickettecForm(instance=ticket)
    return render(request, 'tickets/ticket_form.html', {'form': form, 'ticket': ticket})

@login_required
def update_adm(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    if request.method == 'POST':
        form = TicketForm(request.POST, instance=ticket)
        if form.is_valid():
            form.save()
            return redirect('tickets:tickets_dahsboard_adm')
    else:
        form = TicketForm(instance=ticket)
    return render(request, 'tickets/ticket_form_adm.html', {'form': form})

@login_required
def ticket_create(request):
    if request.method == 'POST':
        form = TicketForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('tickets:tickets_dahsboard')
    else:
        form = TicketForm()
    return render(request, 'tickets/ticket_form.html', {'form': form})


@login_required
def ticket_create_adm(request):
    if request.method == 'POST':
        form = TicketForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('tickets:tickets_dahsboard_adm')
    else:
        form = TicketForm()
    return render(request, 'tickets/ticket_form_adm.html', {'form': form})


@login_required 
def manuales(request):
    return render(request, 'tickets/tickets_manuales.html')

@login_required 
def manualesadm(request):
    return render(request, 'tickets/tickets_manualesadm.html')

@login_required
def user_manage(request, user_id=None):
    usuario = None

    if user_id:
        # ==== MODO EDICIÓN ====
        usuario = get_object_or_404(User, id=user_id)
        form = UserForm(request.POST or None, instance=usuario, edit=True)
    else:
        # ==== MODO CREACIÓN ====
        form = UserForm(request.POST or None, edit=False)

    if request.method == 'POST':
        if form.is_valid():
            user = form.save()

            messages.success(request, "Usuario guardado correctamente.")
            return redirect('tickets:user_manage')

    users = User.objects.all()
    return render(request, "tickets/user_form.html", {
        "form": form,
        "users": users,
    })
