import json
import subprocess
import sys
from datetime import datetime
from io import StringIO

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command, CommandError
from django.db import connection
from django.test import TestCase
from django.utils import timezone

from .models import AuditoriaSolicitudCompra, Departamento, Seccion, SolicitudCompra


class ImportacionAuditoriaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('importador_auditoria')
        dep = Departamento.objects.create(id_departamento='audit-import', nombre='DAF', abreviatura='DAF')
        sec = Seccion.objects.create(nombre='Almacén', departamento=dep, abreviatura='SALM')
        cls.solicitud = SolicitudCompra.objects.bulk_create([
            SolicitudCompra(usuario=cls.user, seccion=sec, descripcion='Auditoría', codigo_correlativo='UPCV-DAF-SALM-001-2026')
        ])[0]
        cls.fecha = timezone.make_aware(datetime(2026, 2, 10, 12, 30))

    def origen_temporal(self):
        # Tabla de prueba en pg_temp: nunca modifica la tabla real si estuviera instalada.
        with connection.cursor() as cursor:
            cursor.execute('CREATE TEMPORARY TABLE gestion_empleados_registroauditoria ('
                           'id bigint PRIMARY KEY, usuario_id integer, fecha timestamp with time zone, '
                           'object_id bigint, detalle text, content_type_id integer, accion varchar(80))')

    def insertar(self, pk=1, solicitud_pk=None, detalle=None, accion='scompras_edicion_administrativa'):
        datos = {
            'correlativo': self.solicitud.codigo_correlativo,
            'fecha_anterior': self.fecha.isoformat(), 'fecha_nuevo': self.fecha.isoformat(),
            'estado_anterior': 'Creada', 'estado_nuevo': 'Finalizada',
        }
        with connection.cursor() as cursor:
            cursor.execute('INSERT INTO gestion_empleados_registroauditoria '
                           '(id, usuario_id, fecha, object_id, detalle, content_type_id, accion) '
                           'VALUES (%s, %s, %s, %s, %s, %s, %s)', [
                               pk, self.user.pk, self.fecha, solicitud_pk or self.solicitud.pk,
                               json.dumps(datos) if detalle is None else detalle,
                               ContentType.objects.get_for_model(SolicitudCompra).pk, accion,
                           ])

    def test_sin_tabla_anterior_no_requiere_aplicacion(self):
        from unittest.mock import patch
        with patch.object(connection.introspection, 'table_names', return_value=[]):
            output = StringIO()
            call_command('importar_auditoria_solicitudes', stdout=output)
        self.assertIn('No es necesario', output.getvalue())
        self.assertFalse(AuditoriaSolicitudCompra.objects.exists())

    def test_copia_fiel_idempotente_sin_modificar_origen(self):
        self.origen_temporal()
        self.insertar()
        self.insertar(pk=2, accion='otra_accion')
        call_command('importar_auditoria_solicitudes', stdout=StringIO())
        call_command('importar_auditoria_solicitudes', stdout=StringIO())
        registro = AuditoriaSolicitudCompra.objects.get()
        self.assertEqual(registro.registro_origen_id, 1)
        self.assertEqual(registro.solicitud, self.solicitud)
        self.assertEqual(registro.solicitud_pk, self.solicitud.pk)
        self.assertEqual(registro.usuario, self.user)
        self.assertEqual(registro.fecha, self.fecha)
        self.assertEqual(registro.fecha_anterior, self.fecha)
        self.assertEqual(registro.estado_nuevo, 'Finalizada')
        with connection.cursor() as cursor:
            cursor.execute('SELECT count(*) FROM gestion_empleados_registroauditoria')
            self.assertEqual(cursor.fetchone()[0], 2)

    def test_registro_huerfano_se_conserva(self):
        self.origen_temporal()
        self.insertar(solicitud_pk=99999999)
        call_command('importar_auditoria_solicitudes', stdout=StringIO())
        registro = AuditoriaSolicitudCompra.objects.get()
        self.assertIsNone(registro.solicitud)
        self.assertEqual(registro.solicitud_pk, 99999999)
        self.assertEqual(registro.correlativo, self.solicitud.codigo_correlativo)

    def test_datos_invalidos_revierten_toda_importacion(self):
        self.origen_temporal()
        self.insertar()
        self.insertar(pk=2, detalle='no es JSON')
        with self.assertRaises(CommandError):
            call_command('importar_auditoria_solicitudes', stdout=StringIO())
        self.assertFalse(AuditoriaSolicitudCompra.objects.exists())
        with connection.cursor() as cursor:
            cursor.execute('SELECT count(*) FROM gestion_empleados_registroauditoria')
            self.assertEqual(cursor.fetchone()[0], 2)

    def test_eliminar_solicitud_no_borra_historial_ni_cambia_flujo(self):
        registro = AuditoriaSolicitudCompra.objects.create(
            solicitud=self.solicitud, solicitud_pk=self.solicitud.pk, usuario=self.user,
            correlativo=self.solicitud.codigo_correlativo, fecha_anterior=self.fecha,
            fecha_nueva=self.fecha, estado_anterior='Creada', estado_nuevo='Finalizada',
        )
        pk = self.solicitud.pk
        self.solicitud.delete()
        registro.refresh_from_db()
        self.assertIsNone(registro.solicitud)
        self.assertEqual(registro.solicitud_pk, pk)
        self.assertEqual(registro.correlativo, 'UPCV-DAF-SALM-001-2026')

    def test_carga_real_con_imports_de_otras_apps_bloqueados(self):
        script = '''
import importlib.abc
import os
import sys
class BloquearApps(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'gestion_empleados', 'empleados_app', 'tickets_app', 'diplomas_app', 'app_backup'}:
            raise ModuleNotFoundError('Aplicación excluida en esta prueba: ' + fullname)
sys.meta_path.insert(0, BloquearApps())
os.environ['DJANGO_SETTINGS_MODULE'] = 'scompras_app.standalone_test_settings'
import django
django.setup()
from django.core.management import call_command
call_command('check')
from scompras_app import solicitud_admin, urls, views
assert solicitud_admin.AuditoriaSolicitudCompra._meta.app_label == 'scompras_app'
'''
        result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('no issues', result.stdout)
