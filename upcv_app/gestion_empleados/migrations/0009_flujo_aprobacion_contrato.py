import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("empleados_app", "0007_flujo_documental_contrato"),
        ("gestion_empleados", "0008_etapas_aval_expediente"),
    ]

    operations = [
        migrations.AddField(
            model_name="procesocontratacion",
            name="contrato_en_preparacion",
            field=models.OneToOneField(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="proceso_en_preparacion", to="empleados_app.contrato",
            ),
        ),
        migrations.AlterField(
            model_name="procesocontratacion", name="estado",
            field=models.CharField(
                choices=[
                    ("PRESELECCION", "Preseleccion"),
                    ("PRUEBA_CONFIABILIDAD", "Prueba Confiabilidad"),
                    ("RECLUTAMIENTO", "Reclutamiento"),
                    ("EXPEDIENTE_INCOMPLETO", "Expediente Incompleto"),
                    ("ELEGIBLE", "Elegible"), ("CONTRATACION", "Contratacion"),
                    ("CONTRATO_CREADO", "Contrato Creado"),
                    ("CONTRATO_FIRMADO", "Contrato Firmado"),
                    ("CONTRATADO", "Contratado"),
                    ("NO_APROBADO", "No Aprobado"), ("CANCELADO", "Cancelado"),
                ], max_length=24,
            ),
        ),
        migrations.RemoveConstraint(
            model_name="procesocontratacion",
            name="proceso_abierto_empleado_tipo_periodo_unico",
        ),
        migrations.AddConstraint(
            model_name="procesocontratacion",
            constraint=models.UniqueConstraint(
                condition=models.Q(estado__in=(
                    "PRESELECCION", "PRUEBA_CONFIABILIDAD", "RECLUTAMIENTO",
                    "EXPEDIENTE_INCOMPLETO", "ELEGIBLE", "CONTRATACION",
                    "CONTRATO_CREADO", "CONTRATO_FIRMADO",
                )), fields=("empleado", "tipo_proceso", "periodo"),
                name="proceso_abierto_empleado_tipo_periodo_unico",
            ),
        ),
    ]
