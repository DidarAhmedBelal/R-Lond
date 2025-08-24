# chat/routing.py
from django.urls import re_path,  path

from . import consumers

websocket_urlpatterns = [
    re_path('ws/chat/room/$', consumers.ChatConsumer.as_asgi()),
]