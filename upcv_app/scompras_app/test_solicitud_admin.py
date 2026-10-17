from datetime import datetime
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.db import DatabaseError, connection
from django.test import Client, TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from .models import (
    AuditoriaSolicitudCompra, CDP, Departamento, Insumo, InsumoSolicitud, KardexPresupuesto,
    PresupuestoAnual, PresupuestoRenglon, ProcesoCompraPaso, Seccion,
    SolicitudCompra, SolicitudPasoEstado, TipoProcesoCompra,
)
from .solicitud_admin import SIN_SECCION


class AdministracionSolicitudesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        grupo, _ = Group.objects.get_or_create(name='Administrador')
        cls.admin = User.objects.create_user('admin_solicitudes')
        cls.admin.groups.add(grupo)
        cls.otro = User.objects.create_user('sin_grupo')
        cls.superuser = User.objects.create_user('super_sin_grupo', is_superuser=True, is_staff=True)
        cls.departamento = Departamento.objects.create(id_departamento='admin-test', nombre='Financiero', abreviatura='CAMBIADA')
        cls.seccion = Seccion.objects.create(nombre='Almacén', departamento=cls.departamento, abreviatura='ACTUAL')
        cls.fecha = timezone.make_aware(datetime(2026, 2, 15, 10, 35, 12, 123456))
        codigos = [
            'UPCV-DAF-SALM-037-2026', 'UPCV-DAF-SALM-037-2025',
            'UPCV-DAF-SALM-002-2026', 'UPCV-DAF-SALM-125-2026',
            'UPCV-DAF-001-2026', 'UPCV-DTI-SIST-001-2026', 'SOL/2020/008',
        ]
        cls.solicitudes = SolicitudCompra.objects.bulk_create([
            SolicitudCompra(seccion=cls.seccion, usuario=cls.otro, descripcion='Insumos de oficina',
                            fecha_solicitud=cls.fecha, codigo_correlativo=codigo)
            for codigo in codigos
        ])
        cls.solicitud = cls.solicitudes[0]
        cls.insumo = Insumo.objects.create(renglon=100, codigo_insumo='100', nombre='<script>insumo</script>',
            nombre_presentacion='Caja', cantidad_unidad_presentacion='10', codigo_presentacion='ADM-100', caracteristicas='Papel')
        cls.detalle = InsumoSolicitud.objects.create(solicitud=cls.solicitud, insumo=cls.insumo,
            cantidad=4, caracteristica_especial='Azul', renglon='100')

    def setUp(self):
        self.client.force_login(self.admin)

    def url(self, accion, pk=None):
        return reverse('scompras:administracion_solicitudes' + ('_' + accion if accion else ''), args=[pk] if pk else [])

    def seleccion(self, **extra):
        return {'institucion': 'UPCV', 'departamento': 'DAF', 'seccion': 'SALM', 'numero': '037', 'anio': '2026', **extra}

    def detalle_actual(self):
        response = self.client.get(self.url('detalle'), self.seleccion())
        self.assertEqual(response.status_code, 200)
        return response.json()['solicitud']

    def guardar(self, **extra):
        data = self.detalle_actual()
        return self.client.post(self.url('actualizar', self.solicitud.pk), {
            'fecha_solicitud': data['fecha_solicitud'], 'estado': data['estado'], 'version': data['version'], **extra,
        })

    def opciones(self, nivel, **params):
        response = self.client.get(self.url('opciones'), {'nivel': nivel, **params})
        self.assertEqual(response.status_code, 200)
        return [item['value'] for item in response.json()['opciones']]

    def test_administrador_accede_y_menu_activo(self):
        response = self.client.get(self.url(''))
        self.assertContains(response, 'Administración de Solicitudes de Compra')
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, 'administracion_solicitudes.js')
        self.assertContains(response, 'administracion_solicitudes.css')
        self.assertContains(response, 'id="admin-nav-toggle"')
        self.assertNotContains(response, 'shopping-cart')

    def test_todos_endpoints_restringidos_incluso_superusuario_sin_grupo(self):
        for usuario in [None, self.otro, self.superuser]:
            self.client.logout()
            if usuario:
                self.client.force_login(usuario)
            for accion, pk in [('', None), ('opciones', None), ('detalle', None), ('historial', self.solicitud.pk)]:
                with self.subTest(usuario=usuario, accion=accion):
                    self.assertEqual(self.client.get(self.url(accion, pk)).status_code, 403)
            self.assertEqual(self.client.post(self.url('actualizar', self.solicitud.pk), {}).status_code, 403)
        self.assertFalse(AuditoriaSolicitudCompra.objects.all().exists())

    def test_menu_no_aparece_sin_grupo(self):
        self.client.force_login(self.otro)
        response = self.client.get(reverse('scompras:detalle_solicitud', args=[self.solicitud.pk]))
        self.assertNotContains(response, self.url(''), status_code=403)

    def test_selectores_usan_codigo_historico_no_abreviatura_actual(self):
        self.assertEqual(self.opciones('institucion'), ['UPCV'])
        self.assertEqual(self.opciones('departamento', institucion='UPCV'), ['DAF', 'DTI'])
        self.assertEqual(self.opciones('departamento', institucion='NO_EXISTE'), [])
        self.assertEqual(self.opciones('seccion', institucion='UPCV', departamento='DTI'), ['SIST'])

    def test_numeros_distintos_ordenados_y_con_ceros(self):
        valores = self.opciones('numero', institucion='UPCV', departamento='DAF', seccion='SALM')
        self.assertEqual(valores, ['002', '037', '125'])
        self.assertEqual(self.opciones('anio', institucion='UPCV', departamento='DAF', seccion='SALM', numero='037'), ['2025', '2026'])
        self.assertEqual(self.opciones('anio', institucion='UPCV', departamento='DAF', seccion='SALM', numero='002'), ['2026'])

    def test_prefijos_faltantes_y_niveles_invalidos(self):
        for params in [{'nivel': 'numero'}, {'nivel': 'invalido'}]:
            self.assertEqual(self.client.get(self.url('opciones'), params).status_code, 400)

    def test_formato_cuatro_componentes_y_historico_irregular(self):
        self.assertIn(SIN_SECCION, self.opciones('seccion', institucion='UPCV', departamento='DAF'))
        response = self.client.get(self.url('detalle'), self.seleccion(seccion=SIN_SECCION, numero='001'))
        self.assertEqual(response.json()['solicitud']['correlativo'], 'UPCV-DAF-001-2026')
        response = self.client.get(self.url('detalle'), {'historico': 'SOL/2020/008'})
        self.assertEqual(response.json()['solicitud']['id'], self.solicitudes[-1].pk)
        self.assertEqual(self.client.get(self.url('opciones')).json()['historicos'], 1)

    def test_inexistentes_no_reconstruyen_solicitud_ficticia(self):
        for params in [self.seleccion(anio='1999'), {'historico': 'UPCV-DAF-SALM-999-2026'}]:
            self.assertEqual(self.client.get(self.url('detalle'), params).status_code, 404)
        self.assertEqual(self.client.get(self.url('detalle'), {'numero': '037'}).status_code, 400)

    def test_duplicados_ambiguos_no_eligen_primero(self):
        with patch('scompras_app.solicitud_admin.filtrados') as filtrados:
            filtrados.return_value.values_list.return_value = [self.solicitud.pk, self.solicitudes[1].pk]
            response = self.client.get(self.url('detalle'), self.seleccion())
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['code'], 'ambiguous')

    def test_detalle_insumos_solo_lectura(self):
        data = self.detalle_actual()
        self.assertEqual(data['id'], self.solicitud.pk)
        self.assertEqual(data['usuario'], self.otro.username)
        self.assertEqual(data['departamento'], self.departamento.nombre)
        self.assertEqual(data['insumos'][0]['cantidad'], 4)
        self.assertEqual(data['insumos'][0]['especiales'], 'Azul')
        self.assertEqual(data['insumos'][0]['caracteristicas'], 'Papel')

    def test_fecha_persiste_con_hora_y_codigo_intactos(self):
        response = self.guardar(fecha_solicitud='2027-03-20', descripcion='No autorizado', codigo_correlativo='ALTERADO', cantidad='999')
        self.assertEqual(response.status_code, 200)
        self.solicitud.refresh_from_db(); self.detalle.refresh_from_db()
        self.assertEqual(timezone.localtime(self.solicitud.fecha_solicitud).isoformat(), '2027-03-20T10:35:12.123456-06:00')
        self.assertEqual(self.solicitud.codigo_correlativo, 'UPCV-DAF-SALM-037-2026')
        self.assertEqual(self.solicitud.descripcion, 'Insumos de oficina')
        self.assertEqual(self.detalle.cantidad, 4)
        self.assertEqual(self.detalle.caracteristica_especial, 'Azul')
        self.assertEqual(self.detalle_actual()['fecha_solicitud'], '2027-03-20')

    def test_estado_permitido_sin_efectos_operativos(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.guardar(estado='Finalizada')
        self.assertEqual(response.status_code, 200)
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'Finalizada')
        self.assertTrue(any('FOR UPDATE' in q['sql'] for q in queries))
        self.assertFalse(CDP.objects.exists())
        self.assertFalse(KardexPresupuesto.objects.exists())
        self.assertEqual(self.guardar(estado='Rechazada').status_code, 200)
        self.assertEqual(self.guardar(estado='Creada').status_code, 200)
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'Creada')
        self.assertEqual(self.guardar(estado='Rechazada').status_code, 200)

    def test_fecha_y_estado_se_auditan_en_una_operacion(self):
        self.assertEqual(self.guardar(fecha_solicitud='2026-04-02', estado='Finalizada').status_code, 200)
        registro = AuditoriaSolicitudCompra.objects.get(solicitud_id=self.solicitud.pk)
        self.assertEqual(registro.usuario, self.admin)
        self.assertEqual(registro.correlativo, self.solicitud.codigo_correlativo)
        self.assertEqual(registro.estado_anterior, 'Creada')
        self.assertEqual(registro.estado_nuevo, 'Finalizada')
        self.assertEqual(registro.fecha_anterior, self.fecha)
        self.assertEqual(registro.solicitud_pk, self.solicitud.pk)
        response = self.client.get(self.url('historial', self.solicitud.pk))
        self.assertEqual([r['campo'] for r in response.json()['registros']], ['Fecha de solicitud', 'Estado'])

    def test_noop_no_actualiza_ni_audita(self):
        with patch('scompras_app.solicitud_admin.AuditoriaSolicitudCompra.objects.create') as audit:
            response = self.guardar()
        self.assertFalse(response.json()['changed'])
        audit.assert_not_called()

    def test_validacion_fecha_estado_y_token(self):
        for params in [{'fecha_solicitud': '2026-02-30'}, {'estado': 'Anulada'}, {'version': 'falsificado'}]:
            with self.subTest(params=params):
                self.assertIn(self.guardar(**params).status_code, [400, 409])
        self.assertFalse(AuditoriaSolicitudCompra.objects.all().exists())

    def test_version_desactualizada_no_sobrescribe(self):
        original = self.detalle_actual()
        self.assertEqual(self.guardar(fecha_solicitud='2026-04-01').status_code, 200)
        response = self.client.post(self.url('actualizar', self.solicitud.pk), {
            'fecha_solicitud': '2026-04-05', 'estado': 'Rechazada', 'version': original['version'],
        })
        self.assertEqual(response.status_code, 409)
        self.solicitud.refresh_from_db()
        self.assertEqual(timezone.localtime(self.solicitud.fecha_solicitud).day, 1)
        self.assertEqual(self.solicitud.estado, 'Creada')

    def test_token_no_puede_usarse_para_otra_solicitud(self):
        data = self.detalle_actual()
        response = self.client.post(self.url('actualizar', self.solicitudes[1].pk), {
            'fecha_solicitud': '2026-04-05', 'estado': 'Rechazada', 'version': data['version'],
        })
        self.assertEqual(response.status_code, 409)

    def test_cdp_activo_bloquea_estado_no_fecha(self):
        presupuesto = PresupuestoAnual.objects.create(anio=2026, activo=True)
        renglon = PresupuestoRenglon.objects.create(presupuesto_anual=presupuesto, codigo_renglon='100', monto_inicial=100)
        cdp = CDP.objects.create(solicitud=self.solicitud, renglon=renglon, monto=10)
        antes = KardexPresupuesto.objects.count()
        self.assertEqual(self.guardar(estado='Rechazada').status_code, 409)
        self.assertEqual(self.guardar(fecha_solicitud='2026-06-10').status_code, 200)
        cdp.refresh_from_db()
        self.assertEqual(cdp.estado, CDP.Estado.RESERVADO)
        self.assertEqual(KardexPresupuesto.objects.count(), antes)
        SolicitudCompra.objects.filter(pk=self.solicitud.pk).update(estado='Finalizada')
        self.assertEqual(self.guardar(estado='Creada').status_code, 409)

    def test_pasos_completados_bloquean_estado(self):
        tipo = TipoProcesoCompra.objects.create(nombre='Proceso', codigo='adm-test')
        paso = ProcesoCompraPaso.objects.create(tipo=tipo, numero=1, titulo='Aprobación')
        SolicitudPasoEstado.objects.create(solicitud=self.solicitud, paso=paso, completado=True)
        self.assertEqual(self.guardar(estado='Finalizada').status_code, 409)

    def test_atomicidad_si_falla_auditoria(self):
        with patch('scompras_app.solicitud_admin.AuditoriaSolicitudCompra.objects.create', side_effect=DatabaseError('fallo simulado')):
            response = self.guardar(estado='Finalizada')
        self.assertEqual(response.status_code, 503)
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'Creada')

    def test_csrf_obligatorio(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        data = self.detalle_actual()
        payload = {'fecha_solicitud': '2026-04-02', 'estado': 'Finalizada', 'version': data['version']}
        self.assertEqual(client.post(self.url('actualizar', self.solicitud.pk), payload).status_code, 403)
        client.get(self.url(''))
        token = client.cookies['csrftoken'].value
        self.assertEqual(client.post(self.url('actualizar', self.solicitud.pk), payload, HTTP_X_CSRFTOKEN=token).status_code, 200)

    def test_historial_paginado_sin_edicion_ni_eliminacion(self):
        self.assertEqual(self.guardar(fecha_solicitud='2026-04-02').status_code, 200)
        registro = AuditoriaSolicitudCompra.objects.get(solicitud_id=self.solicitud.pk)
        AuditoriaSolicitudCompra.objects.bulk_create([
            AuditoriaSolicitudCompra(usuario=self.admin, solicitud=self.solicitud, solicitud_pk=self.solicitud.pk,
                correlativo=registro.correlativo, fecha_anterior=registro.fecha_anterior,
                fecha_nueva=registro.fecha_nueva, estado_anterior=registro.estado_anterior,
                estado_nuevo=registro.estado_nuevo) for _ in range(11)
        ])
        response = self.client.get(self.url('historial', self.solicitud.pk))
        self.assertEqual(response.json()['pages'], 2)
        self.assertEqual(len(response.json()['registros']), 10)
        self.assertEqual(self.client.get(self.url('historial', self.solicitud.pk), {'page': 'mal'}).status_code, 400)
        self.assertEqual(self.client.post(self.url('historial', self.solicitud.pk)).status_code, 405)
        self.assertEqual(self.client.delete(self.url('historial', self.solicitud.pk)).status_code, 405)

    def test_no_se_modifica_generacion_normal(self):
        nueva = SolicitudCompra.objects.create(seccion=self.seccion, usuario=self.otro, descripcion='Nueva', fecha_solicitud=self.fecha)
        self.assertRegex(nueva.codigo_correlativo, r'^UPCV-CAMBIADA-ACTUAL-[0-9]{3}-2026$')
        self.assertEqual(self.client.get(reverse('scompras:detalle_solicitud', args=[nueva.pk])).status_code, 200)


class AdministracionConcurrenteTests(TransactionTestCase):
    def test_dos_administradores_simultaneos_no_pierden_actualizaciones(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import connections

        grupo, _ = Group.objects.get_or_create(name='Administrador')
        user = User.objects.create_user('admin_concurrente')
        user.groups.add(grupo)
        departamento = Departamento.objects.create(id_departamento='concurrencia', nombre='DAF', abreviatura='DAF')
        seccion = Seccion.objects.create(departamento=departamento, nombre='SALM', abreviatura='SALM')
        solicitud = SolicitudCompra.objects.create(usuario=user, seccion=seccion, descripcion='Concurrente')
        clients = [Client(), Client()]
        for client in clients:
            client.force_login(user)
        detalle_url = reverse('scompras:administracion_solicitudes_detalle')
        actualizar_url = reverse('scompras:administracion_solicitudes_actualizar', args=[solicitud.pk])
        snapshot = clients[0].get(detalle_url, {'historico': solicitud.codigo_correlativo}).json()['solicitud']
        barrier = Barrier(2)

        def guardar(index):
            try:
                barrier.wait(timeout=10)
                response = clients[index].post(actualizar_url, {
                    'fecha_solicitud': f'2026-05-0{index + 1}', 'estado': 'Finalizada', 'version': snapshot['version'],
                })
                return response.status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            resultados = list(pool.map(guardar, [0, 1]))
        self.assertEqual(sorted(resultados), [200, 409])
        self.assertEqual(AuditoriaSolicitudCompra.objects.filter(solicitud_id=solicitud.pk).count(), 1)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'Finalizada')
