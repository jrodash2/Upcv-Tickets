"""Copia opcional e idempotente del historial anterior, sin cargar otras apps."""
import json

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from scompras_app.models import AuditoriaSolicitudCompra, SolicitudCompra


class Command(BaseCommand):
    help = 'Copia auditorías anteriores de Compras si su tabla existe; nunca modifica el origen.'

    def add_arguments(self, parser):
        parser.add_argument('--database', default='default')

    def handle(self, *args, **options):
        alias = options['database']
        connection = connections[alias]
        origen = 'gestion_empleados_registroauditoria'
        if origen not in connection.introspection.table_names():
            self.stdout.write('No existe la tabla de auditoría anterior. No es necesario importar registros.')
            return
        quote = connection.ops.quote_name
        sql = (
            f'SELECT r.id, r.usuario_id, r.fecha, r.object_id, r.detalle '
            f'FROM {quote(origen)} r INNER JOIN {quote("django_content_type")} c '
            'ON r.content_type_id = c.id '
            'WHERE c.app_label = %s AND c.model = %s AND r.accion = %s ORDER BY r.id'
        )
        creados = existentes = 0
        with transaction.atomic(using=alias):
            with connection.cursor() as cursor:
                cursor.execute(sql, ['scompras_app', 'solicitudcompra', 'scompras_edicion_administrativa'])
                while True:
                    rows = cursor.fetchmany(200)
                    if not rows:
                        break
                    for pk, usuario_id, fecha, solicitud_pk, detalle in rows:
                        if AuditoriaSolicitudCompra.objects.using(alias).filter(registro_origen_id=pk).exists():
                            existentes += 1
                            continue
                        try:
                            datos = json.loads(detalle)
                            anterior = self.parse_fecha(datos['fecha_anterior'])
                            nueva = self.parse_fecha(datos['fecha_nuevo'])
                            solicitud_id = SolicitudCompra.objects.using(alias).filter(pk=solicitud_pk).values_list('pk', flat=True).first()
                            defaults = dict(
                                solicitud_id=solicitud_id, solicitud_pk=solicitud_pk,
                                usuario_id=usuario_id, fecha=fecha, correlativo=datos['correlativo'],
                                fecha_anterior=anterior, fecha_nueva=nueva,
                                estado_anterior=datos['estado_anterior'], estado_nuevo=datos['estado_nuevo'],
                                observacion=f'Importada del registro de auditoría anterior #{pk}.',
                            )
                            # Validar los datos sin consultar FK/unique en otro alias.
                            candidato = AuditoriaSolicitudCompra(registro_origen_id=pk, **defaults)
                            candidato.clean_fields(exclude=['solicitud', 'usuario', 'registro_origen_id'])
                        except (KeyError, ValueError, TypeError, ValidationError) as exc:
                            raise CommandError(
                                f'El registro anterior #{pk} tiene datos inválidos. '
                                'Se revierte esta importación; el origen no se ha modificado.'
                            ) from exc
                        _, creado = AuditoriaSolicitudCompra.objects.using(alias).get_or_create(
                            registro_origen_id=pk, defaults=defaults,
                        )
                        creados += int(creado)
                        existentes += int(not creado)
        self.stdout.write(self.style.SUCCESS(
            f'Auditorías importadas: {creados}. Ya existentes: {existentes}. El origen se conserva íntegro.'
        ))

    @staticmethod
    def parse_fecha(value):
        fecha = parse_datetime(value)
        if fecha is None:
            raise ValueError('Fecha ISO no válida')
        if settings.USE_TZ and timezone.is_naive(fecha):
            fecha = timezone.make_aware(fecha, timezone.get_default_timezone())
        return fecha
