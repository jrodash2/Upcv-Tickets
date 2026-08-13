from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType

from empleados_app.models import Contrato

from .models import RegistroAuditoria


@receiver(post_save, sender=Contrato)
def auditar_rescision_contrato(sender, instance, **kwargs):
    if instance.estado != Contrato.ESTADO_RESCINDIDO or not instance.rescindido_por_id:
        return
    content_type = ContentType.objects.get_for_model(instance)
    RegistroAuditoria.objects.get_or_create(
        content_type=content_type,
        object_id=instance.pk,
        accion="contrato_rescindido",
        defaults={
            "usuario": instance.rescindido_por,
            "detalle": f"Fecha: {instance.fecha_rescision}; motivo: {instance.motivo_rescision or ''}",
        },
    )
