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

# Channel Layers Configuration
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [(os.environ.get('CHANNEL_LAYERS_HOST', 'redis'), 6379)],
            "capacity": 1500,
            "expiry": 10,  # Message expiry in seconds
            "group_expiry": 60,  # Group expiry in seconds
            "channel_capacity": {
                "http.request": 1000,
                "http.response!*": 1000,
                "websocket.send!*": 1000,
            },
        },
    },
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
        "LOCATION": f"redis://{os.environ.get('CHANNEL_LAYERS_HOST', 'redis')}:6379/0",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,  # seconds
            "SOCKET_TIMEOUT": 5,  # seconds
            "RETRY_ON_TIMEOUT": True,
            "MAX_CONNECTIONS": 1000,
            "CONNECTION_POOL_KWARGS": {"max_connections": 100},
        }
    }
}

# Celery
CELERY_BROKER_URL = f"redis://{os.environ.get('CHANNEL_LAYERS_HOST', 'redis')}:6379/0"
CELERY_RESULT_BACKEND = f"redis://{os.environ.get('CHANNEL_LAYERS_HOST', 'redis')}:6379/0" 