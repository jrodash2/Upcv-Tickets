from django.db import models
from django.contrib.auth.models import User
from datetime import datetime

class Empleado(models.Model):
    dpi = models.CharField(max_length=15, unique=True, null=False, blank=False)  # Agregamos el campo DPI
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    imagen = models.ImageField(upload_to='card_images/', null=True, blank=True)
    tipoc = models.CharField(max_length=100)
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
        return self.fecha_vencimiento.strftime('%Y-%m-%d')
    
    @property
    def fecha_inicio_formateada(self):
        return self.fecha_inicio.strftime('%Y-%m-%d')

    def save(self, *args, **kwargs):
        # Convertir la fecha de vencimiento si es una cadena
        if isinstance(self.fecha_vencimiento, str):
            try:
                self.fecha_vencimiento = datetime.strptime(self.fecha_vencimiento, '%Y-%m-%d').date()
            except ValueError:
                raise ValueError(f"Fecha vencimiento '{self.fecha_vencimiento}' no es válida.")
        
        # Convertir la fecha de inicio si es una cadena
        if isinstance(self.fecha_inicio, str):
            try:
                self.fecha_inicio = datetime.strptime(self.fecha_inicio, '%Y-%m-%d').date()
            except ValueError:
                raise ValueError(f"Fecha Inicio '{self.fecha_inicio}' no es válida.")
            
        if self.fecha_vencimiento <= datetime.today().date():
            self.activo = False
        
        # Llamar al método save de la clase base
        super().save(*args, **kwargs)
