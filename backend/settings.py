import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
dotenv_path = os.path.join(BASE_DIR, ".env")  # Явный путь
load_dotenv(dotenv_path)
from celery.schedules import crontab

print(f"DEBUG = {os.getenv('DEBUG')}")
print(f"DB_NAME = {os.getenv('DB_NAME')}")

SECRET_KEY = os.getenv("SECRET_KEY", "default-secret-key")
DEBUG = True
# SERVER_IP = os.getenv("SERVER_IP", "123.456.78.90")
# ALLOWED_HOSTS = [SERVER_IP, "127.0.0.1", "localhost"]
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "0.0.0.0", "*", "baielapp.kg", "www.baielapp.kg"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "rest_framework",
    "rest_framework.authtoken",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",

    "drf_yasg",
    "django_filters",
    "channels",
    "corsheaders",
    'django_celery_beat',

    "apps.users",
    "apps.products",
    "apps.stores",
    "apps.orders",
    "apps.finance",
    "apps.chats",
    "apps.notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# CORS_ALLOWED_ORIGINS = [
#     "http://127.0.0.1:8000",
#     "http://localhost:8000",
#     f"http://{SERVER_IP}",
#     f"https://{SERVER_IP}",
# ]
CORS_ALLOWED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "https://baielapp.kg",
    "http://baielapp.kg",
]

CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

ROOT_URLCONF = 'backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]



ASGI_APPLICATION = "backend.asgi.application"

WSGI_APPLICATION = 'backend.wsgi.application'

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("localhost", 6379)],
        },
    },
}

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv("DB_NAME"),
        'USER': os.getenv("DB_USER"),
        'PASSWORD': os.getenv("DB_PASSWORD"),
        'HOST': os.getenv("DB_HOST"),
        'PORT': os.getenv("DB_PORT"),
        'OPTIONS': {
            'client_encoding': 'UTF8',
        }
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}



REST_AUTH_REGISTER_SERIALIZERS = {
    "REGISTER_SERIALIZER": "apps.users.serializers.CustomRegisterSerializer"
}
REST_AUTH_SERIALIZERS = {
    "USER_DETAILS_SERIALIZER": "apps.users.serializers.UserSerializer"
}

AUTH_USER_MODEL = "users.User"

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=int(os.getenv("ACCESS_TOKEN_LIFETIME", 1))),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=int(os.getenv("REFRESH_TOKEN_LIFETIME", 7))),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
}


CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'

CELERY_BEAT_SCHEDULE = {
    'generate-daily-finance': {
        'task': 'apps.finance.tasks.run_daily_finance_statistics',
        'schedule': crontab(hour=0, minute=5),
    },
    'archive-daily-data': {
        'task': 'apps.finance.tasks.archive_daily_data',
        'schedule': crontab(hour=23, minute=55),
    },
}

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}


EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False") == "True"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")

# STATIC_ROOT = os.getenv("STATIC_ROOT", "/var/www/bai_el/static/")
# MEDIA_ROOT = os.getenv("MEDIA_ROOT", "/var/www/bai_el/media/")



LANGUAGE_CODE = 'ru-RU'
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

'''Пока чекаем на локалке поэтому все настройки безопасности отключены'''
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_BROWSER_XSS_FILTER = False
SECURE_CONTENT_TYPE_NOSNIFF = False
SECURE_HSTS_SECONDS = 0 #31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

STATIC_URL = "/static/"
STATICFILES_DIRS = [os.path.join(BASE_DIR, "staticfiles")]  # Другое имя
STATIC_ROOT = os.path.join(BASE_DIR, "static")

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

SWAGGER_USE_COMPAT_RENDERERS = False
SWAGGER_SETTINGS = {
    "DEFAULT_INFO": "backend.urls.schema_view",
    "USE_SESSION_AUTH": False,  # Отключаем Basic Auth (чтобы не было полей username/password)
    "JSON_EDITOR": True,
    "SECURITY_DEFINITIONS": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "Введите JWT токен в формате: Bearer <your_token>",
        }
    },
    "DEFAULT_SECURITY": [{"Bearer": []}],
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOG_DIR = os.path.join(BASE_DIR, 'logs')

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": "logs/store_payments.log",
            "formatter": "verbose",
            "encoding": "utf-8",
        },
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": True,
        },
        "store_payments": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
