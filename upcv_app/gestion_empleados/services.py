from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from empleados_app.models import Contrato, Empleado

from .models import (
    CatalogoRequisito,
    DetalleEvaluacionRequisito,
    EvaluacionExpediente,
    HistorialEstadoPostulante,
    HistorialRevisionRequisito,
    Postulante,
    RegistroAuditoria,
)
from .permissions import puede_acceder


def auditar(objeto, usuario, accion, detalle=""):
    return RegistroAuditoria.objects.create(
        objeto=objeto, usuario=usuario, accion=accion, detalle=detalle
    )


@transaction.atomic
def guardar_postulante(form, usuario):
    postulante = form.save(commit=False)
    empleado = Empleado.objects.filter(dpi=postulante.cui).first()
    if empleado:
        postulante.empleado = empleado
        postulante.nombres, postulante.apellidos = empleado.nombres, empleado.apellidos
    anterior = Postulante.objects.select_for_update().filter(pk=postulante.pk).first()
    postulante.responsable = usuario
    postulante.full_clean()
    postulante.save()
    form.save_m2m()
    if not anterior or anterior.estado_tdr_id != postulante.estado_tdr_id:
        HistorialEstadoPostulante.objects.create(
            postulante=postulante,
            estado_anterior=anterior.estado_tdr if anterior else None,
            estado_nuevo=postulante.estado_tdr,
            usuario=usuario,
        )
    auditar(postulante, usuario, "postulante_guardado")
    return postulante


@transaction.atomic
def iniciar_evaluacion(postulante):
    evaluacion, _ = EvaluacionExpediente.objects.get_or_create(postulante=postulante)
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
    postulante = (
        Postulante.objects.select_for_update()
        .select_related("empleado")
        .get(pk=postulante.pk)
    )
    if postulante.empleado_id:
        return postulante.empleado
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
def guardar_contrato_029(empleado, contrato_form, info_form, usuario):
    if not puede_acceder(usuario, "gestion_empleados.manage_employee_contracts"):
        raise PermissionDenied
    contrato = contrato_form.save(commit=False)
    contrato.empleado, contrato.renglon = empleado, "029"
    activos = (
        Contrato.objects.select_for_update()
        .filter(empleado=empleado, activo=True)
        .exclude(pk=contrato.pk)
    )
    if activos.exists():
        raise ValidationError("El empleado ya tiene un contrato activo.")
    contrato.save()
    info = info_form.save(commit=False)
    info.contrato, info.actualizado_por = contrato, usuario
    info.save()
    auditar(contrato, usuario, "contrato_029_creado")
    return contrato


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
