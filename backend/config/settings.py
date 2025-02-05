import os
from pathlib import Path
from datetime import timedelta

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB', 'dbname'),
        'USER': os.getenv('POSTGRES_USER', 'user'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'password'),
        'HOST': os.getenv('POSTGRES_HOST', 'localhost'),  # Use 'localhost' as default instead of 'db'
        'PORT': os.getenv('POSTGRES_PORT', '5432'),
    }
}

# Redis Configuration
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Media files configuration
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# For development, allow all hosts to access media files
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",  # React development server
    "https://your-production-frontend.com"
]

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS']

# For development, serve media files
if DEBUG:
    INSTALLED_APPS += ['django.contrib.staticfiles']
    MIDDLEWARE += ['whitenoise.middleware.WhiteNoiseMiddleware']
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [REDIS_URL],
        },
    },
}

INSTALLED_APPS = [
    # ... other apps ...
    'chat.apps.ChatConfig',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
} 