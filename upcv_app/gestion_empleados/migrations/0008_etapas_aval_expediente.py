from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def conservar_expedientes_completos(apps, schema_editor):
    Evaluacion = apps.get_model("gestion_empleados", "EvaluacionExpediente")
    for evaluacion in Evaluacion.objects.filter(completo=True).iterator():
        evaluacion.pre_aval_aprobado = True
        evaluacion.pre_aval_aprobado_por_id = evaluacion.completado_por_id
        evaluacion.pre_aval_aprobado_en = evaluacion.fecha_completado
        evaluacion.post_aval_aprobado = True
        evaluacion.post_aval_aprobado_por_id = evaluacion.completado_por_id
        evaluacion.post_aval_aprobado_en = evaluacion.fecha_completado
        evaluacion.save(update_fields=(
            "pre_aval_aprobado", "pre_aval_aprobado_por",
            "pre_aval_aprobado_en", "post_aval_aprobado",
            "post_aval_aprobado_por", "post_aval_aprobado_en",
        ))


class Migration(migrations.Migration):
    dependencies = [
        ("gestion_empleados", "0007_eliminar_confiabilidad_postulante"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="evaluacionexpediente",
            name="pre_aval_aprobado",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="evaluacionexpediente",
            name="pre_aval_aprobado_en",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="evaluacionexpediente",
            name="pre_aval_aprobado_por",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="evaluaciones_pre_aval_aprobadas", to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="evaluacionexpediente",
            name="post_aval_aprobado",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="evaluacionexpediente",
            name="post_aval_aprobado_en",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="evaluacionexpediente",
            name="post_aval_aprobado_por",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="evaluaciones_post_aval_aprobadas", to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(
            conservar_expedientes_completos, migrations.RunPython.noop
        ),
    ]
