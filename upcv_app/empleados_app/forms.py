from django import forms
from .models import Contrato, Empleado
from django.forms import CheckboxInput, DateInput
from .models import ConfiguracionGeneral

class ConfiguracionGeneralForm(forms.ModelForm):
    class Meta:
        model = ConfiguracionGeneral
        fields = ['nombre_institucion', 'direccion', 'logotipo', 'logotipo2']
        
    # Personalizamos la clase 'form-control' para otros campos si es necesario
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Añadimos 'form-control' a los campos, si no está especificado en los widgets
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class EmpleadoForm(forms.ModelForm):
    class Meta:
        model = Empleado
        fields = ['nombres', 'apellidos', 'dpi', 'imagen', 'tipoc', 'dcargo',  'dcargo2']

    
    # Personalizar los campos para agregar la clase 'form-control'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


        # Agregar la clase 'form-control' a todos los campos del formulario
        for field in self.fields.values():
            field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' form-control'


class EmpleadoeditForm(forms.ModelForm):
    class Meta:
        model = Empleado
        fields = ['nombres', 'apellidos', 'imagen', 'dpi', 'tipoc', 'dcargo',  'dcargo2', 'activo']
        labels = {'activo': 'Activo'}
        widgets = {
            'activo': CheckboxInput(attrs={'class': 'form-check-input'}),
            'fecha_inicio': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'fecha_vencimiento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Añadir la clase 'form-control' a los campos si no está especificado en los widgets
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'

class ContratoForm(forms.ModelForm):
    class Meta:
        model = Contrato
        fields = [
            'fecha_inicio',
            'fecha_vencimiento',
            'tipo_contrato',
            'renglon',
        ]
        widgets = {
            'fecha_inicio': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'fecha_vencimiento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'tipo_contrato': forms.Select(attrs={'class': 'form-control'}),
            'renglon': forms.Select(attrs={'class': 'form-control'}),
        }
