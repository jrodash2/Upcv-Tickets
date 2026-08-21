import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Oficina, Ticket, TipoEquipo


class DashboardViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='administrador', password='test-pass')
        self.tecnico = User.objects.create_user(username='tecnico', first_name='Ana')
        self.oficina = Oficina.objects.create(nombre='Informática')
        self.tipo = TipoEquipo.objects.create(nombre='Computadora')
        self.client.force_login(self.user)

    def crear_ticket(self, anio, estado='abierto', mes=1):
        ticket = Ticket.objects.create(
            oficina=self.oficina, tipo_equipo=self.tipo, problema='Prueba',
            responsable='Solicitante', estado=estado,
        )
        fecha = timezone.make_aware(datetime.datetime(anio, mes, 15, 10, 0))
        Ticket.objects.filter(pk=ticket.pk).update(
            fecha_creacion=fecha, tecnico_asignado=self.tecnico,
        )
        ticket.refresh_from_db()
        return ticket

    def test_dashboard_filtra_todas_las_metricas_por_anio(self):
        actual = timezone.now().year
        self.crear_ticket(actual, 'abierto', 3)
        self.crear_ticket(actual - 1, 'cerrado', 5)

        response = self.client.get(reverse('tickets:dashboard'), {'anio': actual})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_tickets'], 1)
        self.assertEqual(response.context['tickets_por_mes'][2]['total'], 1)
        self.assertEqual(response.context['tickets_por_mes'][4]['total'], 0)
        self.assertEqual(list(response.context['ultimos_tickets']), [Ticket.objects.get(estado='abierto')])
        self.assertContains(response, f'value="{actual - 1}"')

    def test_anio_invalido_vuelve_al_anio_actual(self):
        response = self.client.get(reverse('tickets:dashboard'), {'anio': 'no-es-un-anio'})
        self.assertEqual(response.context['anio'], timezone.now().year)
        self.assertEqual(response.status_code, 200)

    def test_anio_sin_tickets_muestra_estado_vacio_y_doce_meses(self):
        response = self.client.get(reverse('tickets:dashboard'), {'anio': 2001})
        self.assertEqual(response.context['anio'], 2001)
        self.assertEqual(response.context['total_tickets'], 0)
        self.assertEqual(len(response.context['tickets_por_mes']), 12)
        self.assertContains(response, 'No existen tickets registrados durante 2001')

    def test_dashboard_requiere_autenticacion(self):
        self.client.logout()
        response = self.client.get(reverse('tickets:dashboard'))
        self.assertEqual(response.status_code, 302)
