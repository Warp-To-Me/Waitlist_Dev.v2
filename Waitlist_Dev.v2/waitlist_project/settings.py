import os
from pathlib import Path
from dotenv import load_dotenv
import pymysql

# Load environment variables from .env file
load_dotenv()

# Initialize PyMySQL as MySQLdb driver
pymysql.install_as_MySQLdb()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-default-key-change-me')

DEBUG = True

ALLOWED_HOSTS = ['*']

# Loads from .env as a comma-separated string (e.g., https://site.com,https://www.site.com)
# Defaults to an empty list if not found.
csrf_trusted_env = os.getenv('CSRF_TRUSTED_ORIGINS', '')
CSRF_TRUSTED_ORIGINS = [origin for origin in csrf_trusted_env.split(',') if origin]

# Application definition
INSTALLED_APPS = [
    'daphne', 
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize', # Added for number formatting (1,000,000)
    
    # Third party
    'channels',
    'django_apscheduler',
    
    # Local Apps
    'core',
    'esi_auth',
    'pilot_data',
    'waitlist_data',
    'esi_calls',
    'scheduler',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'waitlist_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.navbar_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'waitlist_project.wsgi.application'
ASGI_APPLICATION = "waitlist_project.asgi.application"

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('DB_NAME', 'waitlist'),
        'USER': os.getenv('DB_USER', 'root'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', '127.0.0.1'),
        'PORT': os.getenv('DB_PORT', '3306'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# EVE Online Configuration
EVE_CLIENT_ID = os.getenv('EVE_CLIENT_ID')
EVE_CALLBACK_URL = os.getenv('EVE_CALLBACK_URL', 'http://localhost:8000/auth/sso/callback/')

EVE_SCOPES = (
    "publicData "
    "esi-skills.read_skills.v1 "
    "esi-skills.read_skillqueue.v1 "
    "esi-clones.read_implants.v1 "
    "esi-location.read_ship_type.v1"
)

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer"
    }
}

# Scheduler Formatting
APSCHEDULER_DATETIME_FORMAT = "N j, Y, f:s a"
APSCHEDULER_RUN_NOW_TIMEOUT = 25