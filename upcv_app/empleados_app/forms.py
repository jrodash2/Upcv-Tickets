from django import forms
from .models import Empleado
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
        fields = ['nombres', 'apellidos', 'dpi', 'imagen', 'tipoc', 'dcargo', 'fecha_vencimiento', 'fecha_inicio']

    # Usamos DateInput para el campo de fecha_vencimiento
    fecha_vencimiento = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'})  # Esto indica al navegador que debe mostrar un calendario
    )
    
    # Usamos DateInput para el campo de fecha_inicio
    fecha_inicio = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'})  # Esto indica al navegador que debe mostrar un calendario
    )

    # Personalizar los campos para agregar la clase 'form-control'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


        # Agregar la clase 'form-control' a todos los campos del formulario
        for field in self.fields.values():
            field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' form-control'


class EmpleadoeditForm(forms.ModelForm):
    class Meta:
        model = Empleado
        fields = ['nombres', 'apellidos', 'imagen', 'dpi', 'tipoc', 'dcargo', 'fecha_vencimiento', 'fecha_inicio', 'activo']
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
