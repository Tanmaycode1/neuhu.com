import os

# Set default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.local')

# Import all settings from the appropriate module
if os.environ.get('DJANGO_ENV') == 'production':
    from .production import *
else:
    from .local import * 