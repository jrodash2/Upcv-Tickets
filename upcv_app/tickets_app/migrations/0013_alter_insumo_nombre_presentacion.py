# Generated by Django 5.1.4 on 2025-05-06 20:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tickets_app', '0012_insumo'),
    ]

    operations = [
        migrations.AlterField(
            model_name='insumo',
            name='nombre_presentacion',
            field=models.CharField(max_length=500),
        ),
    ]
