import os
import django
from django.core.asgi import get_asgi_application

# Set up Django ASGI application first
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from chat.routing import websocket_urlpatterns
from chat.middleware import WebSocketJWTAuthMiddleware

# Get the Django ASGI application for HTTP handling
django_asgi_app = get_asgi_application()

# Create the ASGI application
application = ProtocolTypeRouter({
    # Django's ASGI application for handling HTTP requests
    "http": django_asgi_app,

    # WebSocket handler with auth and routing
    "websocket": AllowedHostsOriginValidator(
        WebSocketJWTAuthMiddleware(
            URLRouter(websocket_urlpatterns)
        )
    ),
})