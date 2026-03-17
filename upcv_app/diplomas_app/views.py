import json

from django.contrib import messages
from django.db.models import ProtectedError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from empleados_app.models import ConfiguracionGeneral, Empleado

from .forms import AgregarEmpleadoCursoForm, CursoForm, DisenoDiplomaForm, FirmaForm
from .models import Curso, CursoEmpleado, DisenoDiploma, Firma


DEFAULT_DIPLOMA_ELEMENTS = {
    "logo1": {"x": 1200, "y": 20, "width": 150, "height": 150, "font_size": 20, "color": "#000000", "align": "left", "content": "{{ logo_1 }}", "type": "logo"},
    "logo2": {"x": 1650, "y": 20, "width": 150, "height": 150, "font_size": 20, "color": "#000000", "align": "left", "content": "{{ logo_2 }}", "type": "logo"},
    "institucion": {"x": 1200, "y": 120, "width": 1100, "height": 120, "font_size": 100, "color": "#000000", "align": "center", "content": "{{ institucion_nombre }}", "type": "text"},
    "titulo": {"x": 1050, "y": 450, "width": 1400, "height": 100, "font_size": 55, "color": "#000000", "align": "center", "content": "OTORGA EL PRESENTE DIPLOMA A:", "type": "text"},
    "nombre": {"x": 1150, "y": 580, "width": 1300, "height": 160, "font_size": 120, "color": "#000000", "align": "center", "content": "{{ participante_nombre }}", "type": "text"},
    "curso": {"x": 1250, "y": 780, "width": 1000, "height": 100, "font_size": 55, "color": "#000000", "align": "center", "content": "{{ curso_nombre }}", "type": "text"},
    "horas": {"x": 1260, "y": 900, "width": 1000, "height": 80, "font_size": 40, "color": "#000000", "align": "center", "content": "{{ horas }}", "type": "text"},
    "fecha": {"x": 1300, "y": 1050, "width": 900, "height": 80, "font_size": 33, "color": "#000000", "align": "center", "content": "Guatemala, {{ fecha }} © UPCV", "type": "text"},
    "codigo": {"x": 1400, "y": 760, "width": 900, "height": 80, "font_size": 33, "color": "#000000", "align": "left", "content": "Código- {{ codigo }}", "type": "text"},
    "firmas": {"x": 800, "y": 1300, "width": 1900, "height": 500, "font_size": 28, "color": "#000000", "align": "center", "content": "{{ firmas }}", "type": "firmas"},
}

from .forms import AgregarEmpleadoCursoForm, CursoForm, DisenoDiplomaForm, FirmaForm
from .models import Curso, CursoEmpleado, DisenoDiploma, Firma

def _clamp_number(value, default, min_value=0):
    try:
        casted = float(value)
    except (TypeError, ValueError):
        return default
    return casted if casted >= min_value else default


def _build_elements_from_positions(posiciones):
    elementos = {key: value.copy() for key, value in DEFAULT_DIPLOMA_ELEMENTS.items()}
    if not isinstance(posiciones, dict):
        return elementos

    for key, value in posiciones.items():
        if key not in elementos or not isinstance(value, dict):
            continue
        elementos[key]["x"] = _clamp_number(value.get("left"), elementos[key]["x"])
        elementos[key]["y"] = _clamp_number(value.get("top"), elementos[key]["y"])
        elementos[key]["width"] = _clamp_number(value.get("width"), elementos[key]["width"])
        elementos[key]["height"] = _clamp_number(value.get("height"), elementos[key]["height"])
    return elementos


def _build_diseno_elements(diseno, fallback_posiciones):
    elementos = _build_elements_from_positions(fallback_posiciones)
    if not diseno or not isinstance(diseno.estilos, dict):
        return elementos

    estilos = diseno.estilos
    if isinstance(estilos.get("elements"), dict):
        for key, value in estilos["elements"].items():
            if key not in elementos or not isinstance(value, dict):
                continue
            elementos[key].update({
                "x": _clamp_number(value.get("x"), elementos[key]["x"]),
                "y": _clamp_number(value.get("y"), elementos[key]["y"]),
                "width": _clamp_number(value.get("width"), elementos[key]["width"]),
                "height": _clamp_number(value.get("height"), elementos[key]["height"]),
                "font_size": _clamp_number(value.get("font_size"), elementos[key]["font_size"], min_value=1),
                "color": value.get("color") or elementos[key]["color"],
                "align": value.get("align") or elementos[key]["align"],
                "content": value.get("content") or elementos[key]["content"],
            })
        return elementos

    return _build_elements_from_positions(estilos)


def _resolve_content(template_content, curso_empleado, config):
    empleado = curso_empleado.empleado
    curso = curso_empleado.curso
    context_map = {
        "{{ participante_nombre }}": f"{empleado.nombres} {empleado.apellidos}",
        "{{ curso_nombre }}": curso.nombre,
        "{{ fecha }}": timezone.now().strftime("%Y"),
        "{{ horas }}": "",
        "{{ codigo }}": f"{curso_empleado.id:04d}-UPCV",
        "{{ institucion_nombre }}": config.nombre_institucion if config else "",
        "{{ logo_1 }}": "",
        "{{ logo_2 }}": "",
        "{{ firmas }}": "",
    }
    resolved = template_content
    for token, value in context_map.items():
        resolved = resolved.replace(token, value)
    return resolved


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
    return render(request, "diplomas/firmas_lista.html", {"firmas": firmas, "form": form})


def crear_firma(request):
    if request.method == "POST":
        form = FirmaForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Firma creada correctamente.")
        else:
            messages.error(request, "Error al crear la firma.")
    return redirect("diplomas:firmas_lista")


def disenos_lista(request):
    disenos = DisenoDiploma.objects.all().order_by('-id')
    form = DisenoDiplomaForm()
    return render(request, "diplomas/disenos_lista.html", {"disenos": disenos, "form": form})


def crear_diseno(request):
    if request.method == "POST":
        form = DisenoDiplomaForm(request.POST, request.FILES)
        if form.is_valid():
            diseno = form.save(commit=False)
            if not diseno.estilos:
                diseno.estilos = {"elements": DEFAULT_DIPLOMA_ELEMENTS}
            diseno.save()
            messages.success(request, "Diseño de diploma creado correctamente.")
        else:
            messages.error(request, "No se pudo crear el diseño. Revise los campos.")
    return redirect("diplomas:disenos_lista")


def editar_diseno(request, diseno_id):
    diseno = get_object_or_404(DisenoDiploma, id=diseno_id)
    if request.method == "POST":
        form = DisenoDiplomaForm(request.POST, request.FILES, instance=diseno)
        if form.is_valid():
            form.save()
            messages.success(request, "Diseño actualizado correctamente.")
            return redirect("diplomas:disenos_lista")
    else:
        form = DisenoDiplomaForm(instance=diseno)

    return render(request, "diplomas/editar_diseno.html", {"form": form, "diseno": diseno})


def modificar_diseno_visual(request, diseno_id):
    diseno = get_object_or_404(DisenoDiploma, id=diseno_id)
    elementos = _build_diseno_elements(diseno, {})
    context = {
        "diseno": diseno,
        "elementos": elementos,
        "elementos_json": json.dumps(elementos),
    }
    return render(request, "diplomas/editor_diseno_visual.html", context)


def guardar_diseno_visual(request, diseno_id):
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    diseno = get_object_or_404(DisenoDiploma, id=diseno_id)
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    incoming = payload.get("elements") if isinstance(payload, dict) else None
    if not isinstance(incoming, dict):
        return JsonResponse({"error": "Estructura de elementos inválida"}, status=400)

    elementos = _build_diseno_elements(diseno, {})
    for key, value in incoming.items():
        if key not in elementos or not isinstance(value, dict):
            continue
        elementos[key]["x"] = _clamp_number(value.get("x"), elementos[key]["x"])
        elementos[key]["y"] = _clamp_number(value.get("y"), elementos[key]["y"])
        elementos[key]["width"] = _clamp_number(value.get("width"), elementos[key]["width"])
        elementos[key]["height"] = _clamp_number(value.get("height"), elementos[key]["height"])
        elementos[key]["font_size"] = _clamp_number(value.get("font_size"), elementos[key]["font_size"], min_value=1)
        elementos[key]["color"] = value.get("color") or elementos[key]["color"]
        elementos[key]["align"] = value.get("align") or elementos[key]["align"]
        elementos[key]["content"] = value.get("content") or elementos[key]["content"]

    diseno.estilos = {"elements": elementos}
    diseno.save(update_fields=["estilos", "actualizado_en"])
    return JsonResponse({"success": True})


def eliminar_diseno(request, diseno_id):
    diseno = get_object_or_404(DisenoDiploma, id=diseno_id)
    if request.method == "POST":
        if diseno.cursos.exists():
            messages.error(request, "No se puede eliminar el diseño porque está asignado a uno o más cursos.")
        else:
            try:
                diseno.delete()
                messages.success(request, "Diseño eliminado correctamente.")
            except ProtectedError:
                messages.error(request, "No se puede eliminar el diseño por integridad de datos.")
    return redirect("diplomas:disenos_lista")


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

            if CursoEmpleado.objects.filter(curso=curso, empleado=empleado).exists():
                messages.warning(request, "Este empleado ya está asignado a este curso.")
                return redirect("agregar_empleado_curso")

            CursoEmpleado.objects.create(curso=curso, empleado=empleado)
            messages.success(request, "Empleado agregado correctamente al curso.")
            return redirect("agregar_empleado_curso")
    else:
        form = AgregarEmpleadoCursoForm()

    return render(request, "diplomas/agregar_empleado_curso.html", {"form": form})


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
        messages.error(request, "Corrige los errores del formulario.")
        return redirect("diplomas:cursos_lista")

    return redirect("diplomas:cursos_lista")


def cursos_lista(request):
    cursos = Curso.objects.all().order_by('-creado_en')
    form = CursoForm()
    return render(request, "diplomas/cursos_lista.html", {"cursos": cursos, "form": form})


def ver_diploma(request, curso_id, participante_id):
    curso_empleado = get_object_or_404(CursoEmpleado, id=participante_id, curso_id=curso_id)
    curso = curso_empleado.curso
    config = ConfiguracionGeneral.objects.first()

    elementos = _build_diseno_elements(curso.diseno_diploma, curso.posiciones or {})
    for key, data in elementos.items():
        if data.get("type") == "text":
            data["rendered_content"] = _resolve_content(data.get("content", ""), curso_empleado, config)
        else:
            data["rendered_content"] = data.get("content", "")

    fondo_url = curso.diseno_diploma.imagen_fondo.url if curso.diseno_diploma and curso.diseno_diploma.imagen_fondo else None

    context = {
        "curso": curso,
        "curso_empleado": curso_empleado,
        "config": config,
        "elementos": elementos,
        "fondo_url": fondo_url,
    }
    return render(request, "diplomas/ver_diploma.html", context)


@csrf_exempt
def guardar_posiciones(request, curso_id):
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    curso = get_object_or_404(Curso, id=curso_id)

    try:
        data = json.loads(request.body)
    except Exception as e:
        return JsonResponse({"error": f"JSON inválido: {str(e)}"}, status=400)

    posiciones_limpias = {}
    for key, values in data.items():
        posiciones_limpias[key] = {
            "left": int(values.get("left", 0)),
            "top": int(values.get("top", 0)),
            "width": int(values.get("width", 0)),
            "height": int(values.get("height", 0)),
            "scale": float(values.get("scale", 1)),
        }

    if curso.diseno_diploma:
        elementos = _build_diseno_elements(curso.diseno_diploma, curso.posiciones)
        for key, values in posiciones_limpias.items():
            if key in elementos:
                elementos[key]["x"] = values["left"]
                elementos[key]["y"] = values["top"]
                elementos[key]["width"] = values["width"]
                elementos[key]["height"] = values["height"]
        curso.diseno_diploma.estilos = {"elements": elementos}
        curso.diseno_diploma.save(update_fields=["estilos", "actualizado_en"])
    else:
        curso.posiciones = posiciones_limpias
        curso.save(update_fields=["posiciones"])

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

    if CursoEmpleado.objects.filter(curso=curso, empleado=empleado).exists():
        messages.warning(request, "El empleado ya está inscrito en este curso.")
        return redirect("diplomas:detalle_curso", curso_id=curso.id)

    CursoEmpleado.objects.create(curso=curso, empleado=empleado, fecha_asignacion=timezone.now())
    messages.success(request, "Empleado agregado correctamente.")
    return redirect("diplomas:detalle_curso", curso_id=curso.id)
