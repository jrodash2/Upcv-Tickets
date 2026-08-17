from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
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
    empleado = Empleado.objects.filter(dpi=postulante.cui).first()
    if empleado:
        postulante.empleado = empleado
        postulante.nombres, postulante.apellidos = empleado.nombres, empleado.apellidos
    anterior = Postulante.objects.select_for_update().filter(pk=postulante.pk).first()
    postulante.responsable = usuario
    if not postulante.pk:
        postulante.resultado_confiabilidad = Postulante.PRUEBA_PENDIENTE
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
    if not postulante.procesos_contratacion.filter(
        estado__in=ProcesoContratacion.ESTADOS_ABIERTOS
    ).exists():
        proceso = ProcesoContratacion.objects.create(
            tipo_proceso=ProcesoContratacion.INGRESO,
            estado=ProcesoContratacion.PRESELECCION,
            empleado=postulante.empleado, postulante=postulante,
            responsable=usuario, creado_por=usuario, actualizado_por=usuario,
        )
        registrar_transicion(proceso, usuario, "proceso_creado")
    return postulante


@transaction.atomic
def registrar_prueba_confiabilidad(postulante, resultado, observacion, usuario):
    if resultado not in dict(Postulante.RESULTADOS_PRUEBA):
        raise ValidationError("Resultado de prueba inválido.")
    postulante.resultado_confiabilidad = resultado
    postulante.observacion_confiabilidad = observacion
    postulante.fecha_evaluacion_confiabilidad = timezone.now()
    postulante.evaluado_por = usuario
    postulante.save()
    proceso = postulante.procesos_contratacion.filter(
        estado__in=(ProcesoContratacion.PRESELECCION,
                    ProcesoContratacion.PRUEBA_CONFIABILIDAD)
    ).order_by("-created_at").first()
    if not proceso:
        raise ValidationError("No existe un proceso abierto en preselección.")
    nuevo = (ProcesoContratacion.NO_APROBADO
             if resultado == Postulante.PRUEBA_NO_APROBADA
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
        raise ValidationError("El proceso ya se encuentra en Reclutamiento y Selección.")
    if proceso_bloqueado.estado == ProcesoContratacion.CANCELADO:
        raise ValidationError("Un proceso cancelado no puede avanzar a reclutamiento.")
    if proceso_bloqueado.estado == ProcesoContratacion.CONTRATADO:
        raise ValidationError("El proceso ya fue contratado y no puede volver a reclutamiento.")
    if proceso_bloqueado.estado == ProcesoContratacion.NO_APROBADO:
        raise ValidationError("La Prueba de Confiabilidad no fue aprobada.")
    if proceso_bloqueado.estado not in (
        ProcesoContratacion.PRESELECCION,
        ProcesoContratacion.PRUEBA_CONFIABILIDAD,
    ):
        raise ValidationError("El proceso no se encuentra en una etapa válida para avanzar.")

    postulante = None
    if proceso_bloqueado.postulante_id:
        postulante = Postulante.objects.get(pk=proceso_bloqueado.postulante_id)
    if proceso_bloqueado.tipo_proceso in (
        ProcesoContratacion.INGRESO,
        ProcesoContratacion.REINGRESO,
    ) and (
        postulante is None
        or postulante.resultado_confiabilidad != Postulante.PRUEBA_APROBADA
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
        postulante.resultado_confiabilidad = Postulante.PRUEBA_PENDIENTE
        postulante.fecha_evaluacion_confiabilidad = None
        postulante.evaluado_por = None
        postulante.observacion_confiabilidad = ""
        postulante.save()
        estado = ProcesoContratacion.PRESELECCION
    proceso = ProcesoContratacion.objects.create(
        tipo_proceso=tipo, estado=estado, empleado=empleado, postulante=postulante,
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
        proceso.postulante = postulante
        proceso.save(update_fields=("postulante", "updated_at"))
    evaluacion, _ = EvaluacionExpediente.objects.get_or_create(
        proceso=proceso, defaults={"postulante": proceso.postulante}
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
def convertir_postulante_en_empleado(postulante, usuario):
    # Bloquea exclusivamente la fila de Postulante. Como `empleado` es nullable,
    # incluirlo con select_related generaría un LEFT OUTER JOIN y PostgreSQL
    # rechazaría el FOR UPDATE sobre el lado nullable de ese join.
    postulante = Postulante.objects.select_for_update().get(pk=postulante.pk)
    if postulante.empleado_id:
        empleado = Empleado.objects.get(pk=postulante.empleado_id)
        empleado._postulante_ya_convertido = True
        return empleado
    empleado, _ = Empleado.objects.get_or_create(
        dpi=postulante.cui,
        defaults={
            "nombres": postulante.nombres,
            "apellidos": postulante.apellidos,
            "tipoc": "029",
            "user": usuario,
        },
    )
    postulante.empleado = empleado
    postulante.save(update_fields=("empleado", "updated_at"))
    empleado._postulante_ya_convertido = False
    return empleado


@transaction.atomic
def revisar_requisito(detalle, cumple, observacion, usuario):
    detalle.cumple, detalle.observacion = cumple, observacion
    detalle.fecha_revision, detalle.revisado_por = timezone.now(), usuario
    detalle.save()
    HistorialRevisionRequisito.objects.create(
        detalle=detalle, cumple=cumple, observacion=observacion, usuario=usuario
    )
    auditar(detalle, usuario, "requisito_revisado", f"Cumple: {cumple}")
    if not cumple and detalle.evaluacion.completo:
        detalle.evaluacion.completo = False
        detalle.evaluacion.save(update_fields=("completo", "updated_at"))


@transaction.atomic
def completar_evaluacion(evaluacion, usuario):
    evaluacion = EvaluacionExpediente.objects.select_for_update().get(pk=evaluacion.pk)
    if evaluacion.requisitos_obligatorios_pendientes():
        raise ValidationError("Existen requisitos obligatorios pendientes.")
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
    if evaluacion.requisitos_obligatorios_pendientes():
        raise ValidationError("El expediente debe completarse antes de iniciar la contratación.")
    if not evaluacion.completo:
        completar_evaluacion(evaluacion, usuario)
    return registrar_transicion(proceso, usuario, "paso_elegible", ProcesoContratacion.ELEGIBLE)


@transaction.atomic
def guardar_contrato_029(empleado, contrato_form, info_form, usuario, proceso=None):
    if not puede_acceder(usuario, "gestion_empleados.manage_employee_contracts"):
        raise PermissionDenied
    contrato = contrato_form.save(commit=False)
    contrato.empleado, contrato.renglon = empleado, "029"
    if proceso:
        proceso = ProcesoContratacion.objects.select_for_update().get(pk=proceso.pk)
    activos = (
        Contrato.objects.select_for_update()
        .filter(empleado=empleado, activo=True,
                fecha_inicio__lte=contrato.fecha_vencimiento,
                fecha_vencimiento__gte=contrato.fecha_inicio)
        .exclude(pk=contrato.pk)
    )
    if activos.exists():
        raise ValidationError("El empleado ya tiene un contrato activo.")
    if not proceso or proceso.empleado_id != empleado.pk or proceso.estado not in (
        ProcesoContratacion.ELEGIBLE, ProcesoContratacion.CONTRATACION
    ) or not proceso.evaluacion.completo:
        raise ValidationError("El expediente debe completarse antes de iniciar la contratación.")
    contrato.save()
    info = info_form.save(commit=False)
    info.contrato, info.actualizado_por = contrato, usuario
    info.save()
    auditar(contrato, usuario, "contrato_029_creado")
    proceso.contrato_resultante = contrato
    proceso.save(update_fields=("contrato_resultante", "updated_at"))
    registrar_transicion(proceso, usuario, "contrato_generado", ProcesoContratacion.CONTRATADO)
    return contrato


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
