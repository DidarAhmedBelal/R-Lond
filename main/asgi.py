"""
ASGI config for main project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

# import os

# from django.core.asgi import get_asgi_application

# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')

# application = get_asgi_application()


import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter
from channels.routing import URLRouter
from channels.security.websocket import AllowedHostsOriginValidator


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
django_asgi_app = get_asgi_application()



from chat.middleware import JWTAuthMiddleware
from chat.routing import websocket_urlpatterns
from chat.routing import websocket_urlpatterns as chat_websocket_urlpatterns
from notification.routing import websocket_urlpatterns as notification_websocket_urlpatterns



application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            JWTAuthMiddleware(URLRouter(
                websocket_urlpatterns
                + chat_websocket_urlpatterns
                + notification_websocket_urlpatterns
                ))
        ),
    },
)
