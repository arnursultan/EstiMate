"""
ASGI config для проекта backend.

Экспортирует ASGI приложение как переменную module-level "application".
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()  # Важно добавить эту строку перед импортом других модулей

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from apps.chats.middleware import TokenAuthMiddleware
import apps.chats.routing

# Инициализация Django ASGI приложения
django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    # HTTP запросы идут через стандартное Django ASGI приложение
    "http": django_asgi_app,

    # WebSocket запросы идут через TokenAuthMiddleware для аутентификации
    "websocket": AllowedHostsOriginValidator(
        TokenAuthMiddleware(
            URLRouter(
                apps.chats.routing.websocket_urlpatterns
            )
        )
    ),
})