from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from empleados_app.models import Contrato, Empleado

from .models import ExpedienteEmpleado
from .selectors import obtener_indicadores_dashboard


class IndicadoresDashboardTests(TestCase):
    def setUp(self):
        self.hoy = timezone.localdate()
        self.empleado = Empleado.objects.create(
            dpi="1234567890101",
            nombres="Ana",
            apellidos="Prueba",
            tipoc="Empleado",
        )

    def crear_contrato(self, inicio, vencimiento, estado=Contrato.ESTADO_ACTIVO):
        contrato = Contrato.objects.create(
            empleado=self.empleado,
            fecha_inicio=inicio,
            fecha_vencimiento=vencimiento,
        )
        if estado == Contrato.ESTADO_RESCINDIDO:
            contrato.rescindir(self.hoy, "Prueba", "", None)
        return contrato

    def test_calcula_indicadores_con_datos_reales(self):
        self.crear_contrato(self.hoy - timedelta(days=1), self.hoy + timedelta(days=10))
        otro = Empleado.objects.create(dpi="1234567890102", nombres="Luis", apellidos="Prueba", tipoc="Empleado")
        Contrato.objects.create(empleado=otro, fecha_inicio=self.hoy - timedelta(days=30), fecha_vencimiento=self.hoy - timedelta(days=1))
        ExpedienteEmpleado.objects.create(empleado=self.empleado)

        indicadores = obtener_indicadores_dashboard()

        self.assertEqual(indicadores["total_empleados"], 2)
        self.assertEqual(indicadores["empleados_con_contrato_activo"], 1)
        self.assertEqual(indicadores["contratos_vencidos"], 1)
        self.assertEqual(indicadores["contratos_proximos_vencer"], 1)
        self.assertEqual(indicadores["expedientes_en_proceso"], 1)


class AccesoGestionTests(TestCase):
    def test_usuario_anonimo_es_redirigido(self):
        response = self.client.get(reverse("gestion_empleados:dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_superusuario_puede_ver_dashboard(self):
        user = get_user_model().objects.create_superuser("rrhh", "rrhh@example.com", "clave-segura")
        self.client.force_login(user)
        response = self.client.get(reverse("gestion_empleados:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gestión de Empleados")
