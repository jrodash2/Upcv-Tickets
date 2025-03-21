# Generated by Django 5.1.4 on 2025-01-30 16:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tickets_app', '0009_ticket_prioridad_alter_ticket_via_contacto'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ticket',
            name='correo',
            field=models.EmailField(blank=True, max_length=100),
        ),
        migrations.AlterField(
            model_name='ticket',
            name='detalle_problema',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='ticket',
            name='solucion_problema',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='ticket',
            name='telefono',
            field=models.CharField(blank=True, max_length=15),
        ),
    ]
