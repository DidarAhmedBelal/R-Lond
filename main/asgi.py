import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')

django_asgi_app = get_asgi_application()

from chat.middleware import JWTAuthMiddleware
from chat.routing import websocket_urlpatterns as chat_ws
from notification.routing import websocket_urlpatterns as notification_ws

from channels.security.websocket import OriginValidator

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": OriginValidator(
            JWTAuthMiddleware(
                URLRouter(chat_ws + notification_ws)
            ),
            ["https://yourfrontend.com", "http://localhost:5173"]
        ),
    },
)
