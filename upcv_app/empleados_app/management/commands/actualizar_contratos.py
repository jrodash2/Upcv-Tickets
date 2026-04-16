from django.core.management.base import BaseCommand
from django.utils.timezone import now
from empleados_app.models import Contrato

class Command(BaseCommand):
    help = 'Actualizar contratos vencidos y marcar activos como False'

    def handle(self, *args, **kwargs):
        today = now().date()
        contratos_vencidos = Contrato.objects.filter(
            estado=Contrato.ESTADO_ACTIVO,
            fecha_vencimiento__lte=today
        )
        count = contratos_vencidos.update(
            activo=False,
            estado=Contrato.ESTADO_VENCIDO
        )
        self.stdout.write(f'Se actualizaron {count} contratos vencidos.')
# comando python manage.py actualizar_contratos
