from django import forms

from empleados_app.forms import ContratoForm, PuestoForm, SedeForm
from empleados_app.models import Puesto

from .models import (
    CasoActuacion,
    CasoJudicial,
    ControlMensualContrato,
    DocumentoGestion,
    InformacionContrato029,
    PerfilRRHHEmpleado,
    Postulante,
)


class RihoFormMixin:
    def aplicar_estilo(self):
        for field in self.fields.values():
            css = (
                "form-check-input"
                if isinstance(field.widget, forms.CheckboxInput)
                else "form-control"
            )
            field.widget.attrs["class"] = css


class PostulanteForm(RihoFormMixin, forms.ModelForm):
    class Meta:
        model = Postulante
        fields = (
            "cui",
            "nombres",
            "apellidos",
            "programa_area",
            "fecha_solicitud",
            "estado_tdr",
            "ficha_tecnica",
        )
        widgets = {"fecha_solicitud": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_estilo()


class PerfilRRHHForm(RihoFormMixin, forms.ModelForm):
    class Meta:
        model = PerfilRRHHEmpleado
        exclude = ("empleado",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_estilo()


class InformacionContrato029Form(RihoFormMixin, forms.ModelForm):
    class Meta:
        model = InformacionContrato029
        exclude = ("contrato", "actualizado_por", "updated_at")
        widgets = {
            "fecha_primera_contratacion": forms.DateInput(attrs={"type": "date"}),
            "fecha_resolucion": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_estilo()


class Contrato029Form(ContratoForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["renglon"].initial = "029"
        self.fields["puesto"].widget.attrs.pop("disabled", None)
        self.fields["puesto"].queryset = Puesto.objects.none()
        sede_id = self.data.get("sede") if self.is_bound else None
        if sede_id and str(sede_id).isdigit():
            self.fields["puesto"].queryset = Puesto.objects.filter(
                sede_id=sede_id
            ).order_by("nombre")
        elif self.instance.pk and self.instance.sede_id:
            self.fields["puesto"].queryset = Puesto.objects.filter(
                sede_id=self.instance.sede_id
            ).order_by("nombre")
        self.fields["puesto"].empty_label = "Seleccione primero una sede"

    def clean(self):
        cleaned_data = super().clean()
        sede, puesto = cleaned_data.get("sede"), cleaned_data.get("puesto")
        if sede and puesto and puesto.sede_id != sede.pk:
            self.add_error(
                "puesto", "El puesto seleccionado no pertenece a la sede indicada."
            )
        return cleaned_data


class SedeRapidaForm(SedeForm):
    pass


class PuestoRapidoForm(PuestoForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sede"].widget.attrs["id"] = "id_puesto-rapido-sede"
        self.fields["nombre"].widget.attrs["id"] = "id_puesto-rapido-nombre"


class ControlMensualForm(RihoFormMixin, forms.ModelForm):
    class Meta:
        model = ControlMensualContrato
        fields = (
            "contrato",
            "mes",
            "anio",
            "fecha_recepcion",
            "estado",
            "observaciones",
        )
        widgets = {"fecha_recepcion": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_estilo()
        self.fields["contrato"].queryset = self.fields[
            "contrato"
        ].queryset.select_related("empleado", "puesto")


class DocumentoGestionForm(RihoFormMixin, forms.ModelForm):
    class Meta:
        model = DocumentoGestion
        fields = ("tipo", "archivo", "estado", "observacion")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_estilo()


class CasoJudicialForm(RihoFormMixin, forms.ModelForm):
    class Meta:
        model = CasoJudicial
        fields = (
            "numero_caso",
            "tipo",
            "empleado",
            "contrato",
            "organo_competente",
            "fecha_inicio",
            "estado",
            "responsable",
            "fecha_ultima_actuacion",
            "observaciones",
        )
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}),
            "fecha_ultima_actuacion": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_estilo()


class CasoActuacionForm(RihoFormMixin, forms.ModelForm):
    class Meta:
        model = CasoActuacion
        fields = ("fecha", "tipo_actuacion", "detalle", "documento")
        widgets = {"fecha": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_estilo()
