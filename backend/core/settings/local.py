from .base import *

# Override any base settings here
DEBUG = True

# Add any local-specific settings here
CORS_ALLOW_ALL_ORIGINS = True

# Database settings for local development
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'dbname'),
        'USER': os.environ.get('POSTGRES_USER', 'user'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'password'),
        'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
    }
}


# CORS settings
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Email settings - Console backend for development
if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Redis Cache Configuration
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://redis:6379/0",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}

# Celery
CELERY_BROKER_URL = 'redis://redis:6379/0'
CELERY_RESULT_BACKEND = 'redis://redis:6379/0' 