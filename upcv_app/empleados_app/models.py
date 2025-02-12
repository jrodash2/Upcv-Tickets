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
        # Formatea la fecha solo si existe
        return self.fecha_vencimiento.strftime('%Y-%m-%d') if self.fecha_vencimiento else None
    
    def save(self, *args, **kwargs):
        # Aquí no es necesario realizar ninguna conversión de fechas manualmente
        # Solo verificamos que la fecha de vencimiento sea correcta y actualizamos el estado de 'activo'
        if self.fecha_vencimiento and self.fecha_vencimiento <= datetime.today().date():
            self.activo = False
        
        # Llamamos al método save de la clase base
        super().save(*args, **kwargs)

    @property
    def fecha_inicio_formateada(self):
        # Formatea la fecha solo si existe
        return self.fecha_inicio.strftime('%Y-%m-%d') if self.fecha_inicio else None

    def save(self, *args, **kwargs):
      
        # Llamamos al método save de la clase base
        super().save(*args, **kwargs)


class ConfiguracionGeneral(models.Model):
    nombre_institucion = models.CharField(max_length=255, verbose_name='Nombre de la Institución')
    direccion = models.CharField(max_length=255, verbose_name='Dirección')
    logotipo = models.ImageField(upload_to='logotipos/', verbose_name='Logotipo', null=True, blank=True)
    logotipo2 = models.ImageField(upload_to='logotipos2/', verbose_name='Logotipo2', null=True, blank=True)

    def __str__(self):
        return self.nombre_institucion