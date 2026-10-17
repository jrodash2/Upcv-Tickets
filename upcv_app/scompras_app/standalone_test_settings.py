"""Configuración de pruebas aisladas; no usar como settings de producción."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = 'solo-pruebas-aisladas-scompras'
DEBUG = True
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'django.contrib.humanize', 'scompras_app',
]
MIDDLEWARE = [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware', 'django.contrib.messages.middleware.MessageMiddleware',
]
ROOT_URLCONF = 'scompras_app.standalone_test_urls'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates', 'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request', 'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages', 'scompras_app.context_processors.grupo_usuario',
        'scompras_app.context_processors.datos_institucion', 'scompras_app.context_processors.permisos_configuracion',
    ]},
}]
DATABASES = {'default': {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': os.environ.get('COMPRAS_TEST_DB_NAME', 'scompras_aislado'),
    'USER': os.environ.get('COMPRAS_TEST_DB_USER', ''),
    'PASSWORD': os.environ.get('COMPRAS_TEST_DB_PASSWORD', ''),
    'HOST': os.environ.get('COMPRAS_TEST_DB_HOST', 'localhost'),
    'PORT': os.environ.get('COMPRAS_TEST_DB_PORT', '5432'),
}}
LANGUAGE_CODE = 'es-gt'
TIME_ZONE = 'America/Guatemala'
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
STATIC_URL = '/static/'
MEDIA_URL = '/media/'
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
# La URL carga views.py, formularios y modelos reales de Compras, sin otras apps.
