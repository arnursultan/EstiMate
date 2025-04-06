import logging
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken, TokenError
from django.contrib.auth import get_user_model
from urllib.parse import parse_qs
import jwt
from django.conf import settings

logger = logging.getLogger(__name__)
User = get_user_model()


@database_sync_to_async
def get_user_from_token(token_key):
    """Получение пользователя по JWT токену."""
    try:
        # Декодируем токен и получаем ID пользователя
        access_token = AccessToken(token_key)
        user_id = access_token['user_id']

        # Получаем пользователя из базы данных
        user = User.objects.get(id=user_id)

        # Проверка активности пользователя
        if not user.is_active:
            logger.warning(f"Пользователь {user_id} не активен")
            return AnonymousUser()

        logger.info(f"Пользователь {user_id} аутентифицирован через WebSocket")
        return user
    except (User.DoesNotExist, TokenError, jwt.PyJWTError) as e:
        logger.warning(f"Ошибка аутентификации через WebSocket: {str(e)}")
        return AnonymousUser()


class TokenAuthMiddleware(BaseMiddleware):
    """
    Middleware для аутентификации WebSocket соединений через JWT токен.

    Токен может быть передан:
    1. В параметре URL: ?token=<jwt_token>
    2. В заголовке: Authorization: Bearer <jwt_token>
    """

    async def __call__(self, scope, receive, send):
        # Извлекаем параметры запроса из URL
        query_string = scope.get("query_string", b"").decode()
        query_params = parse_qs(query_string)

        # Получаем токен из параметров запроса
        token = query_params.get("token", [None])[0]

        # Если токен не найден в URL, проверяем заголовки
        if token is None and 'headers' in scope:
            headers = dict(scope['headers'])
            auth_header = headers.get(b'authorization', b'').decode()

            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]

        # Если токен найден, аутентифицируем пользователя
        if token:
            scope["user"] = await get_user_from_token(token)
        else:
            scope["user"] = AnonymousUser()
            logger.warning("WebSocket соединение без токена аутентификации")

        return await super().__call__(scope, receive, send)