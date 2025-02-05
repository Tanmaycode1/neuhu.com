from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from chat.routing import websocket_urlpatterns
from chat.middleware import WebSocketJWTAuthMiddleware

application = ProtocolTypeRouter({
    'websocket': AllowedHostsOriginValidator(
        WebSocketJWTAuthMiddleware(
            URLRouter(websocket_urlpatterns)
        )
    ),
})