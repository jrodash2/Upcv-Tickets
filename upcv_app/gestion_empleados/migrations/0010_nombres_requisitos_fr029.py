from django.db import migrations


REQUISITOS = (
    ("1", "Fotocopia legible del DPI vigente (anverso y reverso), ampliado a media carta.", "PRE_AVAL"),
    ("2", "Curriculum Vitae Actualizado (Firmado y coincidente con soporte).", "PRE_AVAL"),
    ("3", "Fotocopia de recibo reciente de energía eléctrica o agua.", "PRE_AVAL"),
    ("4", "Constancia RTU con Código QR (Código Actividad 7020.40 o Título).", "PRE_AVAL"),
    ("5", "Solvencia Fiscal SAT (Emitida con fecha igual/posterior a RTU).", "PRE_AVAL"),
    ("6", "Fotocopia Boleto de Ornato vigente (Según escala de honorarios).", "PRE_AVAL"),
    ("7", "Constancia Carencia de Antecedentes Penales vigente.", "PRE_AVAL"),
    ("8", "Constancia Carencia de Antecedentes Policiales vigente.", "PRE_AVAL"),
    ("9", "Constancia y Resolución de Inscripción en RGAE (Ejercicio Fiscal 2026).", "PRE_AVAL"),
    ("10", "Servicios Técnicos: Títulos / Diplomas (Primaria, Básico, Nivel Medio).", "PRE_AVAL"),
    ("10.1", "Certificado de Estudios a nivel Universitario (si acredita).", "PRE_AVAL"),
    ("10.2", "Técnicos Universitarios: Título emitido por Universidad.", "PRE_AVAL"),
    ("11", "Servicios Profesionales: Título Profesional Universitario registrado.", "PRE_AVAL"),
    ("12", "Constancia de Colegiado Activo (Vigente todo el Ejercicio Fiscal).", "PRE_AVAL"),
    ("13", "Diplomas de conocimientos adicionales consignados en TDR/CV.", "PRE_AVAL"),
    ("14", "Constancias Laborales o Contratos Anteriores comprobables.", "PRE_AVAL"),
    ("15", "Fotocopia Cheque Anulado o Constancia de Cuenta Monetaria BANRURAL.", "POST_AVAL"),
    ("16", "Licencia de Conducir vigente (Si prestará servicios de conducción).", "POST_AVAL"),
    ("17", "Acta Notarial de Declaración Jurada (Prohibiciones Art. 80 Ley Contrataciones).", "POST_AVAL"),
    ("18", "Oferta Técnica de Servicios (Acorde a TDR y Curriculum Vitae).", "POST_AVAL"),
    ("19", "Constancia Actualización Anual Datos Personales (Contraloría General Cuentas).", "POST_AVAL"),
)


def actualizar_requisitos(apps, schema_editor):
    Requisito = apps.get_model("gestion_empleados", "CatalogoRequisito")
    for orden, (codigo, descripcion, fase) in enumerate(REQUISITOS, 1):
        requisito, _ = Requisito.objects.get_or_create(
            codigo=codigo,
            defaults={
                "descripcion": descripcion, "fase": fase, "orden": orden,
                "obligatorio": True, "activo": True,
            },
        )
        Requisito.objects.filter(pk=requisito.pk).update(
            descripcion=descripcion, fase=fase, orden=orden,
        )


class Migration(migrations.Migration):
    dependencies = [("gestion_empleados", "0009_flujo_aprobacion_contrato")]

    operations = [
        migrations.RunPython(actualizar_requisitos, migrations.RunPython.noop),
    ]
