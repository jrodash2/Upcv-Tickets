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

from django.urls import reverse


import qrcode
from io import BytesIO
from django.http import HttpResponse
from django.core.files.base import ContentFile


def home(request):
    return render(request, 'empleados/login.html')

@login_required 
def dahsboard(request):
    return render(request, 'empleados/dahsboard.html')


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
                    return redirect('tickets:tickets_dahsboard_adm')
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

  
def editar_empleado(request, e_id):
    empleado = get_object_or_404(Empleado, pk=e_id)
    
    if request.method == 'POST':
        form = EmpleadoeditForm(request.POST, request.FILES, instance=empleado)
        if form.is_valid():
            empleado = form.save(commit=False)
        
            empleado.save()
            return redirect('empleados:empleado_lista') 
    else:
        form = EmpleadoeditForm(instance=empleado)
    
    return render(request, 'empleados/editar_empleado.html', {'form': form})




@login_required 
def lista_empleados(request):
    empleados = Empleado.objects.all()  
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

    return render(request, 'empleados/empleado_detalle.html', {
        'empleado': empleado,
    })