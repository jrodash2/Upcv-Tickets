from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from empleados_app.models import Contrato, Empleado

from .models import (
    CatalogoRequisito,
    DetalleEvaluacionRequisito,
    EvaluacionExpediente,
    HistorialProcesoContratacion,
    HistorialEstadoPostulante,
    HistorialRevisionRequisito,
    Postulante,
    ProcesoContratacion,
    RegistroAuditoria,
)
from .permissions import puede_acceder


def auditar(objeto, usuario, accion, detalle=""):
    return RegistroAuditoria.objects.create(
        objeto=objeto, usuario=usuario, accion=accion, detalle=detalle
    )


def registrar_transicion(proceso, usuario, accion, estado_nuevo=None, detalle=""):
    anterior = proceso.estado
    nuevo = estado_nuevo or anterior
    if estado_nuevo and estado_nuevo != anterior:
        proceso.estado = estado_nuevo
        proceso.actualizado_por = usuario
        if nuevo in (ProcesoContratacion.CONTRATADO, ProcesoContratacion.NO_APROBADO,
                     ProcesoContratacion.CANCELADO):
            proceso.fecha_finalizacion = timezone.now()
        proceso.save()
    HistorialProcesoContratacion.objects.create(
        proceso=proceso, usuario=usuario, accion=accion,
        estado_anterior=anterior, estado_nuevo=nuevo, detalle=detalle,
    )
    auditar(proceso, usuario, accion, detalle)
    return proceso


@transaction.atomic
def guardar_postulante(form, usuario):
    postulante = form.save(commit=False)
    es_nuevo = postulante.pk is None
    empleado = Empleado.objects.filter(dpi=postulante.cui).first()
    if empleado:
        postulante.empleado = empleado
        postulante.nombres, postulante.apellidos = empleado.nombres, empleado.apellidos
    anterior = Postulante.objects.select_for_update().filter(pk=postulante.pk).first()
    postulante.responsable = usuario
    postulante.full_clean()
    postulante.save()
    form.save_m2m()
    if postulante.estado_tdr_id and (not anterior or anterior.estado_tdr_id != postulante.estado_tdr_id):
        HistorialEstadoPostulante.objects.create(
            postulante=postulante,
            estado_anterior=anterior.estado_tdr if anterior else None,
            estado_nuevo=postulante.estado_tdr,
            usuario=usuario,
        )
    auditar(postulante, usuario, "postulante_guardado")
    if es_nuevo:
        iniciar_nueva_postulacion(postulante, usuario)
    return postulante


@transaction.atomic
def registrar_prueba_confiabilidad(proceso, resultado, observacion, usuario):
    if resultado not in dict(ProcesoContratacion.RESULTADOS_PRUEBA):
        raise ValidationError("Resultado de prueba inválido.")
    proceso = ProcesoContratacion.objects.select_for_update().filter(
        pk=proceso.pk,
        estado__in=(ProcesoContratacion.PRESELECCION,
                    ProcesoContratacion.PRUEBA_CONFIABILIDAD)
    ).first()
    if not proceso:
        raise ValidationError("No existe un proceso abierto en preselección.")
    proceso.resultado_confiabilidad = resultado
    proceso.observacion_confiabilidad = observacion
    proceso.fecha_evaluacion_confiabilidad = timezone.now()
    proceso.evaluado_por = usuario
    proceso.actualizado_por = usuario
    proceso.save()
    nuevo = (ProcesoContratacion.NO_APROBADO
             if resultado == ProcesoContratacion.PRUEBA_NO_APROBADA
             else ProcesoContratacion.PRUEBA_CONFIABILIDAD)
    registrar_transicion(proceso, usuario, "resultado_prueba_confiabilidad", nuevo,
                         observacion)
    return proceso


@transaction.atomic
def pasar_a_reclutamiento(proceso, usuario):
    if not puede_acceder(usuario, "gestion_empleados.manage_preselection"):
        raise PermissionDenied

    # Bloquear exclusivamente ProcesoContratacion. Sus relaciones empleado y
    # postulante son nullable; incluirlas con select_related produciría LEFT JOIN
    # y PostgreSQL no permite FOR UPDATE sobre el lado nullable del join.
    try:
        proceso_bloqueado = ProcesoContratacion.objects.select_for_update().get(
            pk=proceso.pk
        )
    except ProcesoContratacion.DoesNotExist as error:
        raise ValidationError("El proceso ya no existe.") from error
    if proceso_bloqueado.estado == ProcesoContratacion.RECLUTAMIENTO:
        raise ValidationError("Este proceso ya se encuentra en Reclutamiento y Selección.")
    if proceso_bloqueado.estado == ProcesoContratacion.CANCELADO:
        raise ValidationError("Un proceso cancelado no puede avanzar a reclutamiento.")
    if proceso_bloqueado.estado == ProcesoContratacion.CONTRATADO:
        raise ValidationError("El proceso ya fue contratado y no puede volver a reclutamiento.")
    if proceso_bloqueado.estado == ProcesoContratacion.NO_APROBADO:
        raise ValidationError(
            "El postulante no aprobó la Prueba de Confiabilidad y no puede "
            "continuar a Reclutamiento."
        )
    if proceso_bloqueado.estado not in (
        ProcesoContratacion.PRESELECCION,
        ProcesoContratacion.PRUEBA_CONFIABILIDAD,
    ):
        raise ValidationError("El proceso no se encuentra en una etapa válida para avanzar.")

    requiere_confiabilidad = proceso_bloqueado.tipo_proceso in (
        ProcesoContratacion.INGRESO,
        ProcesoContratacion.REINGRESO,
    )
    if requiere_confiabilidad:
        if proceso_bloqueado.resultado_confiabilidad == ProcesoContratacion.PRUEBA_PENDIENTE:
            raise ValidationError("La Prueba de Confiabilidad todavía está pendiente.")
        if proceso_bloqueado.resultado_confiabilidad == ProcesoContratacion.PRUEBA_NO_APROBADA:
            raise ValidationError(
                "El postulante no aprobó la Prueba de Confiabilidad y no puede "
                "continuar a Reclutamiento."
            )
        if (
            not proceso_bloqueado.postulante_id
            or proceso_bloqueado.resultado_confiabilidad
            != ProcesoContratacion.PRUEBA_APROBADA
        ):
            raise ValidationError("La Prueba de Confiabilidad debe estar aprobada.")

    registrar_transicion(proceso_bloqueado, usuario, "paso_reclutamiento",
                         ProcesoContratacion.RECLUTAMIENTO)
    iniciar_evaluacion(proceso_bloqueado)
    return proceso_bloqueado


@transaction.atomic
def iniciar_proceso_empleado(empleado, tipo, usuario, periodo=None):
    empleado = Empleado.objects.select_for_update().get(pk=empleado.pk)
    periodo = periodo or timezone.localdate().year
    vigente = Contrato.objects.filter(
        empleado=empleado, activo=True, estado=Contrato.ESTADO_ACTIVO,
        fecha_inicio__lte=timezone.localdate(), fecha_vencimiento__gte=timezone.localdate(),
    ).exists()
    if tipo == ProcesoContratacion.RENOVACION and not vigente:
        raise ValidationError("Solo puede renovar un empleado con contrato activo.")
    if tipo == ProcesoContratacion.REINGRESO and (vigente or not empleado.contratos.exists()):
        raise ValidationError("El reingreso requiere historial contractual y ningún contrato activo.")
    if ProcesoContratacion.objects.filter(
        empleado=empleado, tipo_proceso=tipo, periodo=periodo,
        estado__in=ProcesoContratacion.ESTADOS_ABIERTOS,
    ).exists():
        raise ValidationError("Ya existe un proceso abierto de este tipo para el período.")
    postulante = None
    estado = ProcesoContratacion.RECLUTAMIENTO
    if tipo == ProcesoContratacion.REINGRESO:
        postulante, _ = Postulante.objects.get_or_create(
            cui=empleado.dpi,
            defaults={"nombres": empleado.nombres, "apellidos": empleado.apellidos,
                      "programa_area": empleado.dcargo or "Por definir", "responsable": usuario,
                      "empleado": empleado},
        )
        postulante.empleado = empleado
        postulante.save()
        estado = ProcesoContratacion.PRESELECCION
    proceso = ProcesoContratacion.objects.create(
        tipo_proceso=tipo, estado=estado, empleado=empleado, postulante=postulante,
        resultado_confiabilidad=ProcesoContratacion.PRUEBA_PENDIENTE,
        periodo=periodo, responsable=usuario, creado_por=usuario, actualizado_por=usuario,
    )
    registrar_transicion(proceso, usuario,
                         "renovacion_iniciada" if tipo == ProcesoContratacion.RENOVACION else "reingreso_iniciado")
    if estado == ProcesoContratacion.RECLUTAMIENTO:
        iniciar_evaluacion(proceso)
    return proceso


@transaction.atomic
def iniciar_evaluacion(proceso):
    postulante = None
    if proceso.postulante_id:
        postulante = Postulante.objects.get(pk=proceso.postulante_id)
    else:
        if not proceso.empleado_id:
            raise ValidationError("El proceso no tiene una persona vinculada.")
        postulante, _ = Postulante.objects.get_or_create(
            cui=proceso.empleado.dpi,
            defaults={"nombres": proceso.empleado.nombres, "apellidos": proceso.empleado.apellidos,
                      "programa_area": proceso.empleado.dcargo or "Por definir",
                      "responsable": proceso.responsable, "empleado": proceso.empleado},
        )
    evaluacion, _ = EvaluacionExpediente.objects.get_or_create(
        proceso=proceso, defaults={"postulante": postulante}
    )
    existentes = set(evaluacion.detalles.values_list("requisito_id", flat=True))
    DetalleEvaluacionRequisito.objects.bulk_create(
        [
            DetalleEvaluacionRequisito(evaluacion=evaluacion, requisito=r)
            for r in CatalogoRequisito.objects.filter(activo=True).exclude(
                pk__in=existentes
            )
        ]
    )
    return evaluacion


@transaction.atomic
def vincular_empleado_para_contratacion(proceso, usuario):
    raise ValidationError(
        "El empleado se vincula únicamente al aprobar un contrato firmado."
    )


@transaction.atomic
def iniciar_nueva_postulacion(postulante, usuario):
    if not puede_acceder(usuario, "gestion_empleados.manage_preselection"):
        raise PermissionDenied
    postulante = Postulante.objects.select_for_update().get(pk=postulante.pk)
    identidad = Q(postulante=postulante)
    if postulante.empleado_id:
        identidad |= Q(empleado_id=postulante.empleado_id)
    procesos_abiertos = ProcesoContratacion.objects.select_for_update().filter(
        identidad, estado__in=ProcesoContratacion.ESTADOS_ABIERTOS
    )
    if procesos_abiertos.exists():
        raise ValidationError("El postulante ya tiene un proceso activo.")

    empleado = postulante.empleado
    if empleado is None:
        empleado = Empleado.objects.filter(dpi=postulante.cui).first()
        if empleado:
            postulante.empleado = empleado
            postulante.save(update_fields=("empleado", "updated_at"))
    tipo = ProcesoContratacion.INGRESO
    if empleado:
        hoy = timezone.localdate()
        if Contrato.objects.filter(
            empleado=empleado, activo=True, estado=Contrato.ESTADO_ACTIVO,
            fecha_inicio__lte=hoy, fecha_vencimiento__gte=hoy,
        ).exists():
            raise ValidationError(
                "El empleado tiene contrato activo; debe iniciar una renovación."
            )
        if empleado.contratos.exists():
            tipo = ProcesoContratacion.REINGRESO
    proceso = ProcesoContratacion.objects.create(
        tipo_proceso=tipo,
        estado=ProcesoContratacion.PRESELECCION,
        resultado_confiabilidad=ProcesoContratacion.PRUEBA_PENDIENTE,
        postulante=postulante,
        empleado=empleado,
        responsable=usuario,
        creado_por=usuario,
        actualizado_por=usuario,
    )
    registrar_transicion(proceso, usuario, "nueva_postulacion_iniciada")
    return proceso


@transaction.atomic
def revisar_requisito(detalle, cumple, observacion, usuario):
    detalle = DetalleEvaluacionRequisito.objects.select_for_update().get(pk=detalle.pk)
    evaluacion = EvaluacionExpediente.objects.select_for_update().get(
        pk=detalle.evaluacion_id
    )
    requisito = CatalogoRequisito.objects.get(pk=detalle.requisito_id)
    if requisito.fase == CatalogoRequisito.POST_AVAL and not evaluacion.pre_aval_aprobado:
        raise ValidationError("Post-aval se habilitará al aprobar Pre-aval.")
    if requisito.fase == CatalogoRequisito.PRE_AVAL and evaluacion.pre_aval_aprobado:
        raise ValidationError("Pre-aval ya fue aprobado y no admite más cambios.")
    if requisito.fase == CatalogoRequisito.POST_AVAL and evaluacion.post_aval_aprobado:
        raise ValidationError("Post-aval ya fue aprobado y no admite más cambios.")
    detalle.cumple, detalle.observacion = cumple, observacion
    detalle.fecha_revision, detalle.revisado_por = timezone.now(), usuario
    detalle.save()
    HistorialRevisionRequisito.objects.create(
        detalle=detalle, cumple=cumple, observacion=observacion, usuario=usuario
    )
    auditar(detalle, usuario, "requisito_revisado", f"Cumple: {cumple}")
    if not cumple and evaluacion.completo:
        evaluacion.completo = False
        evaluacion.save(update_fields=("completo", "updated_at"))


@transaction.atomic
def aprobar_pre_aval(evaluacion, usuario):
    evaluacion = EvaluacionExpediente.objects.select_for_update().get(pk=evaluacion.pk)
    if not evaluacion.proceso_id or not ProcesoContratacion.objects.filter(
        pk=evaluacion.proceso_id,
        estado__in=(ProcesoContratacion.RECLUTAMIENTO,
                    ProcesoContratacion.EXPEDIENTE_INCOMPLETO),
    ).exists():
        raise ValidationError("El proceso no se encuentra en reclutamiento.")
    if evaluacion.pre_aval_aprobado:
        raise ValidationError("Pre-aval ya fue aprobado.")
    if not evaluacion.detalles_fase(CatalogoRequisito.PRE_AVAL).exists():
        raise ValidationError("No hay requisitos activos de Pre-aval para aprobar.")
    if evaluacion.requisitos_obligatorios_pendientes(CatalogoRequisito.PRE_AVAL):
        raise ValidationError(
            "Debe completar todos los requisitos de Pre-aval para aprobar esta etapa."
        )
    evaluacion.pre_aval_aprobado = True
    evaluacion.pre_aval_aprobado_por = usuario
    evaluacion.pre_aval_aprobado_en = timezone.now()
    evaluacion.full_clean()
    evaluacion.save(update_fields=(
        "pre_aval_aprobado", "pre_aval_aprobado_por",
        "pre_aval_aprobado_en", "updated_at",
    ))
    auditar(evaluacion, usuario, "pre_aval_aprobado")
    return evaluacion


@transaction.atomic
def aprobar_post_aval(evaluacion, usuario):
    evaluacion = EvaluacionExpediente.objects.select_for_update().get(pk=evaluacion.pk)
    if not evaluacion.proceso_id or not ProcesoContratacion.objects.filter(
        pk=evaluacion.proceso_id,
        estado__in=(ProcesoContratacion.RECLUTAMIENTO,
                    ProcesoContratacion.EXPEDIENTE_INCOMPLETO),
    ).exists():
        raise ValidationError("El proceso no se encuentra en reclutamiento.")
    if not evaluacion.pre_aval_aprobado:
        raise ValidationError("Debe aprobar Pre-aval antes de aprobar Post-aval.")
    if evaluacion.post_aval_aprobado:
        raise ValidationError("Post-aval ya fue aprobado.")
    if not evaluacion.detalles_fase(CatalogoRequisito.POST_AVAL).exists():
        raise ValidationError("No hay requisitos activos de Post-aval para aprobar.")
    if evaluacion.requisitos_obligatorios_pendientes(CatalogoRequisito.POST_AVAL):
        raise ValidationError(
            "Debe completar todos los requisitos de Post-aval para aprobar esta etapa."
        )
    evaluacion.post_aval_aprobado = True
    evaluacion.post_aval_aprobado_por = usuario
    evaluacion.post_aval_aprobado_en = timezone.now()
    evaluacion.completo = True
    evaluacion.completado_por = usuario
    evaluacion.fecha_completado = timezone.now()
    evaluacion.full_clean()
    evaluacion.save()
    auditar(evaluacion, usuario, "post_aval_aprobado")
    auditar(evaluacion, usuario, "expediente_completado")
    return evaluacion


@transaction.atomic
def completar_evaluacion(evaluacion, usuario):
    evaluacion = EvaluacionExpediente.objects.select_for_update().get(pk=evaluacion.pk)
    if not (evaluacion.pre_aval_aprobado and evaluacion.post_aval_aprobado):
        raise ValidationError("Debe aprobar Pre-aval y Post-aval para completar el expediente.")
    evaluacion.completo, evaluacion.completado_por, evaluacion.fecha_completado = (
        True,
        usuario,
        timezone.now(),
    )
    evaluacion.full_clean()
    evaluacion.save()
    auditar(evaluacion, usuario, "expediente_completado")


@transaction.atomic
def marcar_elegible(proceso, usuario):
    proceso = ProcesoContratacion.objects.select_for_update().get(pk=proceso.pk)
    if proceso.estado == ProcesoContratacion.ELEGIBLE:
        raise ValidationError("El proceso ya se encuentra en Elegibles.")
    if proceso.estado not in (
        ProcesoContratacion.RECLUTAMIENTO,
        ProcesoContratacion.EXPEDIENTE_INCOMPLETO,
    ):
        raise ValidationError("El proceso no se encuentra en reclutamiento.")
    evaluacion = iniciar_evaluacion(proceso)
    if not (evaluacion.pre_aval_aprobado and evaluacion.post_aval_aprobado):
        raise ValidationError(
            "Pre-aval y Post-aval deben estar aprobados antes de marcar como elegible."
        )
    if evaluacion.requisitos_obligatorios_pendientes() or not evaluacion.completo:
        raise ValidationError("El expediente debe completarse antes de iniciar la contratación.")
    return registrar_transicion(proceso, usuario, "paso_elegible", ProcesoContratacion.ELEGIBLE)


@transaction.atomic
def guardar_contrato_029(empleado, contrato_form, info_form, usuario, proceso=None):
    if not puede_acceder(usuario, "gestion_empleados.manage_employee_contracts"):
        raise PermissionDenied
    if not proceso:
        raise ValidationError("Debe indicar el proceso de contratación.")
    proceso = ProcesoContratacion.objects.select_for_update().get(pk=proceso.pk)
    editando = bool(proceso.contrato_en_preparacion_id)
    if editando:
        permitido = (
            proceso.estado == ProcesoContratacion.CONTRATO_CREADO
            and contrato_form.instance.pk == proceso.contrato_en_preparacion_id
        )
    else:
        permitido = proceso.estado in (
            ProcesoContratacion.ELEGIBLE, ProcesoContratacion.CONTRATACION
        )
    if not permitido:
        raise ValidationError("El proceso no está disponible para crear un contrato.")
    if not hasattr(proceso, "evaluacion") or not proceso.evaluacion.completo:
        raise ValidationError("El expediente debe completarse antes de crear el contrato.")
    contrato = contrato_form.save(commit=False)
    contrato.empleado = empleado
    contrato.renglon = "029"
    contrato.estado_documental = Contrato.DOCUMENTO_CREADO
    contrato.estado = Contrato.ESTADO_BORRADOR
    contrato.activo = False
    contrato.creado_por = usuario
    contrato.save()
    info = info_form.save(commit=False)
    info.contrato, info.actualizado_por = contrato, usuario
    info.save()
    auditar(contrato, usuario, "contrato_029_creado")
    proceso.contrato_en_preparacion = contrato
    proceso.actualizado_por = usuario
    proceso.save(update_fields=(
        "contrato_en_preparacion", "actualizado_por", "updated_at"
    ))
    if editando:
        auditar(contrato, usuario, "contrato_editado")
    else:
        registrar_transicion(
            proceso, usuario, "contrato_creado",
            ProcesoContratacion.CONTRATO_CREADO,
        )
    return contrato


@transaction.atomic
def marcar_contrato_firmado(proceso, usuario):
    if not puede_acceder(usuario, "gestion_empleados.manage_employee_contracts"):
        raise PermissionDenied
    proceso = ProcesoContratacion.objects.select_for_update().get(pk=proceso.pk)
    if proceso.estado != ProcesoContratacion.CONTRATO_CREADO:
        raise ValidationError("Solo un contrato creado puede marcarse como firmado.")
    if not proceso.contrato_en_preparacion_id:
        raise ValidationError("El proceso no tiene un contrato creado.")
    contrato = Contrato.objects.select_for_update().get(
        pk=proceso.contrato_en_preparacion_id
    )
    if contrato.estado == Contrato.ESTADO_RESCINDIDO:
        raise ValidationError("Un contrato rescindido no puede marcarse como firmado.")
    if contrato.estado_documental != Contrato.DOCUMENTO_CREADO:
        raise ValidationError("El contrato no se encuentra en estado Creado.")
    contrato.estado_documental = Contrato.DOCUMENTO_FIRMADO
    contrato.firmado_por = usuario
    contrato.fecha_firma = timezone.now()
    contrato.save(update_fields=(
        "estado_documental", "firmado_por", "fecha_firma", "estado",
        "activo", "updated_at",
    ))
    auditar(contrato, usuario, "contrato_firmado")
    return registrar_transicion(
        proceso, usuario, "contrato_firmado", ProcesoContratacion.CONTRATO_FIRMADO
    )


@transaction.atomic
def aprobar_contrato(proceso, usuario):
    if not puede_acceder(usuario, "gestion_empleados.manage_employee_contracts"):
        raise PermissionDenied
    proceso = ProcesoContratacion.objects.select_for_update().get(pk=proceso.pk)
    if proceso.estado != ProcesoContratacion.CONTRATO_FIRMADO:
        raise ValidationError("El contrato debe estar firmado antes de aprobarse.")
    if not proceso.contrato_en_preparacion_id:
        raise ValidationError("El proceso no tiene un contrato para aprobar.")
    contrato = Contrato.objects.select_for_update().get(
        pk=proceso.contrato_en_preparacion_id
    )
    if contrato.estado_documental != Contrato.DOCUMENTO_FIRMADO:
        raise ValidationError("El contrato debe estar firmado antes de aprobarse.")
    if not hasattr(contrato, "informacion_029"):
        raise ValidationError("Faltan los datos obligatorios del contrato 029.")

    empleado = None
    if proceso.empleado_id:
        empleado = Empleado.objects.select_for_update().get(pk=proceso.empleado_id)
    else:
        if not proceso.postulante_id:
            raise ValidationError("El proceso no tiene una persona vinculada.")
        postulante = Postulante.objects.select_for_update().get(pk=proceso.postulante_id)
        empleado = Empleado.objects.select_for_update().filter(dpi=postulante.cui).first()
        if empleado is None:
            empleado = Empleado.objects.create(
                dpi=postulante.cui, nombres=postulante.nombres,
                apellidos=postulante.apellidos, tipoc="029", user=usuario,
            )
        postulante.empleado = empleado
        postulante.save(update_fields=("empleado", "updated_at"))

    incompatibles = Contrato.objects.select_for_update().filter(
        empleado=empleado, activo=True,
        fecha_inicio__lte=contrato.fecha_vencimiento,
        fecha_vencimiento__gte=contrato.fecha_inicio,
    ).exclude(pk=contrato.pk)
    if incompatibles.exists():
        raise ValidationError("El empleado ya tiene un contrato activo incompatible.")

    contrato.empleado = empleado
    contrato.estado_documental = Contrato.DOCUMENTO_APROBADO
    contrato.aprobado_por = usuario
    contrato.fecha_aprobacion = timezone.now()
    contrato.save()
    proceso.empleado = empleado
    proceso.contrato_resultante = contrato
    proceso.contrato_en_preparacion = None
    proceso.actualizado_por = usuario
    proceso.save(update_fields=(
        "empleado", "contrato_resultante", "contrato_en_preparacion",
        "actualizado_por", "updated_at",
    ))
    auditar(contrato, usuario, "contrato_aprobado")
    return registrar_transicion(
        proceso, usuario, "contrato_aprobado", ProcesoContratacion.CONTRATADO
    )


@transaction.atomic
def iniciar_contratacion(proceso, usuario):
    if not puede_acceder(usuario, "gestion_empleados.manage_employee_contracts"):
        raise PermissionDenied
    proceso_bloqueado = ProcesoContratacion.objects.select_for_update().get(
        pk=proceso.pk
    )
    if proceso_bloqueado.estado == ProcesoContratacion.CONTRATACION:
        return proceso_bloqueado
    if proceso_bloqueado.estado != ProcesoContratacion.ELEGIBLE:
        raise ValidationError(
            "El expediente debe completarse antes de iniciar la contratación."
        )
    evaluacion = EvaluacionExpediente.objects.filter(
        proceso_id=proceso_bloqueado.pk, completo=True
    ).first()
    if evaluacion is None or evaluacion.requisitos_obligatorios_pendientes():
        raise ValidationError(
            "El expediente debe completarse antes de iniciar la contratación."
        )
    return registrar_transicion(
        proceso_bloqueado,
        usuario,
        "inicio_contratacion",
        ProcesoContratacion.CONTRATACION,
    )


@transaction.atomic
def guardar_control_mensual(form, usuario):
    control = form.save(commit=False)
    control.responsable = usuario
    control.fecha_revision = timezone.now()
    control.full_clean()
    control.save()
    auditar(control, usuario, "control_mensual_guardado")
    return control


@transaction.atomic
def guardar_documento(expediente, form, usuario):
    documento = form.save(commit=False)
    documento.expediente = expediente
    documento.usuario = usuario
    documento.full_clean()
    documento.save()
    auditar(expediente, usuario, "documento_cargado", documento.tipo.nombre)
    return documento


@transaction.atomic
def guardar_caso(form, usuario):
    caso = form.save(commit=False)
    if not caso.pk:
        caso.creado_por = usuario
    caso.actualizado_por = usuario
    caso.full_clean()
    caso.save()
    auditar(caso, usuario, "caso_judicial_guardado")
    return caso


@transaction.atomic
def guardar_actuacion(caso, form, usuario):
    actuacion = form.save(commit=False)
    actuacion.caso, actuacion.usuario = caso, usuario
    actuacion.full_clean()
    actuacion.save()
    caso.fecha_ultima_actuacion = actuacion.fecha
    caso.actualizado_por = usuario
    caso.save(update_fields=("fecha_ultima_actuacion", "actualizado_por", "updated_at"))
    auditar(caso, usuario, "actuacion_judicial_agregada", actuacion.tipo_actuacion)
    return actuacion
