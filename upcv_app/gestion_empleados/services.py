from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from empleados_app.models import Contrato, Empleado

from .models import (CatalogoRequisito, DetalleEvaluacionRequisito, EvaluacionExpediente,
                     HistorialEstadoPostulante, HistorialRevisionRequisito, Postulante)
from .permissions import puede_acceder


@transaction.atomic
def guardar_postulante(form, usuario):
    postulante = form.save(commit=False)
    empleado = Empleado.objects.filter(dpi=postulante.cui).first()
    if empleado:
        postulante.empleado = empleado
        postulante.nombres, postulante.apellidos = empleado.nombres, empleado.apellidos
    anterior = Postulante.objects.select_for_update().filter(pk=postulante.pk).first()
    postulante.responsable = usuario
    postulante.full_clean(); postulante.save(); form.save_m2m()
    if not anterior or anterior.estado_tdr_id != postulante.estado_tdr_id:
        HistorialEstadoPostulante.objects.create(postulante=postulante, estado_anterior=anterior.estado_tdr if anterior else None, estado_nuevo=postulante.estado_tdr, usuario=usuario)
    return postulante


@transaction.atomic
def iniciar_evaluacion(postulante):
    evaluacion, _ = EvaluacionExpediente.objects.get_or_create(postulante=postulante)
    existentes = set(evaluacion.detalles.values_list("requisito_id", flat=True))
    DetalleEvaluacionRequisito.objects.bulk_create([DetalleEvaluacionRequisito(evaluacion=evaluacion, requisito=r) for r in CatalogoRequisito.objects.filter(activo=True).exclude(pk__in=existentes)])
    return evaluacion


@transaction.atomic
def convertir_postulante_en_empleado(postulante, usuario):
    postulante = Postulante.objects.select_for_update().select_related("empleado").get(pk=postulante.pk)
    if postulante.empleado_id:
        return postulante.empleado
    empleado, _ = Empleado.objects.get_or_create(dpi=postulante.cui, defaults={"nombres": postulante.nombres, "apellidos": postulante.apellidos, "tipoc": "029", "user": usuario})
    postulante.empleado = empleado; postulante.save(update_fields=("empleado", "updated_at"))
    return empleado


@transaction.atomic
def revisar_requisito(detalle, cumple, observacion, usuario):
    detalle.cumple, detalle.observacion = cumple, observacion
    detalle.fecha_revision, detalle.revisado_por = timezone.now(), usuario
    detalle.save()
    HistorialRevisionRequisito.objects.create(detalle=detalle, cumple=cumple, observacion=observacion, usuario=usuario)
    if not cumple and detalle.evaluacion.completo:
        detalle.evaluacion.completo = False; detalle.evaluacion.save(update_fields=("completo", "updated_at"))


@transaction.atomic
def completar_evaluacion(evaluacion, usuario):
    evaluacion = EvaluacionExpediente.objects.select_for_update().get(pk=evaluacion.pk)
    if evaluacion.requisitos_obligatorios_pendientes():
        raise ValidationError("Existen requisitos obligatorios pendientes.")
    evaluacion.completo, evaluacion.completado_por, evaluacion.fecha_completado = True, usuario, timezone.now()
    evaluacion.full_clean(); evaluacion.save()


@transaction.atomic
def guardar_contrato_029(empleado, contrato_form, info_form, usuario):
    if not puede_acceder(usuario, "gestion_empleados.manage_employee_contracts"):
        raise PermissionDenied
    contrato = contrato_form.save(commit=False)
    contrato.empleado, contrato.renglon = empleado, "029"
    activos = Contrato.objects.select_for_update().filter(empleado=empleado, activo=True).exclude(pk=contrato.pk)
    if activos.exists():
        raise ValidationError("El empleado ya tiene un contrato activo.")
    contrato.save()
    info = info_form.save(commit=False); info.contrato, info.actualizado_por = contrato, usuario; info.save()
    return contrato
