from django.shortcuts import render, redirect, get_object_or_404
from .forms import EmpleadoForm, EmpleadoeditForm
from django.contrib.auth.models import User
from django.contrib import messages
from .models import Empleado
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, logout, login as auth_login  
from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm
from .models import ConfiguracionGeneral
from .forms import ConfiguracionGeneralForm
from django.urls import reverse


from PIL import Image
from io import BytesIO
from django.template.loader import render_to_string

from django.db.models.functions import ExtractYear
from django.db.models import Count

import qrcode

from django.http import HttpResponse
from django.core.files.base import ContentFile

def configuracion_general(request):
    configuracion, created = ConfiguracionGeneral.objects.get_or_create(id=1)  # Solo una configuración general
    if request.method == 'POST':
        form = ConfiguracionGeneralForm(request.POST, request.FILES, instance=configuracion)
        if form.is_valid():
            form.save()
            return redirect('empleados:configuracion_general')  # Redirige al formulario para ver los cambios
    else:
        form = ConfiguracionGeneralForm(instance=configuracion)
    
    return render(request, 'empleados/configuracion_general.html', {'form': form, 'configuracion': configuracion})

def home(request):
    return render(request, 'empleados/login.html')

@login_required 
def dahsboard(request):
    # Totales generales
    total_activos = Empleado.objects.filter(activo=True).count()
    total_inactivos = Empleado.objects.filter(activo=False).count()

    # Activos por año
    activos_por_anio = (
        Empleado.objects.filter(activo=True)
        .annotate(anio=ExtractYear('fecha_inicio'))
        .values('anio')
        .annotate(total=Count('id'))
        .order_by('anio')
    )

    datos_empleados = {
        'activos': total_activos,
        'inactivos': total_inactivos,
    }

    return render(request, 'empleados/dahsboard.html', {
        'datos_empleados': datos_empleados,
        'activos_por_anio': list(activos_por_anio),  # Convertimos a lista para JSON-safe
    })


def signout(request):
    logout(request)
    return redirect('empleados:signin')

def signin(request):  
    if request.method == 'GET':
        return render(request, 'empleados/login.html', {
            'form': AuthenticationForm
        })
    else:
       
        user = authenticate(
            request, username=request.POST['username'], password=request.POST['password']
        )
        if user is None:
            return render(request, 'empleados/login.html', {
                'form': AuthenticationForm,
                'error': 'Usuario o Password es Incorrecto'
            })
        else:
            
            auth_login(request, user)  
                      
            data = user.groups.all()
            for g in data:
                print(g.name)
                if g.name == 'Admin_gafetes':
                    return redirect('empleados:dahsboard')
                elif g.name == 'Admin_tickets':
                    return redirect('tickets:dashboard')
                elif g.name == 'tecnico':
                    return redirect('tickets:tickets_dahsboard')
                else:
                    return redirect('dahsboard')

@login_required
def crear_empleado(request):
    if request.method == 'POST':
        form = EmpleadoForm(request.POST, request.FILES)
        if form.is_valid():
            empleado = form.save(commit=False)  # Crea el objeto pero no lo guarda aún
            empleado.user = request.user  # Asignamos el usuario logueado
            empleado.save()  # Ahora sí lo guardamos en la base de datos
            return redirect('empleados:empleado_lista')  # Redirige a la lista de empleados
    else:
        form = EmpleadoForm()

    return render(request, 'empleados/crear_empleado.html', {'form': form})

  
@login_required
def editar_empleado(request, e_id):
    # Obtener el objeto empleado a editar
    empleado = get_object_or_404(Empleado, pk=e_id)

    # Formatear las fechas a 'YYYY-MM-DD'
    empleado.fecha_inicio = empleado.fecha_inicio.strftime('%Y-%m-%d')
    empleado.fecha_vencimiento = empleado.fecha_vencimiento.strftime('%Y-%m-%d')

    if request.method == 'POST':
        form = EmpleadoeditForm(request.POST, request.FILES, instance=empleado)
        if form.is_valid():
            form.save()
            return redirect('empleados:empleado_lista')
    else:
        form = EmpleadoeditForm(instance=empleado)

    return render(request, 'empleados/editar_empleado.html', {'form': form})





@login_required 
def lista_empleados(request):
    empleados = Empleado.objects.filter(activo=False) 
    return render(request, 'empleados/lista_empleados.html', {'empleados': empleados})


@login_required 
def credencial_empleados(request):
    empleados = Empleado.objects.all()  
    return render(request, 'empleados/credencial_empleados.html', {'empleados': empleados})


def empleado_detalle(request, id):
    empleado = Empleado.objects.get(id=id)
    
    # Generar el código QR
    qr_url = request.build_absolute_uri()  # Genera la URL completa de la página
    qr_image = qrcode.make(qr_url)

    # Guardar el código QR en un objeto BytesIO
    img_io = BytesIO()
    qr_image.save(img_io, 'PNG')
    img_io.seek(0)

    # Crear un archivo temporal en la memoria
    empleado.qr_code.save(f'qr_{empleado.id}.png', ContentFile(img_io.read()), save=False)
    configuracion = ConfiguracionGeneral.objects.first()
    return render(request, 'empleados/empleado_detalle.html', {
        'empleado': empleado,
        'configuracion': configuracion,
    })