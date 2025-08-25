# import os
# from django.core.asgi import get_asgi_application
# from channels.routing import ProtocolTypeRouter, URLRouter
# from channels.security.websocket import AllowedHostsOriginValidator

# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')

# django_asgi_app = get_asgi_application()

# from chat.middleware import JWTAuthMiddleware
# from chat.routing import websocket_urlpatterns as chat_ws
# from notification.routing import websocket_urlpatterns as notification_ws

# application = ProtocolTypeRouter(
#     {
#         "http": django_asgi_app,
#         "websocket": AllowedHostsOriginValidator(
#             JWTAuthMiddleware(
#                 URLRouter(
#                     chat_ws + notification_ws
#                 )
#             )
#         ),
#     },
# )


import os
 
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter
from channels.routing import URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
 
 
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
django_asgi_app = get_asgi_application()
 
 
 
# from chatbot.routing import websocket_urlpatterns
from chat.middleware import JWTAuthMiddleware
 
from chat.routing import websocket_urlpatterns as chat_websocket_urlpatterns
from notification.routing import websocket_urlpatterns as notification_websocket_urlpatterns
 
 
application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            JWTAuthMiddleware(URLRouter(
                # websocket_urlpatterns
                 chat_websocket_urlpatterns
                + notification_websocket_urlpatterns
                ))
        ),
    },
)
 