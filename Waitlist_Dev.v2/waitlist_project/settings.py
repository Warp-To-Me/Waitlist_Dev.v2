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
    
    # FIX: Use 'fernet_fields' instead of 'django_fernet_fields'
    'fernet_fields',
    
    # Third party
    'channels', # REQUIRED: Core ASGI/WebSocket support
    #'django_apscheduler',
    
    # Third party
    'rest_framework',

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
if os.getenv('USE_SQLITE', 'False') == 'True':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
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

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# EVE Online Configuration
EVE_CLIENT_ID = os.getenv('EVE_CLIENT_ID')
EVE_CALLBACK_URL = os.getenv('EVE_CALLBACK_URL', 'http://localhost:8000/auth/sso/callback/')

# --- SCOPE CONFIGURATION ---

# 1. Base Scopes (Required for all pilots)
EVE_SCOPES_BASE = (
    "publicData "
    "esi-skills.read_skills.v1 "
    "esi-skills.read_skillqueue.v1 "
    "esi-clones.read_implants.v1 "
    "esi-location.read_ship_type.v1 "
    "esi-location.read_online.v1 "
    "esi-wallet.read_character_wallet.v1 "
    "esi-characters.read_loyalty.v1"
)

# 2. FC Scopes (Required only for Fleet Commanders)
EVE_SCOPES_FC = (
    "esi-fleets.read_fleet.v1 "
    "esi-fleets.write_fleet.v1"
)

# 3. SRP Manager Scopes (NEW)
EVE_SCOPES_SRP = (
    "esi-wallet.read_corporation_wallets.v1"
)

# 4. Combined Master List (For Auditing/Backwards Compatibility)
EVE_SCOPES = f"{EVE_SCOPES_BASE} {EVE_SCOPES_FC} {EVE_SCOPES_SRP}"

# --- CELERY SETTINGS ---
# 1. Connection to Redis (Running in WSL)
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://127.0.0.1:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://127.0.0.1:6379/0')

# 2. Timezone matches Django
CELERY_TIMEZONE = "UTC"

# 3. Connection Retry (Required for newer Celery versions)
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# --- CHANNEL LAYERS (Redis Config) ---
# We reuse the CELERY_BROKER_URL for Channels to keep config DRY.
# This ensures WebSockets work across multiple worker processes.
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [CELERY_BROKER_URL],
        },
    },
}

# 4. Beat Schedule (Replaces APScheduler)
from celery.schedules import crontab

# Run every 1 minute
CELERY_BEAT_SCHEDULE = {
    'dispatch-stale-characters-every-minute': {
        'task': 'scheduler.tasks.dispatch_stale_characters',
        'schedule': crontab(minute='*'), # Runs every 1 minute
    },
    'refresh-srp-wallet-hourly': {
        'task': 'scheduler.tasks.refresh_srp_wallet_task',
        'schedule': crontab(minute=0), # Runs at the start of every hour
    },
    'check-expired-bans-every-minute': {
        'task': 'core.tasks.check_expired_bans',
        'schedule': crontab(minute='*'),
    },
}

# 5. SAFETY & RATE LIMITS
# This limits the worker to only grabbing 1 task at a time, preventing it from hoarding tasks if ESI is slow.
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# --- AUTHENTICATION SETTINGS ---
LOGIN_URL = 'access_denied'      # Redirect here instead of 'sso_login'
LOGIN_REDIRECT_URL = 'profile'   
LOGOUT_REDIRECT_URL = 'landing_page'

# --- CELERY GEVENT FIX ---
import os
import sys

# Detect if running as Celery worker
if 'celery' in sys.argv[0]:
    os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"