from django import forms
from django.contrib.auth.models import User, Group
from .models import Ticket, TipoEquipo, Insumo, FechaInsumo
from django.core.exceptions import ValidationError

class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ['oficina', 'via_contacto', 'telefono', 'correo', 'prioridad', 'tipo_equipo', 'problema', 'responsable', 'tecnico_asignado', 'estado']

    def __init__(self, *args, **kwargs):
        super(TicketForm, self).__init__(*args, **kwargs)
        
        # Filtrar usuarios por grupo 'tecnico'
        try:
            tecnicos_group = Group.objects.get(name='tecnico')
            self.fields['tecnico_asignado'].queryset = User.objects.filter(groups=tecnicos_group)
        except Group.DoesNotExist:
            self.fields['tecnico_asignado'].queryset = User.objects.none()
        
        # Agregar la clase 'form-control' a todos los campos del formulario
        for field in self.fields.values():
            field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' form-control'


from django import forms
from django.contrib.auth.models import User, Group

class UserForm(forms.ModelForm):
    dpi = forms.CharField(
        label="DPI del empleado",
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Ingrese DPI del empleado",
            "id": "id_dpi"
        })
    )

    username = forms.CharField(
        label="Nombre de usuario",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Ingrese nombre de usuario"
        })
    )

    first_name = forms.CharField(
        label="Nombre",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Ingrese nombre"
        })
    )

    last_name = forms.CharField(
        label="Apellido",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Ingrese apellido"
        })
    )

    email = forms.EmailField(
        label="Correo electrónico",
        widget=forms.EmailInput(attrs={
            "class": "form-control",
            "placeholder": "correo@ejemplo.com"
        })
    )

    new_password = forms.CharField(
        label="Contraseña",
        required=True,
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Ingrese una contraseña segura"
        })
    )

    confirm_password = forms.CharField(
        label="Confirmar contraseña",
        required=True,
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Repita la contraseña"
        })
    )

    group = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        label="Grupo",
        required=True,
        widget=forms.Select(attrs={
            "class": "form-control"
        })
    )

    class Meta:
        model = User
        fields = ["dpi", "username", "first_name", "last_name", "email", "group"]

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("new_password") != cleaned_data.get("confirm_password"):
            raise forms.ValidationError("Las contraseñas no coinciden.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["new_password"])
        if commit:
            user.save()
            user.groups.set([self.cleaned_data["group"]])
        return user
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Si estamos editando, cargar el grupo actual
        if self.instance and self.instance.pk:
            grupos = self.instance.groups.all()
            if grupos.exists():
                self.fields['group'].initial = grupos.first().id




            
class TickettecForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ['detalle_problema', 'solucion_problema', 'estado']

    def __init__(self, *args, **kwargs):
        super(TickettecForm, self).__init__(*args, **kwargs)
        

       
        
         # Filtrar estados
        ESTADOS_PERMITIDOS = ['en_proceso', 'cerrado', 'pendiente']
        self.fields['estado'].choices = [(key, value) for key, value in self.fields['estado'].choices if key in ESTADOS_PERMITIDOS]
        # Agregar la clase 'form-control' a todos los campos del formulario
        for field in self.fields.values():
            field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' form-control'


from .models import Oficina

class OficinaForm(forms.ModelForm):
    class Meta:
        model = Oficina
        fields = ['nombre']

        
    def __init__(self, *args, **kwargs):
        super(OficinaForm, self).__init__(*args, **kwargs)
        
        
        # Agregar la clase 'form-control' a todos los campos del formulario
        for field in self.fields.values():
            field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' form-control'


class TipoEquipoForm(forms.ModelForm):
    class Meta:
        model = TipoEquipo
        fields = ['nombre']

          
    def __init__(self, *args, **kwargs):
        super(TipoEquipoForm, self).__init__(*args, **kwargs)
        
        
        # Agregar la clase 'form-control' a todos los campos del formulario
        for field in self.fields.values():
            field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' form-control'



class ExcelUploadForm(forms.Form):
    archivo_excel = forms.FileField()

    def __init__(self, *args, **kwargs):
        super(ExcelUploadForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            # Si es tipo FileField, normalmente se usa 'form-control' o 'form-control-file'
            css_class = 'form-control'
            field.widget.attrs['class'] = field.widget.attrs.get('class', '') + f' {css_class}'

class InsumoForm(forms.ModelForm):
    class Meta:
        model = Insumo
        fields = ['renglon', 'codigo_insumo', 'nombre', 'caracteristicas', 
                  'nombre_presentacion', 'cantidad_unidad_presentacion', 
                  'codigo_presentacion', 'fecha_actualizacion']
        widgets = {
            'fecha_actualizacion': forms.DateTimeInput(attrs={'type': 'datetime-local'})  # Usamos el widget para una entrada de fecha y hora
        }
        


class FechaInsumoForm(forms.ModelForm):
    class Meta:
        model = FechaInsumo
        fields = ['fechainsumo']
        widgets = {
            'fechainsumo': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super(FechaInsumoForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' form-control'
   


