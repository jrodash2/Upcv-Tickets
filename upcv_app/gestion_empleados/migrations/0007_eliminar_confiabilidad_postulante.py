from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("gestion_empleados", "0006_confiabilidad_por_proceso"),
    ]

    operations = [
        # 0006 ya copió estos valores a cada ProcesoContratacion. La eliminación
        # ocurre en un paso posterior para no mezclar copia y retiro de columnas.
        migrations.RemoveField(
            model_name="postulante", name="legado_resultado_confiabilidad"
        ),
        migrations.RemoveField(
            model_name="postulante", name="legado_fecha_evaluacion_confiabilidad"
        ),
        migrations.RemoveField(model_name="postulante", name="legado_evaluado_por"),
        migrations.RemoveField(
            model_name="postulante", name="legado_observacion_confiabilidad"
        ),
    ]
