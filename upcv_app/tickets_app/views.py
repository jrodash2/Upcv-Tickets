
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout
from django.contrib.auth.forms import AuthenticationForm

from django.contrib.auth.models import Group, User

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Ticket
from .forms import TicketForm
from .forms import TickettecForm
from django.db.models import Case, When, IntegerField
from .forms import TicketForm
from .models import Oficina
from .forms import OficinaForm
from .models import TipoEquipo
from .forms import TipoEquipoForm
from .forms import UserForm

@login_required
def user_create(request):
    if request.method == 'POST':
        form = UserForm(request.POST)
        if form.is_valid():
            form.save()  # Guarda el usuario si el formulario es válido
            return redirect('tickets:user_create')  # Redirige a la misma página
    else:
        form = UserForm()

    users = User.objects.all()  # Obtener todos los usuarios
    return render(request, 'tickets/user_form.html', {'form': form, 'users': users})


@login_required
def user_delete(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        user.delete()
        return redirect('tickets:user_create')  # Redirige a la misma página para mostrar la lista actualizada
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
    tickets = Ticket.objects.all().annotate(
        estado_order=Case(
            When(estado='abierto', then=0),
            When(estado='en_proceso', then=1),
            When(estado='cerrado', then=2),
            When(estado='pendiente', then=3),
            output_field=IntegerField(),
        )
    ).order_by('estado_order', '-fecha_creacion')
    return render(request, 'tickets/tickets_dahsboard_adm.html', {'tickets': tickets})


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


