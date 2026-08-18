import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("empleados_app", "0006_estados_contrato_futuro"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="contrato", name="empleado",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name="contratos", to="empleados_app.empleado",
            ),
        ),
        migrations.AddField(
            model_name="contrato", name="estado_documental",
            field=models.CharField(
                choices=[("borrador", "Borrador"), ("creado", "Creado"),
                         ("firmado", "Firmado"), ("aprobado", "Aprobado")],
                default="aprobado", max_length=12,
            ),
        ),
        migrations.AddField(model_name="contrato", name="fecha_firma", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="contrato", name="fecha_aprobacion", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(
            model_name="contrato", name="creado_por",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="contratos_creados", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="contrato", name="firmado_por",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="contratos_firmados", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="contrato", name="aprobado_por",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="contratos_aprobados", to=settings.AUTH_USER_MODEL),
        ),
    ]
