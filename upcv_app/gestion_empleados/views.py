from datetime import date

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from empleados_app.forms import DatosBasicosEmpleadoForm, EmpleadoeditForm
from empleados_app.models import Contrato, Empleado

from .forms import Contrato029Form, InformacionContrato029Form, PerfilRRHHForm, PostulanteForm
from .models import (CatalogoRequisito, DetalleEvaluacionRequisito, ExpedienteEmpleado,
                     InformacionContrato029, PerfilRRHHEmpleado, Postulante)
from .permissions import permiso_gestion_requerido
from .selectors import obtener_indicadores_dashboard
from .services import (completar_evaluacion, convertir_postulante_en_empleado, guardar_contrato_029,
                       guardar_postulante, iniciar_evaluacion, revisar_requisito)


@permiso_gestion_requerido()
def dashboard(request):
    return render(request, "gestion_empleados/dashboard.html", {"indicadores": obtener_indicadores_dashboard()})


@permiso_gestion_requerido("gestion_empleados.manage_preselection")
def preseleccion(request):
    return render(request, "gestion_empleados/preseleccion/lista.html", {"postulantes": Postulante.objects.select_related("empleado", "estado_tdr", "responsable")})


@permiso_gestion_requerido("gestion_empleados.manage_preselection")
def postulante_editar(request, pk=None):
    postulante = get_object_or_404(Postulante, pk=pk) if pk else None
    form = PostulanteForm(request.POST or None, request.FILES or None, instance=postulante)
    if request.method == "POST" and form.is_valid():
        postulante = guardar_postulante(form, request.user)
        messages.success(request, "Postulante guardado correctamente.")
        return redirect("gestion_empleados:postulante_detalle", pk=postulante.pk)
    return render(request, "gestion_empleados/preseleccion/form.html", {"form": form, "postulante": postulante})


@permiso_gestion_requerido()
def postulante_detalle(request, pk):
    postulante = get_object_or_404(Postulante.objects.select_related("empleado", "estado_tdr"), pk=pk)
    return render(request, "gestion_empleados/preseleccion/detalle.html", {"postulante": postulante})


@permiso_gestion_requerido("gestion_empleados.review_employee_files")
def reclutamiento(request):
    postulantes = Postulante.objects.select_related("estado_tdr").annotate(total=Count("evaluacion__detalles"), cumplidos=Count("evaluacion__detalles", filter=Q(evaluacion__detalles__cumple=True)))
    return render(request, "gestion_empleados/reclutamiento/lista.html", {"postulantes": postulantes})


@permiso_gestion_requerido("gestion_empleados.review_employee_files")
def expediente(request, postulante_id):
    postulante = get_object_or_404(Postulante, pk=postulante_id)
    evaluacion = iniciar_evaluacion(postulante)
    detalles = evaluacion.detalles.select_related("requisito", "revisado_por")
    return render(request, "gestion_empleados/reclutamiento/expediente.html", {"postulante": postulante, "evaluacion": evaluacion, "pre_aval": detalles.filter(requisito__fase=CatalogoRequisito.PRE_AVAL), "post_aval": detalles.filter(requisito__fase=CatalogoRequisito.POST_AVAL), "cumplidos": detalles.filter(cumple=True).count(), "total": detalles.count()})


@require_POST
@permiso_gestion_requerido("gestion_empleados.review_employee_files")
def requisito_revisar(request, pk):
    detalle = get_object_or_404(DetalleEvaluacionRequisito, pk=pk)
    revisar_requisito(detalle, request.POST.get("cumple") == "on", request.POST.get("observacion", ""), request.user)
    messages.success(request, "Requisito revisado y auditado.")
    return redirect("gestion_empleados:expediente", postulante_id=detalle.evaluacion.postulante_id)


@require_POST
@permiso_gestion_requerido("gestion_empleados.review_employee_files")
def expediente_completar(request, postulante_id):
    postulante = get_object_or_404(Postulante, pk=postulante_id)
    try:
        completar_evaluacion(iniciar_evaluacion(postulante), request.user)
    except ValidationError as error:
        messages.error(request, "; ".join(error.messages))
    else:
        messages.success(request, "Expediente marcado como completo.")
    return redirect("gestion_empleados:expediente", postulante_id=postulante_id)


@require_POST
@permiso_gestion_requerido("gestion_empleados.edit_employee_record")
def postulante_convertir(request, pk):
    postulante = get_object_or_404(Postulante, pk=pk)
    empleado = convertir_postulante_en_empleado(postulante, request.user)
    messages.success(request, "El postulante quedó vinculado al registro oficial del empleado.")
    return redirect("gestion_empleados:empleado_ficha", pk=empleado.pk)


@permiso_gestion_requerido()
def empleados(request):
    empleados_qs = Empleado.objects.prefetch_related("contratos").select_related("datos_basicos").order_by("apellidos", "nombres")
    return render(request, "gestion_empleados/empleados/lista.html", {"empleados": empleados_qs})


@permiso_gestion_requerido()
def empleado_ficha(request, pk):
    empleado = get_object_or_404(Empleado.objects.prefetch_related("contratos__informacion_029", "formaciones"), pk=pk)
    nacimiento = getattr(getattr(empleado, "datos_basicos", None), "fecha_nacimiento", None)
    edad = date.today().year - nacimiento.year - ((date.today().month, date.today().day) < (nacimiento.month, nacimiento.day)) if nacimiento else None
    return render(request, "gestion_empleados/empleados/ficha.html", {"empleado": empleado, "edad": edad})


@permiso_gestion_requerido("gestion_empleados.edit_employee_record")
def empleado_editar(request, pk):
    empleado = get_object_or_404(Empleado, pk=pk)
    datos = getattr(empleado, "datos_basicos", None); perfil = getattr(empleado, "perfil_rrhh", None)
    form_empleado = EmpleadoeditForm(request.POST or None, request.FILES or None, instance=empleado, prefix="empleado")
    form_datos = DatosBasicosEmpleadoForm(request.POST or None, instance=datos, prefix="datos")
    form_perfil = PerfilRRHHForm(request.POST or None, instance=perfil, prefix="rrhh")
    if request.method == "POST" and all(f.is_valid() for f in (form_empleado, form_datos, form_perfil)):
        from django.db import transaction
        with transaction.atomic():
            form_empleado.save(); obj = form_datos.save(commit=False); obj.empleado = empleado; obj.save(); obj = form_perfil.save(commit=False); obj.empleado = empleado; obj.save()
        messages.success(request, "Ficha actualizada."); return redirect("gestion_empleados:empleado_ficha", pk=pk)
    return render(request, "gestion_empleados/empleados/form.html", {"empleado": empleado, "formularios": (form_empleado, form_datos, form_perfil)})


@permiso_gestion_requerido("gestion_empleados.view_contract_information")
def contratos(request):
    return render(request, "gestion_empleados/contratos/lista.html", {"contratos": Contrato.objects.select_related("empleado", "sede", "puesto", "rescindido_por").order_by("-fecha_inicio")})


@permiso_gestion_requerido("gestion_empleados.manage_employee_contracts")
def contratacion(request, empleado_id):
    empleado = get_object_or_404(Empleado, pk=empleado_id)
    contrato_form, info_form = Contrato029Form(request.POST or None), InformacionContrato029Form(request.POST or None, request.FILES or None)
    if request.method == "POST" and contrato_form.is_valid() and info_form.is_valid():
        try:
            guardar_contrato_029(empleado, contrato_form, info_form, request.user)
        except ValidationError as error:
            messages.error(request, "; ".join(error.messages))
        else:
            messages.success(request, "Contrato 029 creado."); return redirect("gestion_empleados:empleado_ficha", pk=empleado.pk)
    return render(request, "gestion_empleados/contratos/form.html", {"empleado": empleado, "contrato_form": contrato_form, "info_form": info_form, "historial": empleado.contratos.select_related("informacion_029", "rescindido_por").order_by("-fecha_inicio")})
