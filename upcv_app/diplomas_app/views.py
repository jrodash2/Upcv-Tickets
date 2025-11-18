from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .forms import AgregarEmpleadoCursoForm, CursoForm
from .models import CursoEmpleado, Curso
from empleados_app.models import Empleado
from django.http import JsonResponse
from django.utils import timezone

from .models import Firma
from .forms import FirmaForm

def firmas_lista(request):
    firmas = Firma.objects.all().order_by('-id')
    form = FirmaForm()
    return render(request, "diplomas/firmas_lista.html", {
        "firmas": firmas,
        "form": form
    })


def crear_firma(request):
    if request.method == "POST":
        form = FirmaForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Firma creada correctamente.")
        else:
            messages.error(request, "Error al crear la firma.")
    return redirect("diplomas:firmas_lista")



def editar_curso(request, curso_id):
    curso = get_object_or_404(Curso, id=curso_id)

    if request.method == "POST":
        form = CursoForm(request.POST, instance=curso)
        if form.is_valid():
            form.save()
            messages.success(request, "Curso actualizado correctamente.")
            return redirect("diplomas:cursos_lista")
    else:
        form = CursoForm(instance=curso)

    return render(request, "diplomas/editar_curso.html", {"form": form, "curso": curso})



def agregar_empleado_a_curso(request):
    if request.method == "POST":
        form = AgregarEmpleadoCursoForm(request.POST)
        if form.is_valid():
            curso = form.cleaned_data["curso"]
            empleado = form.cleaned_data["empleado"]

            # Validar si ya está inscrito
            if CursoEmpleado.objects.filter(curso=curso, empleado=empleado).exists():
                messages.warning(request, "Este empleado ya está asignado a este curso.")
                return redirect("agregar_empleado_curso")

            CursoEmpleado.objects.create(
                curso=curso,
                empleado=empleado
            )

            messages.success(request, "Empleado agregado correctamente al curso.")
            return redirect("agregar_empleado_curso")
    else:
        form = AgregarEmpleadoCursoForm()

    return render(request, "diplomas/agregar_empleado_curso.html", {"form": form})


from django.http import JsonResponse
from empleados_app.models import Empleado

def buscar_empleado_por_dpi(request):
    dpi = request.GET.get("dpi")

    if not dpi:
        return JsonResponse({"error": "No se envió DPI"}, status=400)

    try:
        empleado = Empleado.objects.get(dpi=dpi)
        return JsonResponse({
            "existe": True,
            "nombres": empleado.nombres,
            "apellidos": empleado.apellidos,
            "nombre_completo": f"{empleado.nombres} {empleado.apellidos}"
        })
    except Empleado.DoesNotExist:
        return JsonResponse({"existe": False})


def crear_curso_modal(request):
    if request.method == "POST":
        form = CursoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Curso creado correctamente.")
            return redirect("diplomas:cursos_lista")
        else:
            messages.error(request, "Corrige los errores del formulario.")
            return redirect("diplomas:cursos_lista")

    return redirect("diplomas:cursos_lista")





def cursos_lista(request):
    cursos = Curso.objects.all().order_by('-creado_en')

    # formulario vacío para el modal
    form = CursoForm()

    return render(request, "diplomas/cursos_lista.html", {
        "cursos": cursos,
        "form": form
    })



def detalle_curso(request, curso_id):
    curso = get_object_or_404(Curso, id=curso_id)
    participantes = CursoEmpleado.objects.filter(curso=curso).select_related("empleado")

    return render(request, "diplomas/detalle_curso.html", {
        "curso": curso,
        "participantes": participantes
    })


def agregar_empleado_detalle(request, curso_id):
    curso = get_object_or_404(Curso, id=curso_id)
    dpi = request.POST.get("dpi")

    if not dpi:
        messages.error(request, "Debe ingresar un DPI.")
        return redirect("diplomas:detalle_curso", curso_id=curso.id)

    try:
        empleado = Empleado.objects.get(dpi=dpi)
    except Empleado.DoesNotExist:
        messages.error(request, "No existe un empleado con ese DPI.")
        return redirect("diplomas:detalle_curso", curso_id=curso.id)

    # Validar si ya está asignado
    if CursoEmpleado.objects.filter(curso=curso, empleado=empleado).exists():
        messages.warning(request, "El empleado ya está inscrito en este curso.")
        return redirect("diplomas:detalle_curso", curso_id=curso.id)

    # Crear asignación
    CursoEmpleado.objects.create(
        curso=curso,
        empleado=empleado,
        fecha_asignacion=timezone.now()
    )

    messages.success(request, "Empleado agregado correctamente.")
    return redirect("diplomas:detalle_curso", curso_id=curso.id)
