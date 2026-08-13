from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("gestion_empleados", "0003_personal_casos_auditoria")]

    operations = [
        # FileField almacena solo la referencia. RemoveField no borra archivos físicos;
        # cualquier archivo histórico queda intacto en MEDIA_ROOT para revisión manual.
        migrations.RemoveField(model_name="postulante", name="ficha_tecnica"),
    ]
