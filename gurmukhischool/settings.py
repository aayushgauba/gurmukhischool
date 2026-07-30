from pathlib import Path
import os
from django.core.exceptions import ImproperlyConfigured
from django.utils.csp import CSP
from dotenv import load_dotenv
SETTINGS_PATH = os.path.dirname(os.path.dirname(__file__))
# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in ('1', 'true', 'yes', 'on'):
        return True
    if normalized in ('0', 'false', 'no', 'off'):
        return False
    raise ImproperlyConfigured(
        f'{name} must be one of: true, false, 1, 0, yes, no, on, off'
    )


def env_int(name, default):
    value = os.environ.get(name, str(default))
    try:
        return int(value)
    except ValueError as exc:
        raise ImproperlyConfigured(f'{name} must be an integer') from exc


def env_list(name, default=''):
    return [
        item.strip()
        for item in os.environ.get(name, default).split(',')
        if item.strip()
    ]


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env_bool('DJANGO_DEBUG', False)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY and DEBUG:
    SECRET_KEY = 'django-insecure-local-development-only'
elif not SECRET_KEY:
    raise ImproperlyConfigured(
        'DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is false'
    )

ALLOWED_HOSTS = env_list(
    'DJANGO_ALLOWED_HOSTS',
    'localhost,127.0.0.1',
)
CSRF_TRUSTED_ORIGINS = env_list('DJANGO_CSRF_TRUSTED_ORIGINS')
# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'pages.apps.PagesConfig',
    'portal',
    'main',
    'crispy_forms',
    'crispy_bootstrap5',
    'django_select2',
    'aiwaf.django',
]

TINYMCE_DEFAULT_CONFIG = {
    'height': 360,
    'width': 800,
    'cleanup_on_startup': True,
    'custom_undo_redo_levels': 20,
    'selector': 'textarea',
    'theme': 'silver',
    'plugins': '''
        textcolor save link image media preview codesample contextmenu table code lists fullscreen
        insertdatetime nonbreaking contextmenu directionality searchreplace wordcount visualblocks
        visualchars code fullscreen autolink lists charmap print hr anchor pagebreak
    ''',
    'toolbar1': '''
        fullscreen preview bold italic underline | fontselect, fontsizeselect | forecolor backcolor |
        alignleft alignright | aligncenter alignjustify | indent outdent | bullist numlist table |
        link image media | codesample
    ''',
    'toolbar2': '''
        visualblocks visualchars | charmap hr pagebreak nonbreaking anchor | code
    ''',
    'contextmenu': 'formats | link image',
    'menubar': True,
    'statusbar': True,
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.csp.ContentSecurityPolicyMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'aiwaf.django.middleware.JsonExceptionMiddleware',
    'aiwaf.django.middleware.GeoBlockMiddleware',
    'aiwaf.django.middleware.IPAndKeywordBlockMiddleware',
    'aiwaf.django.middleware.RateLimitMiddleware',
    'aiwaf.django.middleware.AIAnomalyMiddleware',
    'aiwaf.django.middleware.HoneypotTimingMiddleware',
    'aiwaf.django.middleware.UUIDTamperMiddleware',
    'aiwaf.django.middleware.HeaderValidationMiddleware',
    'aiwaf.django.middleware_logger.AIWAFLoggerMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'gurmukhischool.urls'
SECURE_CSP = {
    'default-src': [CSP.SELF],
    'script-src': [CSP.SELF, CSP.NONCE],
    'style-src': [CSP.SELF, CSP.NONCE],
}

AIWAF_EXEMPT_PATHS = [
    '/static/',
    '/media/',
    '/favicon.ico',
    '/robots.txt',
    '/sitemap.xml',
    '/.well-known/',
]


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(SETTINGS_PATH, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.csp',
            ],
        },
    },
]

WSGI_APPLICATION = 'gurmukhischool.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DB_ENGINE = os.environ.get(
    'DB_ENGINE',
    'django.db.backends.postgresql',
)
DEFAULT_DB_PORT = '3306' if DB_ENGINE.endswith('mysql') else '5432'

DATABASES = {
    'default': {
        'ENGINE': DB_ENGINE,
        'NAME': os.environ.get('DB_NAME', 'gurudwara'),
        'USER': os.environ.get('DB_USER', 'postgres'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', DEFAULT_DB_PORT),
    }
}


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

AUTH_USER_MODEL = 'portal.CustomUser'

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = '/static/' 
STATICFILES_DIRS = [ BASE_DIR / "static", ] 
STATIC_ROOT = BASE_DIR / "staticfiles"
# Default primary key field type
# https://docs.djangoproject.com/en/6.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.smtp.EmailBackend',
)
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'localhost')
EMAIL_PORT = env_int('EMAIL_PORT', 587)
EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', True)
EMAIL_USE_SSL = env_bool('EMAIL_USE_SSL', False)
if EMAIL_USE_TLS and EMAIL_USE_SSL:
    raise ImproperlyConfigured(
        'EMAIL_USE_TLS and EMAIL_USE_SSL cannot both be true'
    )
EMAIL_TIMEOUT = env_int('EMAIL_TIMEOUT', 30)
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get(
    'DEFAULT_FROM_EMAIL',
    EMAIL_HOST_USER or 'webmaster@localhost',
)
SERVER_EMAIL = os.environ.get('SERVER_EMAIL', DEFAULT_FROM_EMAIL)
EMAIL_IMAP_HOST = os.environ.get('EMAIL_IMAP_HOST', '')
EMAIL_IMAP_PORT = env_int('EMAIL_IMAP_PORT', 993)
EMAIL_IMAP_USE_SSL = env_bool('EMAIL_IMAP_USE_SSL', True)
EMAIL_IMAP_USE_TLS = env_bool('EMAIL_IMAP_USE_TLS', False)
if EMAIL_IMAP_USE_SSL and EMAIL_IMAP_USE_TLS:
    raise ImproperlyConfigured(
        'EMAIL_IMAP_USE_SSL and EMAIL_IMAP_USE_TLS cannot both be true'
    )
EMAIL_IMAP_USER = os.environ.get('EMAIL_IMAP_USER', EMAIL_HOST_USER)
EMAIL_IMAP_PASSWORD = os.environ.get(
    'EMAIL_IMAP_PASSWORD',
    EMAIL_HOST_PASSWORD,
)
EMAIL_IMAP_FOLDER = os.environ.get('EMAIL_IMAP_FOLDER', 'INBOX')
EMAIL_IMAP_SYNC_LIMIT = env_int('EMAIL_IMAP_SYNC_LIMIT', 100)
ACTIVATION_RESEND_COOLDOWN_SECONDS = env_int(
    'ACTIVATION_RESEND_COOLDOWN_SECONDS',
    300,
)
ACTIVATION_EMAIL_MAX_ATTEMPTS = env_int(
    'ACTIVATION_EMAIL_MAX_ATTEMPTS',
    5,
)
CRISPY_TEMPLATE_PACK = 'bootstrap5'
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
LOGIN_URL = 'login'
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
SECURE_SSL_REDIRECT = not DEBUG and env_bool(
    'DJANGO_SECURE_SSL_REDIRECT',
    True,
)
if env_bool('DJANGO_TRUST_X_FORWARDED_PROTO', False):
    # Enable only when the application is behind a trusted TLS-terminating
    # proxy that sets and sanitizes X-Forwarded-Proto.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

SECURE_HSTS_SECONDS = (
    env_int('DJANGO_HSTS_SECONDS', 300)
    if not DEBUG
    else 0
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = (
    not DEBUG
    and env_bool('DJANGO_HSTS_INCLUDE_SUBDOMAINS', False)
)
SECURE_HSTS_PRELOAD = (
    not DEBUG
    and env_bool('DJANGO_HSTS_PRELOAD', False)
)
X_FRAME_OPTIONS = 'DENY'
