from datetime import date

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from empleados_app.forms import DatosBasicosEmpleadoForm
from empleados_app.models import Contrato, Empleado

from .forms import (
    CasoActuacionForm,
    CasoJudicialForm,
    Contrato029Form,
    ControlMensualForm,
    DocumentoGestionForm,
    FichaEmpleadoForm,
    InformacionContrato029Form,
    PerfilRRHHForm,
    PuestoRapidoForm,
    SedeRapidaForm,
    PostulanteForm,
    PruebaConfiabilidadForm,
)
from .models import (
    CasoJudicial,
    CatalogoRequisito,
    ControlMensualContrato,
    DetalleEvaluacionRequisito,
    EstadoControlMensual,
    Postulante,
    ProcesoContratacion,
)
from .permissions import permiso_estricto_requerido, permiso_gestion_requerido
from .selectors import (
    empleados_con_estado_contractual,
    contratos_vigentes,
    obtener_dashboard,
    obtener_resumen_empleado,
)
from .services import (
    completar_evaluacion,
    aprobar_pre_aval,
    aprobar_post_aval,
    guardar_contrato_029,
    guardar_actuacion,
    guardar_caso,
    guardar_control_mensual,
    guardar_documento,
    guardar_postulante,
    iniciar_evaluacion,
    revisar_requisito,
    registrar_prueba_confiabilidad,
    pasar_a_reclutamiento,
    iniciar_proceso_empleado,
    iniciar_nueva_postulacion,
    marcar_contrato_firmado,
    aprobar_contrato,
    marcar_elegible,
    auditar,
    registrar_transicion,
)


@permiso_gestion_requerido()
def dashboard(request):
    return render(request, "gestion_empleados/dashboard.html", obtener_dashboard())


@permiso_gestion_requerido("gestion_empleados.manage_preselection")
def preseleccion(request):
    return render(
        request,
        "gestion_empleados/preseleccion/lista.html",
        {
            "procesos": ProcesoContratacion.objects.filter(
                estado__in=(ProcesoContratacion.PRESELECCION,
                            ProcesoContratacion.PRUEBA_CONFIABILIDAD,
                            ProcesoContratacion.NO_APROBADO)
            ).select_related("postulante", "empleado", "responsable")
        },
    )


@permiso_gestion_requerido("gestion_empleados.manage_preselection")
def postulante_editar(request, pk=None):
    postulante = get_object_or_404(Postulante, pk=pk) if pk else None
    if postulante is None and request.method == "POST":
        cui = request.POST.get("cui", "").strip()
        existente = Postulante.objects.filter(cui=cui).select_related("empleado").first()
        if existente:
            procesos = existente.procesos_contratacion.order_by("-fecha_inicio", "-created_at")
            tiene_contrato_activo = bool(
                existente.empleado_id
                and contratos_vigentes().filter(empleado_id=existente.empleado_id).exists()
            )
            return render(
                request,
                "gestion_empleados/preseleccion/existente.html",
                {
                    "postulante": existente,
                    "ultimo_proceso": procesos.first(),
                    "tiene_proceso_activo": procesos.filter(
                        estado__in=ProcesoContratacion.ESTADOS_ABIERTOS
                    ).exists(),
                    "tiene_contrato_activo": tiene_contrato_activo,
                },
                status=409,
            )
    form_class = PruebaConfiabilidadForm if postulante else PostulanteForm
    proceso = None
    if postulante:
        proceso = postulante.procesos_contratacion.filter(
            estado__in=(ProcesoContratacion.PRESELECCION,
                        ProcesoContratacion.PRUEBA_CONFIABILIDAD)
        ).order_by("-created_at").first()
        if proceso is None:
            return redirect("gestion_empleados:postulante_detalle", pk=postulante.pk)
    form = form_class(
        request.POST or None,
        request.FILES or None,
        instance=proceso if postulante else None,
    )
    if request.method == "POST" and form.is_valid():
        if postulante:
            registrar_prueba_confiabilidad(
                proceso, form.cleaned_data["resultado_confiabilidad"],
                form.cleaned_data["observacion_confiabilidad"], request.user,
            )
        else:
            try:
                postulante = guardar_postulante(form, request.user)
            except ValidationError as error:
                form.add_error(None, error)
                return render(
                    request,
                    "gestion_empleados/preseleccion/form.html",
                    {"form": form, "postulante": None, "proceso": None},
                )
        messages.success(request, "Postulante guardado correctamente.")
        return redirect("gestion_empleados:postulante_detalle", pk=postulante.pk)
    return render(
        request,
        "gestion_empleados/preseleccion/form.html",
        {"form": form, "postulante": postulante, "proceso": proceso},
    )


@permiso_gestion_requerido()
def postulante_detalle(request, pk):
    postulante = get_object_or_404(
        Postulante.objects.select_related("empleado", "estado_tdr"), pk=pk
    )
    procesos = postulante.procesos_contratacion.select_related(
        "contrato_resultante", "empleado"
    ).prefetch_related("evaluacion__detalles").order_by("-fecha_inicio", "-created_at")
    proceso_activo = procesos.filter(
        estado__in=ProcesoContratacion.ESTADOS_ABIERTOS
    ).first()
    tiene_contrato_activo = bool(
        postulante.empleado_id
        and contratos_vigentes().filter(empleado_id=postulante.empleado_id).exists()
    )
    return render(
        request,
        "gestion_empleados/preseleccion/detalle.html",
        {"postulante": postulante, "proceso": procesos.first(),
         "procesos": procesos, "proceso_activo": proceso_activo,
         "tiene_contrato_activo": tiene_contrato_activo},
    )


@require_POST
@permiso_gestion_requerido("gestion_empleados.manage_preselection")
def postulante_nueva_postulacion(request, pk):
    postulante = get_object_or_404(Postulante, pk=pk)
    try:
        proceso = iniciar_nueva_postulacion(postulante, request.user)
    except ValidationError as error:
        messages.error(request, "; ".join(error.messages))
    else:
        messages.success(request, "Nueva postulación iniciada correctamente.")
        return redirect("gestion_empleados:postulante_detalle", pk=proceso.postulante_id)
    return redirect("gestion_empleados:postulante_detalle", pk=pk)


@require_POST
@permiso_gestion_requerido("gestion_empleados.manage_preselection")
def proceso_reclutamiento(request, pk):
    proceso = get_object_or_404(ProcesoContratacion, pk=pk)
    try:
        pasar_a_reclutamiento(proceso, request.user)
    except ValidationError as error:
        messages.error(request, "; ".join(error.messages))
        if proceso.postulante_id:
            return redirect("gestion_empleados:postulante_detalle", pk=proceso.postulante_id)
        return redirect("gestion_empleados:reclutamiento")
    messages.success(request, "Proceso enviado a Reclutamiento y Selección.")
    return redirect("gestion_empleados:expediente", proceso_id=proceso.pk)


@permiso_gestion_requerido("gestion_empleados.review_employee_files")
def reclutamiento(request):
    procesos = ProcesoContratacion.objects.filter(
        estado__in=(ProcesoContratacion.RECLUTAMIENTO,
                    ProcesoContratacion.EXPEDIENTE_INCOMPLETO)
    ).select_related("postulante", "empleado", "evaluacion").annotate(
        total=Count(
            "evaluacion__detalles",
            filter=Q(
                evaluacion__detalles__requisito__activo=True,
                evaluacion__detalles__requisito__obligatorio=True,
            ),
        ),
        cumplidos=Count(
            "evaluacion__detalles",
            filter=Q(
                evaluacion__detalles__cumple=True,
                evaluacion__detalles__requisito__activo=True,
                evaluacion__detalles__requisito__obligatorio=True,
            ),
        ),
    )
    tipo, expediente_filtro = request.GET.get("tipo"), request.GET.get("expediente")
    if tipo in dict(ProcesoContratacion.TIPOS): procesos = procesos.filter(tipo_proceso=tipo)
    if expediente_filtro == "completo": procesos = procesos.filter(evaluacion__completo=True)
    elif expediente_filtro == "pendiente": procesos = procesos.filter(Q(evaluacion__completo=False) | Q(evaluacion__isnull=True))
    return render(
        request,
        "gestion_empleados/reclutamiento/lista.html",
        {"procesos": procesos, "tipos_proceso": ProcesoContratacion.TIPOS,
         "tipo_actual": tipo, "expediente_actual": expediente_filtro},
    )


@permiso_gestion_requerido("gestion_empleados.review_employee_files")
def expediente(request, proceso_id):
    proceso = get_object_or_404(ProcesoContratacion.objects.select_related("postulante", "empleado"), pk=proceso_id)
    if proceso.estado not in (
        ProcesoContratacion.RECLUTAMIENTO,
        ProcesoContratacion.EXPEDIENTE_INCOMPLETO,
        ProcesoContratacion.ELEGIBLE,
    ):
        messages.error(request, "El proceso no se encuentra en reclutamiento.")
        return redirect("gestion_empleados:reclutamiento")
    evaluacion = iniciar_evaluacion(proceso)
    detalles = evaluacion.detalles.filter(requisito__activo=True).select_related(
        "requisito", "revisado_por"
    ).order_by("requisito__orden", "requisito__pk")
    pre_aval = detalles.filter(requisito__fase=CatalogoRequisito.PRE_AVAL)
    post_aval = detalles.filter(requisito__fase=CatalogoRequisito.POST_AVAL)
    pre_cumplidos, pre_total = evaluacion.progreso_fase(CatalogoRequisito.PRE_AVAL)
    post_cumplidos, post_total = evaluacion.progreso_fase(CatalogoRequisito.POST_AVAL)
    return render(
        request,
        "gestion_empleados/reclutamiento/expediente.html",
        {
            "postulante": proceso.postulante, "proceso": proceso,
            "evaluacion": evaluacion,
            "pre_aval": pre_aval, "post_aval": post_aval,
            "pre_cumplidos": pre_cumplidos, "pre_total": pre_total,
            "post_cumplidos": post_cumplidos, "post_total": post_total,
            "pre_listo": bool(pre_total) and not evaluacion.requisitos_obligatorios_pendientes(
                CatalogoRequisito.PRE_AVAL
            ),
            "post_listo": bool(post_total) and not evaluacion.requisitos_obligatorios_pendientes(
                CatalogoRequisito.POST_AVAL
            ),
            "requisito_abierto": request.GET.get("requisito", ""),
            "elegible_registro": proceso.historial.filter(
                accion="paso_elegible"
            ).select_related("usuario").first(),
            "cumplidos": detalles.filter(cumple=True).count(),
            "total": detalles.count(),
        },
    )


@require_POST
@permiso_gestion_requerido("gestion_empleados.review_employee_files")
def requisito_revisar(request, pk):
    detalle = get_object_or_404(DetalleEvaluacionRequisito, pk=pk)
    try:
        revisar_requisito(
            detalle, request.POST.get("cumple") == "on",
            request.POST.get("observacion", ""), request.user,
        )
    except ValidationError as error:
        messages.error(request, "; ".join(error.messages))
    else:
        messages.success(request, "Requisito revisado y auditado.")
    destino = reverse(
        "gestion_empleados:expediente",
        kwargs={"proceso_id": detalle.evaluacion.proceso_id},
    )
    return redirect(f"{destino}?requisito={detalle.pk}#requisito-{detalle.pk}")


@require_POST
@permiso_gestion_requerido("gestion_empleados.review_employee_files")
def expediente_completar(request, proceso_id):
    proceso = get_object_or_404(ProcesoContratacion, pk=proceso_id)
    try:
        completar_evaluacion(iniciar_evaluacion(proceso), request.user)
    except ValidationError as error:
        messages.error(request, "; ".join(error.messages))
    else:
        messages.success(request, "Expediente marcado como completo.")
    return redirect("gestion_empleados:expediente", proceso_id=proceso_id)


def _aprobar_etapa(request, proceso_id, servicio, nombre):
    proceso = get_object_or_404(ProcesoContratacion, pk=proceso_id)
    try:
        servicio(iniciar_evaluacion(proceso), request.user)
    except ValidationError as error:
        messages.error(request, "; ".join(error.messages))
    else:
        messages.success(request, f"{nombre} aprobado correctamente.")
    return redirect("gestion_empleados:expediente", proceso_id=proceso_id)


@require_POST
@permiso_gestion_requerido("gestion_empleados.review_employee_files")
def expediente_aprobar_pre_aval(request, proceso_id):
    return _aprobar_etapa(request, proceso_id, aprobar_pre_aval, "Pre-aval")


@require_POST
@permiso_gestion_requerido("gestion_empleados.review_employee_files")
def expediente_aprobar_post_aval(request, proceso_id):
    return _aprobar_etapa(request, proceso_id, aprobar_post_aval, "Post-aval")


@require_POST
@permiso_gestion_requerido("gestion_empleados.review_employee_files")
def expediente_elegible(request, proceso_id):
    proceso = get_object_or_404(ProcesoContratacion, pk=proceso_id)
    try: marcar_elegible(proceso, request.user)
    except ValidationError as error: messages.error(request, "; ".join(error.messages))
    else:
        messages.success(request, "Aspirante marcado como elegible para contratación.")
        return redirect("gestion_empleados:elegibles")
    return redirect("gestion_empleados:expediente", proceso_id=proceso_id)


@permiso_gestion_requerido()
def elegibles(request):
    procesos = ProcesoContratacion.objects.filter(estado__in=(
        ProcesoContratacion.ELEGIBLE, ProcesoContratacion.CONTRATO_CREADO,
        ProcesoContratacion.CONTRATO_FIRMADO,
    )).select_related(
        "empleado", "postulante", "contrato_resultante",
        "contrato_en_preparacion",
    ).prefetch_related("empleado__contratos")
    tipo = request.GET.get("tipo")
    if tipo in dict(ProcesoContratacion.TIPOS): procesos = procesos.filter(tipo_proceso=tipo)
    for proceso in procesos:
        proceso.ultimo_contrato = (
            proceso.empleado.contratos.order_by("-fecha_inicio", "-pk").first()
            if proceso.empleado_id else None
        )
    return render(request, "gestion_empleados/elegibles/lista.html",
                  {"procesos": procesos, "tipos_proceso": ProcesoContratacion.TIPOS, "tipo_actual": tipo})


@permiso_gestion_requerido()
def proceso_detalle(request, pk):
    proceso = get_object_or_404(
        ProcesoContratacion.objects.select_related(
            "empleado", "postulante", "contrato_resultante", "responsable"
        ).prefetch_related(
            "historial__usuario", "evaluacion__detalles__requisito"
        ),
        pk=pk,
    )
    evaluacion = getattr(proceso, "evaluacion", None)
    pasos = {
        ProcesoContratacion.RECLUTAMIENTO: 1,
        ProcesoContratacion.EXPEDIENTE_INCOMPLETO: 1,
        ProcesoContratacion.ELEGIBLE: 2,
        ProcesoContratacion.CONTRATACION: 2,
        ProcesoContratacion.CONTRATO_CREADO: 3,
        ProcesoContratacion.CONTRATO_FIRMADO: 4,
        ProcesoContratacion.CONTRATADO: 6,
    }
    return render(
        request,
        "gestion_empleados/procesos/detalle.html",
        {"proceso": proceso, "evaluacion": evaluacion,
         "paso_contratacion": pasos.get(proceso.estado, 0)},
    )


@require_POST
@permiso_gestion_requerido("gestion_empleados.manage_employee_contracts")
def iniciar_proceso(request, empleado_id, tipo):
    empleado = get_object_or_404(Empleado, pk=empleado_id)
    try: proceso = iniciar_proceso_empleado(empleado, tipo.upper(), request.user, request.POST.get("periodo") or None)
    except (ValidationError, ValueError) as error:
        messages.error(request, "; ".join(getattr(error, "messages", [str(error)])))
        return redirect("gestion_empleados:empleado_ficha", pk=empleado.pk)
    messages.success(request, "Proceso iniciado sin modificar el contrato actual.")
    if proceso.estado == ProcesoContratacion.RECLUTAMIENTO:
        return redirect("gestion_empleados:expediente", proceso_id=proceso.pk)
    return redirect("gestion_empleados:postulante_detalle", pk=proceso.postulante_id)


@permiso_gestion_requerido()
def empleados(request):
    filtro_contrato = request.GET.get("contrato", "todos")
    empleados_qs = (
        empleados_con_estado_contractual()
        .annotate(total_contratos=Count("contratos", distinct=True))
        .select_related("datos_basicos")
        .order_by("apellidos", "nombres")
    )
    total_empleados = empleados_qs.count()
    con_contrato = empleados_qs.filter(tiene_contrato_activo_db=True).count()
    if filtro_contrato == "activo":
        empleados_qs = empleados_qs.filter(tiene_contrato_activo_db=True)
    elif filtro_contrato == "sin_activo":
        empleados_qs = empleados_qs.filter(tiene_contrato_activo_db=False)
    else:
        filtro_contrato = "todos"
    return render(
        request,
        "gestion_empleados/empleados/lista.html",
        {
            "empleados": empleados_qs,
            "filtro_contrato": filtro_contrato,
            "total_empleados": total_empleados,
            "con_contrato": con_contrato,
            "sin_contrato": total_empleados - con_contrato,
        },
    )


@permiso_gestion_requerido()
def empleado_ficha(request, pk):
    empleado = get_object_or_404(
        Empleado.objects.prefetch_related("contratos__informacion_029", "formaciones"),
        pk=pk,
    )
    nacimiento = getattr(
        getattr(empleado, "datos_basicos", None), "fecha_nacimiento", None
    )
    edad = (
        date.today().year
        - nacimiento.year
        - ((date.today().month, date.today().day) < (nacimiento.month, nacimiento.day))
        if nacimiento
        else None
    )
    contexto = {
        "empleado": empleado,
        "edad": edad,
        **obtener_resumen_empleado(empleado),
    }
    contexto["controles"] = ControlMensualContrato.objects.filter(
        contrato__empleado=empleado
    ).select_related("contrato", "estado", "responsable")
    contexto["procesos"] = empleado.procesos_contratacion.select_related(
        "contrato_resultante", "postulante").annotate(
            expediente_total=Count(
                "evaluacion__detalles",
                filter=Q(
                    evaluacion__detalles__requisito__activo=True,
                    evaluacion__detalles__requisito__obligatorio=True,
                ),
            ),
            expediente_cumplidos=Count(
                "evaluacion__detalles",
                filter=Q(
                    evaluacion__detalles__requisito__activo=True,
                    evaluacion__detalles__requisito__obligatorio=True,
                    evaluacion__detalles__cumple=True,
                ),
            ),
        ).prefetch_related("evaluacion__detalles")
    return render(request, "gestion_empleados/empleados/ficha.html", contexto)


@permiso_gestion_requerido("gestion_empleados.edit_employee_record")
def empleado_editar(request, pk):
    empleado = get_object_or_404(Empleado, pk=pk)
    datos = getattr(empleado, "datos_basicos", None)
    perfil = getattr(empleado, "perfil_rrhh", None)
    form_empleado = FichaEmpleadoForm(
        request.POST or None,
        request.FILES or None,
        instance=empleado,
        prefix="empleado",
    )
    form_datos = DatosBasicosEmpleadoForm(
        request.POST or None, instance=datos, prefix="datos"
    )
    form_perfil = PerfilRRHHForm(request.POST or None, instance=perfil, prefix="rrhh")
    if request.method == "POST" and all(
        f.is_valid() for f in (form_empleado, form_datos, form_perfil)
    ):
        from django.db import transaction

        with transaction.atomic():
            form_empleado.save()
            obj = form_datos.save(commit=False)
            obj.empleado = empleado
            obj.save()
            obj = form_perfil.save(commit=False)
            obj.empleado = empleado
            obj.save()
            auditar(empleado, request.user, "ficha_empleado_actualizada")
        messages.success(request, "Ficha actualizada.")
        return redirect("gestion_empleados:empleado_ficha", pk=pk)
    return render(
        request,
        "gestion_empleados/empleados/form.html",
        {"empleado": empleado, "formularios": (form_empleado, form_datos, form_perfil)},
    )


@permiso_gestion_requerido("gestion_empleados.view_contract_information")
def contratos(request):
    return render(
        request,
        "gestion_empleados/contratos/lista.html",
        {
            "contratos": Contrato.objects.select_related(
                "empleado", "sede", "puesto", "rescindido_por"
            ).order_by("-fecha_inicio")
        },
    )


@permiso_gestion_requerido("gestion_empleados.manage_employee_contracts")
def contratacion(request, proceso_id):
    proceso = get_object_or_404(ProcesoContratacion.objects.select_related("empleado", "postulante"), pk=proceso_id)
    if proceso.estado not in (
        ProcesoContratacion.ELEGIBLE, ProcesoContratacion.CONTRATACION,
        ProcesoContratacion.CONTRATO_CREADO,
        ProcesoContratacion.CONTRATO_FIRMADO,
    ) or not hasattr(proceso, "evaluacion") or not proceso.evaluacion.completo:
        messages.error(request, "El expediente debe completarse antes de iniciar la contratación.")
        return redirect("gestion_empleados:elegibles")
    empleado = proceso.empleado
    persona = empleado or proceso.postulante
    contrato_actual = proceso.contrato_en_preparacion
    contrato_referencia = (
        empleado.contratos.exclude(pk=contrato_actual.pk if contrato_actual else None)
        .order_by("-fecha_inicio", "-pk").first() if empleado else None
    )
    contrato_form, info_form = Contrato029Form(
        request.POST or None, instance=contrato_actual
    ), InformacionContrato029Form(
        request.POST or None, request.FILES or None,
        instance=getattr(contrato_actual, "informacion_029", None),
    )
    if request.method == "POST" and contrato_form.is_valid() and info_form.is_valid():
        try:
            guardar_contrato_029(empleado, contrato_form, info_form, request.user, proceso)
        except ValidationError as error:
            messages.error(request, "; ".join(error.messages))
        else:
            messages.success(request, "Contrato creado correctamente.")
            return redirect("gestion_empleados:contratacion", proceso_id=proceso.pk)
    return render(
        request,
        "gestion_empleados/contratos/form.html",
        {
            "empleado": empleado,
            "persona": persona,
            "proceso": proceso,
            "contrato_referencia": contrato_referencia,
            "contrato_form": contrato_form,
            "info_form": info_form,
            "historial": (
                empleado.contratos.select_related(
                    "informacion_029", "rescindido_por"
                ).order_by("-fecha_inicio")
                if empleado else Contrato.objects.none()
            ),
            "sede_form": SedeRapidaForm(),
            "puesto_form": PuestoRapidoForm(
                initial=(
                    {"sede": request.GET.get("sede")}
                    if request.GET.get("sede")
                    else None
                )
            ),
        },
    )


@require_POST
@permiso_gestion_requerido("gestion_empleados.manage_employee_contracts")
def contrato_marcar_firmado(request, proceso_id):
    proceso = get_object_or_404(ProcesoContratacion, pk=proceso_id)
    try:
        marcar_contrato_firmado(proceso, request.user)
    except ValidationError as error:
        messages.error(request, "; ".join(error.messages))
    else:
        messages.success(request, "Contrato marcado como firmado.")
    return redirect("gestion_empleados:contratacion", proceso_id=proceso_id)


@require_POST
@permiso_gestion_requerido("gestion_empleados.manage_employee_contracts")
def contrato_aprobar(request, proceso_id):
    proceso = get_object_or_404(ProcesoContratacion, pk=proceso_id)
    try:
        aprobar_contrato(proceso, request.user)
    except ValidationError as error:
        messages.error(request, "; ".join(error.messages))
        return redirect("gestion_empleados:contratacion", proceso_id=proceso_id)
    proceso.refresh_from_db()
    messages.success(request, "Contrato aprobado correctamente.")
    return redirect("gestion_empleados:empleado_ficha", pk=proceso.empleado_id)


@permiso_gestion_requerido("gestion_empleados.view_personnel_management")
def gestion_personal(request):
    controles = ControlMensualContrato.objects.select_related(
        "contrato__empleado", "contrato__puesto", "estado", "responsable"
    )
    filtros = {
        clave: request.GET.get(clave, "")
        for clave in (
            "anio",
            "mes",
            "empleado",
            "contrato",
            "departamento",
            "seccion",
            "estado",
        )
    }
    if filtros["anio"]:
        controles = controles.filter(anio=filtros["anio"])
    if filtros["mes"]:
        controles = controles.filter(mes=filtros["mes"])
    if filtros["empleado"]:
        controles = controles.filter(contrato__empleado_id=filtros["empleado"])
    if filtros["contrato"]:
        controles = controles.filter(contrato_id=filtros["contrato"])
    if filtros["departamento"]:
        controles = controles.filter(
            contrato__informacion_029__departamento=filtros["departamento"]
        )
    if filtros["seccion"]:
        controles = controles.filter(
            contrato__informacion_029__seccion=filtros["seccion"]
        )
    if filtros["estado"]:
        controles = controles.filter(estado_id=filtros["estado"])
    resumen = controles.aggregate(
        total=Count("id"),
        completos=Count("id", filter=Q(estado__es_completo=True)),
        observados=Count("id", filter=Q(estado__codigo="con-observaciones")),
    )
    resumen["pendientes"] = resumen["total"] - resumen["completos"]
    return render(
        request,
        "gestion_empleados/personal/lista.html",
        {
            "controles": controles,
            "filtros": filtros,
            "resumen": resumen,
            "empleados_filtro": Empleado.objects.order_by("apellidos"),
            "contratos_filtro": Contrato.objects.select_related("empleado"),
            "estados_filtro": EstadoControlMensual.objects.filter(activo=True),
        },
    )


@permiso_gestion_requerido("gestion_empleados.manage_monthly_deliverables")
def control_mensual_editar(request, pk=None):
    control = get_object_or_404(ControlMensualContrato, pk=pk) if pk else None
    form = ControlMensualForm(request.POST or None, instance=control)
    if not (
        request.user.is_superuser
        or request.user.has_perm("gestion_empleados.validate_monthly_deliverables")
    ):
        form.fields["estado"].queryset = form.fields["estado"].queryset.exclude(
            codigo="validado"
        )
    if request.method == "POST" and form.is_valid():
        if form.cleaned_data["estado"].codigo == "validado" and not (
            request.user.is_superuser
            or request.user.has_perm("gestion_empleados.validate_monthly_deliverables")
        ):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        try:
            control = guardar_control_mensual(form, request.user)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Control mensual guardado.")
            return redirect("gestion_empleados:control_mensual_detalle", pk=control.pk)
    return render(
        request,
        "gestion_empleados/personal/form.html",
        {"form": form, "control": control},
    )


@permiso_gestion_requerido("gestion_empleados.view_personnel_management")
def control_mensual_detalle(request, pk):
    control = get_object_or_404(
        ControlMensualContrato.objects.select_related(
            "contrato__empleado", "estado", "responsable"
        ).prefetch_related("documentos__tipo"),
        pk=pk,
    )
    return render(
        request,
        "gestion_empleados/personal/detalle.html",
        {"control": control, "documento_form": DocumentoGestionForm()},
    )


@require_POST
@permiso_gestion_requerido("gestion_empleados.manage_monthly_deliverables")
def control_documento_agregar(request, pk):
    control = get_object_or_404(ControlMensualContrato, pk=pk)
    form = DocumentoGestionForm(request.POST, request.FILES)
    if form.is_valid():
        guardar_documento(control, form, request.user)
        messages.success(request, "Documento cargado.")
    else:
        messages.error(request, "No fue posible cargar el documento.")
    return redirect("gestion_empleados:control_mensual_detalle", pk=pk)


@permiso_estricto_requerido("gestion_empleados.ver_casos")
def casos(request):
    casos_qs = CasoJudicial.objects.select_related(
        "empleado", "contrato", "estado", "responsable"
    ).annotate(total_actuaciones=Count("actuaciones"))
    return render(request, "gestion_empleados/casos/lista.html", {"casos": casos_qs})


@permiso_estricto_requerido("gestion_empleados.crear_casos")
def caso_crear(request):
    form = CasoJudicialForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if form.cleaned_data["estado"].cerrado and not (
            request.user.is_superuser
            or request.user.has_perm("gestion_empleados.cerrar_casos")
        ):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        caso = guardar_caso(form, request.user)
        messages.success(request, "Caso creado.")
        return redirect("gestion_empleados:caso_detalle", pk=caso.pk)
    return render(request, "gestion_empleados/casos/form.html", {"form": form})


@permiso_estricto_requerido("gestion_empleados.ver_casos")
def caso_detalle(request, pk):
    caso = get_object_or_404(
        CasoJudicial.objects.select_related(
            "empleado", "contrato", "estado", "responsable"
        ).prefetch_related("actuaciones__usuario", "documentos__tipo"),
        pk=pk,
    )
    return render(
        request,
        "gestion_empleados/casos/detalle.html",
        {
            "caso": caso,
            "actuacion_form": CasoActuacionForm(),
            "documento_form": DocumentoGestionForm(),
        },
    )


@permiso_estricto_requerido("gestion_empleados.editar_casos")
def caso_editar(request, pk):
    caso = get_object_or_404(CasoJudicial, pk=pk)
    form = CasoJudicialForm(request.POST or None, instance=caso)
    if request.method == "POST" and form.is_valid():
        if form.cleaned_data["estado"].cerrado and not (
            request.user.is_superuser
            or request.user.has_perm("gestion_empleados.cerrar_casos")
        ):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        caso = guardar_caso(form, request.user)
        messages.success(request, "Caso actualizado.")
        return redirect("gestion_empleados:caso_detalle", pk=caso.pk)
    return render(
        request, "gestion_empleados/casos/form.html", {"form": form, "caso": caso}
    )


@require_POST
@permiso_estricto_requerido("gestion_empleados.editar_casos")
def caso_actuacion_agregar(request, pk):
    caso = get_object_or_404(CasoJudicial, pk=pk)
    form = CasoActuacionForm(request.POST, request.FILES)
    if form.is_valid():
        guardar_actuacion(caso, form, request.user)
        messages.success(request, "Actuación registrada.")
    else:
        messages.error(request, "Revise los datos de la actuación.")
    return redirect("gestion_empleados:caso_detalle", pk=pk)


@require_POST
@permiso_estricto_requerido("gestion_empleados.editar_casos")
def caso_documento_agregar(request, pk):
    caso = get_object_or_404(CasoJudicial, pk=pk)
    form = DocumentoGestionForm(request.POST, request.FILES)
    if form.is_valid():
        guardar_documento(caso, form, request.user)
        messages.success(request, "Documento jurídico cargado.")
    else:
        messages.error(request, "Revise el documento.")
    return redirect("gestion_empleados:caso_detalle", pk=pk)
