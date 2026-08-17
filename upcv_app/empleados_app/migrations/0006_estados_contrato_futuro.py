from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("empleados_app", "0005_contrato_estado_contrato_fecha_registro_rescision_and_more")]
    operations = [
        migrations.AlterField(
            model_name="contrato", name="estado",
            field=models.CharField(
                choices=[("activo", "Activo"), ("rescindido", "Rescindido"),
                         ("vencido", "Vencido"), ("borrador", "Borrador"),
                         ("pendiente", "Pendiente / futuro")],
                default="activo", max_length=15,
            ),
        ),
    ]
