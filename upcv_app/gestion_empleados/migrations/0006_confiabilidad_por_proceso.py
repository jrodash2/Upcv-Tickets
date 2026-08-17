from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def migrar_confiabilidad_al_proceso(apps, schema_editor):
    Postulante = apps.get_model("gestion_empleados", "Postulante")
    Proceso = apps.get_model("gestion_empleados", "ProcesoContratacion")
    for postulante in Postulante.objects.all().iterator():
        procesos = Proceso.objects.filter(postulante_id=postulante.pk).order_by(
            "-fecha_inicio", "-created_at", "-pk"
        )
        proceso = procesos.first()
        if proceso is None:
            continue
        procesos.filter(estado="NO_APROBADO").update(
            resultado_confiabilidad="NO_APROBADA"
        )
        procesos.filter(estado__in=(
            "RECLUTAMIENTO", "EXPEDIENTE_INCOMPLETO", "ELEGIBLE",
            "CONTRATACION", "CONTRATADO",
        )).update(resultado_confiabilidad="APROBADA")
        # El registro de Postulante solo conservaba una evaluación. Se copia
        # íntegramente al proceso más reciente; para procesos anteriores se
        # conserva la mejor inferencia posible desde su estado final.
        proceso.resultado_confiabilidad = postulante.resultado_confiabilidad
        proceso.fecha_evaluacion_confiabilidad = postulante.fecha_evaluacion_confiabilidad
        proceso.evaluado_por_id = postulante.evaluado_por_id
        proceso.observacion_confiabilidad = postulante.observacion_confiabilidad
        proceso.save(update_fields=(
            "resultado_confiabilidad", "fecha_evaluacion_confiabilidad",
            "evaluado_por", "observacion_confiabilidad",
        ))


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("gestion_empleados", "0005_proceso_contratacion"),
    ]
    operations = [
        migrations.AddField(
            model_name="procesocontratacion", name="resultado_confiabilidad",
            field=models.CharField(
                choices=[
                    ("PENDIENTE", "Prueba de Confiabilidad pendiente"),
                    ("APROBADA", "Prueba de Confiabilidad aprobada"),
                    ("NO_APROBADA", "Prueba de Confiabilidad no aprobada"),
                ], default="PENDIENTE", max_length=15,
            ),
        ),
        migrations.AddField(
            model_name="procesocontratacion", name="fecha_evaluacion_confiabilidad",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="procesocontratacion", name="observacion_confiabilidad",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="procesocontratacion", name="evaluado_por",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="procesos_confiabilidad_evaluados", to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(migrar_confiabilidad_al_proceso, migrations.RunPython.noop),
        migrations.RenameField(model_name="postulante", old_name="resultado_confiabilidad", new_name="legado_resultado_confiabilidad"),
        migrations.RenameField(model_name="postulante", old_name="fecha_evaluacion_confiabilidad", new_name="legado_fecha_evaluacion_confiabilidad"),
        migrations.RenameField(model_name="postulante", old_name="evaluado_por", new_name="legado_evaluado_por"),
        migrations.RenameField(model_name="postulante", old_name="observacion_confiabilidad", new_name="legado_observacion_confiabilidad"),
        migrations.AlterField(
            model_name="postulante", name="legado_resultado_confiabilidad",
            field=models.CharField(default="PENDIENTE", editable=False, max_length=15),
        ),
        migrations.AlterField(
            model_name="postulante", name="legado_fecha_evaluacion_confiabilidad",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="postulante", name="legado_evaluado_por",
            field=models.ForeignKey(
                blank=True, editable=False, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="pruebas_confiabilidad_legadas", to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="postulante", name="legado_observacion_confiabilidad",
            field=models.TextField(blank=True, editable=False),
        ),
    ]
