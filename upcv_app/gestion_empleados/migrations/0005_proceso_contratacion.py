from datetime import date
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def migrar_procesos(apps, schema_editor):
    Postulante = apps.get_model("gestion_empleados", "Postulante")
    Proceso = apps.get_model("gestion_empleados", "ProcesoContratacion")
    Evaluacion = apps.get_model("gestion_empleados", "EvaluacionExpediente")
    Historial = apps.get_model("gestion_empleados", "HistorialProcesoContratacion")
    for postulante in Postulante.objects.all().iterator():
        proceso = Proceso.objects.create(
            tipo_proceso="INGRESO", estado="PRESELECCION", empleado_id=postulante.empleado_id,
            postulante_id=postulante.pk, periodo=postulante.fecha_solicitud.year,
            fecha_inicio=postulante.fecha_solicitud, responsable_id=postulante.responsable_id,
            creado_por_id=postulante.responsable_id, actualizado_por_id=postulante.responsable_id,
        )
        Evaluacion.objects.filter(postulante_id=postulante.pk).update(proceso_id=proceso.pk)
        Historial.objects.create(proceso_id=proceso.pk, accion="proceso_migrado",
            estado_nuevo="PRESELECCION", detalle="Creado desde postulación histórica",
            usuario_id=postulante.responsable_id)


class Migration(migrations.Migration):
    dependencies = [("empleados_app", "0006_estados_contrato_futuro"),
                    migrations.swappable_dependency(settings.AUTH_USER_MODEL),
                    ("gestion_empleados", "0004_remove_postulante_ficha_tecnica")]
    operations = [
        migrations.AddField(model_name="postulante", name="resultado_confiabilidad", field=models.CharField(choices=[("PENDIENTE", "Prueba de Confiabilidad pendiente"), ("APROBADA", "Prueba de Confiabilidad aprobada"), ("NO_APROBADA", "Prueba de Confiabilidad no aprobada")], default="PENDIENTE", max_length=15)),
        migrations.AddField(model_name="postulante", name="fecha_evaluacion_confiabilidad", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="postulante", name="observacion_confiabilidad", field=models.TextField(blank=True)),
        migrations.AddField(model_name="postulante", name="evaluado_por", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="pruebas_confiabilidad_registradas", to=settings.AUTH_USER_MODEL)),
        migrations.AlterField(model_name="postulante", name="estado_tdr", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="postulantes", to="gestion_empleados.estadopostulacion")),
        migrations.AlterField(model_name="evaluacionexpediente", name="postulante", field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="evaluaciones", to="gestion_empleados.postulante")),
        migrations.CreateModel(name="ProcesoContratacion", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("tipo_proceso", models.CharField(choices=[("INGRESO", "Ingreso"), ("RENOVACION", "Renovación"), ("REINGRESO", "Reingreso")], max_length=12)),
            ("estado", models.CharField(choices=[(x, x.replace("_", " ").title()) for x in ("PRESELECCION", "PRUEBA_CONFIABILIDAD", "RECLUTAMIENTO", "EXPEDIENTE_INCOMPLETO", "ELEGIBLE", "CONTRATACION", "CONTRATADO", "NO_APROBADO", "CANCELADO")], max_length=24)),
            ("periodo", models.PositiveSmallIntegerField(default=date.today().year)), ("fecha_inicio", models.DateField(default=date.today)), ("fecha_finalizacion", models.DateTimeField(blank=True, null=True)), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("contrato_resultante", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="proceso_contratacion", to="empleados_app.contrato")),
            ("empleado", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="procesos_contratacion", to="empleados_app.empleado")),
            ("postulante", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="procesos_contratacion", to="gestion_empleados.postulante")),
            ("responsable", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="procesos_contratacion_responsable", to=settings.AUTH_USER_MODEL)), ("creado_por", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="procesos_contratacion_creados", to=settings.AUTH_USER_MODEL)), ("actualizado_por", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="procesos_contratacion_actualizados", to=settings.AUTH_USER_MODEL)),
        ], options={"ordering": ("-fecha_inicio", "-created_at"), "permissions": [("manage_hiring_process", "Puede gestionar procesos de contratación")]}),
        migrations.CreateModel(name="HistorialProcesoContratacion", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("accion", models.CharField(max_length=80)), ("estado_anterior", models.CharField(blank=True, max_length=24)), ("estado_nuevo", models.CharField(max_length=24)), ("detalle", models.TextField(blank=True)), ("fecha", models.DateTimeField(auto_now_add=True)), ("proceso", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="historial", to="gestion_empleados.procesocontratacion")), ("usuario", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
        ], options={"ordering": ("-fecha",)}),
        migrations.AddField(model_name="evaluacionexpediente", name="proceso", field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="evaluacion", to="gestion_empleados.procesocontratacion")),
        migrations.RunPython(migrar_procesos, migrations.RunPython.noop),
        migrations.AddConstraint(model_name="procesocontratacion", constraint=models.UniqueConstraint(condition=models.Q(("estado__in", ("PRESELECCION", "PRUEBA_CONFIABILIDAD", "RECLUTAMIENTO", "EXPEDIENTE_INCOMPLETO", "ELEGIBLE", "CONTRATACION"))), fields=("empleado", "tipo_proceso", "periodo"), name="proceso_abierto_empleado_tipo_periodo_unico")),
    ]
