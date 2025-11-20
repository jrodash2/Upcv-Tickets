from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .forms import AgregarEmpleadoCursoForm, CursoForm
from .models import CursoEmpleado, Curso
from empleados_app.models import Empleado
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
import json
from .models import Firma
from .forms import FirmaForm
from empleados_app.models import ConfiguracionGeneral





def eliminar_participante(request, curso_id, participante_id):
    curso = get_object_or_404(Curso, id=curso_id)
    asignacion = get_object_or_404(CursoEmpleado, id=participante_id)

    asignacion.delete()

    messages.success(request, "Participante eliminado del curso.")
    return redirect("diplomas:detalle_curso", curso_id=curso.id)



def diplomas_dahsboard(request):


    return render(request, 'diplomas/dashboard.html')



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


def ver_diploma(request, curso_id, participante_id):

    # Participante = CursoEmpleado
    curso_empleado = get_object_or_404(
        CursoEmpleado,
        id=participante_id,
        curso_id=curso_id
    )

    curso = curso_empleado.curso
    empleado = curso_empleado.empleado

    # Configuración general
    config = ConfiguracionGeneral.objects.first()

    context = {
        "curso": curso,
        "empleado": empleado,
        "curso_empleado": curso_empleado,  # contiene el número de diploma
        "config": config,
    }

    return render(request, "diplomas/ver_diploma.html", context)




@csrf_exempt
def guardar_posiciones(request, curso_id):
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    # Buscar curso
    try:
        curso = Curso.objects.get(id=curso_id)
    except Curso.DoesNotExist:
        return JsonResponse({"error": "Curso no encontrado"}, status=404)

    # Leer JSON de la petición
    try:
        data = json.loads(request.body)
    except Exception as e:
        return JsonResponse({"error": f"JSON inválido: {str(e)}"}, status=400)

    # Validar estructura del diccionario recibido
    posiciones_limpias = {}

    for key, values in data.items():
        posiciones_limpias[key] = {
            "left": int(values.get("left", 0)),
            "top": int(values.get("top", 0)),
            "width": int(values.get("width", 0)),
            "height": int(values.get("height", 0)),

            # Asegurar scale siempre existe y es numérico
            "scale": float(values.get("scale", 1))
        }

    # Guardar en el modelo
    curso.posiciones = posiciones_limpias
    curso.save()

    return JsonResponse({"success": True})

def detalle_curso(request, curso_id):
    curso = get_object_or_404(Curso, id=curso_id)
    participantes = CursoEmpleado.objects.filter(curso=curso).select_related("empleado")
    total_participantes = participantes.count()

    return render(request, "diplomas/detalle_curso.html", {
        "curso": curso,
        "participantes": participantes,
        "total_participantes": total_participantes
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
