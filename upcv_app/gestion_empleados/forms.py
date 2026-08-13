from django import forms

from empleados_app.forms import ContratoForm, DatosBasicosEmpleadoForm, EmpleadoeditForm

from .models import InformacionContrato029, PerfilRRHHEmpleado, Postulante


class RihoFormMixin:
    def aplicar_estilo(self):
        for field in self.fields.values():
            css = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control"
            field.widget.attrs["class"] = css


class PostulanteForm(RihoFormMixin, forms.ModelForm):
    class Meta:
        model = Postulante
        fields = ("cui", "nombres", "apellidos", "programa_area", "fecha_solicitud", "estado_tdr", "ficha_tecnica")
        widgets = {"fecha_solicitud": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs); self.aplicar_estilo()


class PerfilRRHHForm(RihoFormMixin, forms.ModelForm):
    class Meta:
        model = PerfilRRHHEmpleado
        exclude = ("empleado",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs); self.aplicar_estilo()


class InformacionContrato029Form(RihoFormMixin, forms.ModelForm):
    class Meta:
        model = InformacionContrato029
        exclude = ("contrato", "actualizado_por", "updated_at")
        widgets = {"fecha_primera_contratacion": forms.DateInput(attrs={"type": "date"}), "fecha_resolucion": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs); self.aplicar_estilo()


class Contrato029Form(ContratoForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["renglon"].initial = "029"
