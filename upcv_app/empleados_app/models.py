from datetime import datetime

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


    
class Empleado(models.Model):
    dpi = models.CharField(max_length=15, unique=True, null=False, blank=False)
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    imagen = models.ImageField(upload_to='card_images/', null=True, blank=True)
    tipoc = models.CharField(max_length=100)
    dcargo = models.CharField(max_length=100, null=True, blank=True)
    dcargo2 = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)  
    updated_at = models.DateTimeField(auto_now=True)  
    activo = models.BooleanField(default=True)

    # 🔥 CAMBIO IMPORTANTE AQUÍ 🔥
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,   # 👈 YA NO BORRA EL EMPLEADO
        null=True,
        blank=True,
        related_name='empleados'
    )

    qr_code = models.ImageField(upload_to='qr_codes/', null=True, blank=True)

    def __str__(self):
        return self.nombres

    @property
    def fecha_vencimiento_formateada(self):
        return self.fecha_vencimiento.strftime('%Y-%m-%d') if self.fecha_vencimiento else None

    @property
    def fecha_inicio_formateada(self):
        return self.fecha_inicio.strftime('%Y-%m-%d') if self.fecha_inicio else None
    
    @property
    def tiene_contrato_activo(self):
        return self.contratos.filter(activo=True).exists()
    
    @property
    def contrato_activo(self):
        return self.contratos.filter(activo=True).first()




def buscar_empleado_dpi(request):
    dpi = request.GET.get("dpi")
    if not dpi:
        return JsonResponse({"error": "No DPI"}, status=400)

    try:
        emp = Empleado.objects.using('tickets_db').get(dpi=dpi)
        return JsonResponse({
            "nombres": emp.nombres,
            "apellidos": emp.apellidos,
            "imagen": emp.imagen.url if emp.imagen else None,
            "username": generar_username(emp.nombres, emp.apellidos),
            "email": "",
        })
    except Empleado.DoesNotExist:
        return JsonResponse({"error": "Empleado no encontrado"}, status=404)
    

def generar_username(nombre, apellido):
    # Primera letra del nombre + apellido sin espacios
    return (nombre.split()[0][0] + apellido.replace(" ", "")).lower()

class DatosBasicosEmpleado(models.Model):
    empleado = models.OneToOneField(
        Empleado,
        on_delete=models.CASCADE,
        related_name='datos_basicos'
    )

    fecha_nacimiento = models.DateField(null=True, blank=True)

    sexo = models.CharField(
        max_length=10,
        choices=[
            ('M', 'Masculino'),
            ('F', 'Femenino'),
            ('O', 'Otro'),
        ],
        null=True,
        blank=True
    )

    estado_civil = models.CharField(
        max_length=20,
        choices=[
            ('soltero', 'Soltero(a)'),
            ('casado', 'Casado(a)'),
            ('divorciado', 'Divorciado(a)'),
            ('viudo', 'Viudo(a)'),
            ('union', 'Unión de hecho'),
        ],
        null=True,
        blank=True
    )

    nacionalidad = models.CharField(max_length=50, null=True, blank=True)

    GRUPO_ETNICO_CHOICES = [
        ('maya', 'Maya'),
        ('xinca', 'Xinca'),
        ('garifuna', 'Garífuna'),
        ('otro', 'Otro'),
    ]

    grupo_etnico = models.CharField(
        max_length=20,
        choices=GRUPO_ETNICO_CHOICES,
        null=True,
        blank=True
    )

    idiomas = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        help_text="Ejemplo: Español (Nativo), Inglés (Básico)"
    )

    direccion_residencia = models.CharField(max_length=250, null=True, blank=True)

    telefono_personal = models.CharField(max_length=20, null=True, blank=True)
    telefono_emergencia = models.CharField(max_length=20, null=True, blank=True)
    persona_contacto_emergencia = models.CharField(max_length=100, null=True, blank=True)

    correo_institucional = models.EmailField(null=True, blank=True)

    def __str__(self):
        return f"Datos Básicos de {self.empleado}"



class FormacionAcademicaEmpleado(models.Model):

    NIVEL_CHOICES = [
        ('primaria', 'Primaria'),
        ('basicos', 'Básicos'),
        ('diversificado', 'Diversificado'),
        ('tecnico', 'Técnico'),
        ('universitario', 'Universitario'),
        ('posgrado', 'Posgrado'),
        ('maestria', 'Maestría'),
        ('doctorado', 'Doctorado'),
        ('diplomado', 'Diplomado'),
        ('certificado', 'Certificado'),
        ('otro', 'Otro'),
    ]

    empleado = models.ForeignKey(
        Empleado,
        on_delete=models.CASCADE,
        related_name='formaciones'
    )

    nivel = models.CharField(max_length=20, choices=NIVEL_CHOICES)
    titulo_obtenido = models.CharField(max_length=150, null=True, blank=True)
    centro_estudio = models.CharField(max_length=150)

    # 🔥 SOLO UNA FECHA (el año o la fecha del documento)
    fecha = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.empleado} - {self.nivel}"


class Sede(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    direccion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre


class Puesto(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)
    sede = models.ForeignKey(Sede, on_delete=models.CASCADE, related_name='puestos')

    def __str__(self):
        return f"{self.nombre} ({self.sede.nombre})"




class Contrato(models.Model):
    ESTADO_ACTIVO = 'activo'
    ESTADO_RESCINDIDO = 'rescindido'
    ESTADO_VENCIDO = 'vencido'

    ESTADO_CHOICES = [
        (ESTADO_ACTIVO, 'Activo'),
        (ESTADO_RESCINDIDO, 'Rescindido'),
        (ESTADO_VENCIDO, 'Vencido'),
    ]

    # Opciones para el campo tipo de contrato
    TIPO_CONTRATO_CHOICES = [
        ('Servicios Técnicos', 'Servicios Técnicos'),
        ('Servicios Profesionales', 'Servicios Profesionales'),
        ('Personal Permanente', 'Personal Permanente'),
    ]

    empleado = models.ForeignKey('Empleado', on_delete=models.CASCADE, related_name='contratos')
    fecha_inicio = models.DateField()
    fecha_vencimiento = models.DateField()

    tipo_contrato = models.CharField(
        max_length=50,
        choices=TIPO_CONTRATO_CHOICES,
        default='Servicios Técnicos'  # O el valor que más uses
    )

    RENGLON_CHOICES = [
        ('029', '029'),
        ('021', '021'),
        ('022', '022'),
    ]

    renglon = models.CharField(
        max_length=3,
        choices=RENGLON_CHOICES,
        default='029'
    )

    activo = models.BooleanField(default=True)
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default=ESTADO_ACTIVO)
    fecha_rescision = models.DateField(null=True, blank=True)
    motivo_rescision = models.TextField(null=True, blank=True)
    observaciones_rescision = models.TextField(null=True, blank=True)
    rescindido_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contratos_rescindidos'
    )
    fecha_registro_rescision = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sede = models.ForeignKey(Sede, on_delete=models.SET_NULL, null=True, blank=True, related_name='contratos')
    puesto = models.ForeignKey(Puesto, on_delete=models.SET_NULL, null=True, blank=True, related_name='contratos')

    def clean(self):
        if self.fecha_inicio and self.fecha_vencimiento and self.fecha_vencimiento < self.fecha_inicio:
            raise ValidationError("La fecha de vencimiento no puede ser menor que la fecha de inicio.")

        if self.estado == self.ESTADO_RESCINDIDO and self.fecha_rescision and self.fecha_rescision < self.fecha_inicio:
            raise ValidationError("La fecha de rescisión no puede ser menor que la fecha de inicio del contrato.")

    def actualizar_estado_automatico(self):
        if self.estado == self.ESTADO_RESCINDIDO:
            self.activo = False
            return

        if self.fecha_vencimiento < datetime.today().date():
            self.estado = self.ESTADO_VENCIDO
            self.activo = False
        else:
            self.estado = self.ESTADO_ACTIVO
            self.activo = True

    def save(self, *args, **kwargs):
        self.actualizar_estado_automatico()
        self.full_clean()
        super().save(*args, **kwargs)

    def rescindir(self, fecha_rescision, motivo_rescision, observaciones_rescision, usuario, commit=True):
        if self.estado == self.ESTADO_RESCINDIDO:
            raise ValidationError("Este contrato ya se encuentra rescindido.")
        if fecha_rescision < self.fecha_inicio:
            raise ValidationError("La fecha de rescisión no puede ser menor que la fecha de inicio.")

        self.estado = self.ESTADO_RESCINDIDO
        self.activo = False
        self.fecha_rescision = fecha_rescision
        self.motivo_rescision = motivo_rescision
        self.observaciones_rescision = observaciones_rescision
        self.rescindido_por = usuario
        self.fecha_registro_rescision = timezone.now()

        if commit:
            self.save()

    def __str__(self):
        return f"Contrato de {self.empleado.nombres}"




class ConfiguracionGeneral(models.Model):
    nombre_institucion = models.CharField(max_length=255, verbose_name='Nombre de la Institución')
    direccion = models.CharField(max_length=255, verbose_name='Dirección')
    logotipo = models.ImageField(upload_to='logotipos/', verbose_name='Logotipo', null=True, blank=True)
    logotipo2 = models.ImageField(upload_to='logotipos2/', verbose_name='Logotipo2', null=True, blank=True)

    def __str__(self):
        return self.nombre_institucion
    
    
