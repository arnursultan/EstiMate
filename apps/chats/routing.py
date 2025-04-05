from django.urls import re_path
from . import consumers

# Маршруты WebSocket
websocket_urlpatterns = [
    re_path(r'ws/chat/(?P<chat_id>\d+)/$', consumers.ChatConsumer.as_asgi()),
]