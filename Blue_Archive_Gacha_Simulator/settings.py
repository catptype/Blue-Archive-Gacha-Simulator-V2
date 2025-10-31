import os
from pathlib import Path
import dj_database_url

# ==============================================================================
# CORE PATHS & CONFIGURATION
# ==============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent

# Environment
IS_PRODUCTION = os.environ.get('PRODUCTION', '0') == '1'
USE_HTTPS = os.environ.get('USE_HTTPS', '0') == '1'
SECRET_KEY = os.environ.get('SECRET_KEY', 'a-default-development-secret-key')
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')
# ALLOWED_HOSTS = ['*']

CORS_ALLOWED_ORIGINS = ["http://localhost:5173"]

# For Render deployments
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

DEBUG = not IS_PRODUCTION

# ==============================================================================
# APPLICATION DEFINITION
# ==============================================================================

INSTALLED_APPS = [
    # Django apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',

    # Third-party apps
    'corsheaders',
    'drf_yasg',
    'rest_framework',
    'webpack_boilerplate',

    # Local apps
    'app_web',
]
if DEBUG:
    INSTALLED_APPS += ['django_browser_reload']

# ==============================================================================
# MIDDLEWARE
# ==============================================================================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # WhiteNoise
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware', # CORS middleware
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
if DEBUG:
    MIDDLEWARE += ['django_browser_reload.middleware.BrowserReloadMiddleware']

# ==============================================================================
# URLS, TEMPLATES, & WSGI
# ==============================================================================

ROOT_URLCONF = 'Blue_Archive_Gacha_Simulator.urls'
WSGI_APPLICATION = 'Blue_Archive_Gacha_Simulator.wsgi.application'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# ==============================================================================
# DATABASE
# ==============================================================================

if IS_PRODUCTION:
    # Use the DATABASE_URL environment variable provided by Render.
    # ssl_require=True is essential for secure connections to Render's databases.
    DATABASES = {
        'default': dj_database_url.config(conn_max_age=600, ssl_require=True)
    }
else:
    # Keep using SQLite for local development
    DATABASES = {
        'default': { 'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3' }
    }

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==============================================================================
# CACHES
# ==============================================================================

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-gacha-simulator-snowflake', # Can be any unique string
    }
}

# ==============================================================================
# AUTHENTICATION & SECURITY
# ==============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LOGIN_REDIRECT_URL = '/dashboard/' 
LOGOUT_REDIRECT_URL = '/'

if USE_HTTPS: 
    SECURE_SSL_REDIRECT = True # Set true if use HTTPS (W008)
    SESSION_COOKIE_SECURE = True # Set true if use HTTPS (W012)
    CSRF_COOKIE_SECURE = True # Set true if use HTTPS (W016)
else:
    SECURE_SSL_REDIRECT = False 
    SESSION_COOKIE_SECURE = False 
    CSRF_COOKIE_SECURE = False 

SECURE_CROSS_ORIGIN_OPENER_POLICY = None

CORS_ALLOW_ALL_ORIGINS = not IS_PRODUCTION

# ==============================================================================
# INTERNATIONALIZATION & STATIC FILES
# ==============================================================================

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [
    BASE_DIR / "frontend/build",
    BASE_DIR / "static",
]

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ==============================================================================
# THIRD-PARTY & DEVELOPMENT-ONLY SETTINGS
# ==============================================================================

WEBPACK_LOADER = {
    'MANIFEST_FILE': BASE_DIR / "frontend/build/manifest.json",
}

# ==============================================================================
# LOGGING CONFIGURATION
# ==============================================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}