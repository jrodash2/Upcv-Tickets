from django.db import models
from django.contrib.auth.models import User
from datetime import datetime

class Empleado(models.Model):
    dpi = models.CharField(max_length=15, unique=True, null=False, blank=False)  # Agregamos el campo DPI
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    imagen = models.ImageField(upload_to='card_images/', null=True, blank=True)
    tipoc = models.CharField(max_length=100)
    dcargo = models.CharField(max_length=100, null=True, blank=True)
    dcargo2 = models.CharField(max_length=100, null=True, blank=True)
    fecha_inicio = models.DateField()  
    fecha_vencimiento = models.DateField()  
    created_at = models.DateTimeField(auto_now_add=True)  
    updated_at = models.DateTimeField(auto_now=True)  
    activo = models.BooleanField(default=True)  
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='empleados') 
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


    def save(self, *args, **kwargs):
        # Si la fecha de vencimiento ya pasó o es hoy, desactivar
        if self.fecha_vencimiento and self.fecha_vencimiento <= datetime.today().date():
            self.activo = False

        super().save(*args, **kwargs)

class Contrato(models.Model):
    empleado = models.ForeignKey('Empleado', on_delete=models.CASCADE, related_name='contratos')
    fecha_inicio = models.DateField()
    fecha_vencimiento = models.DateField()
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.activo = self.fecha_vencimiento > datetime.today().date()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Contrato de {self.empleado.nombres}"

class ConfiguracionGeneral(models.Model):
    nombre_institucion = models.CharField(max_length=255, verbose_name='Nombre de la Institución')
    direccion = models.CharField(max_length=255, verbose_name='Dirección')
    logotipo = models.ImageField(upload_to='logotipos/', verbose_name='Logotipo', null=True, blank=True)
    logotipo2 = models.ImageField(upload_to='logotipos2/', verbose_name='Logotipo2', null=True, blank=True)

    def __str__(self):
        return self.nombre_institucion