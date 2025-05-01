import re
from django.core.cache import cache
# Убрали неиспользуемые импорты: Sum, get_object_or_404
# from django.db.models import Sum
from django.shortcuts import get_object_or_404 # Оставляем для других views
from rest_framework import generics, permissions, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser as DRFIsAdminUser # Переименуем стандартный
from .models import User
from .serializers import (
     UserSerializer, LoginSerializer, UserDetailSerializer,
     UserUpdateSerializer, UserPutSerializer
)
from apps.users.tasks import send_reset_email
# Импортируем наши кастомные разрешения
from apps.users.permissions import IsAdminUser, IsOwnerOrAdmin
from rest_framework_simplejwt.views import TokenRefreshView
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import random
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken, BlacklistedToken, OutstandingToken
# Убрали неиспользуемые импорты: datetime, time, timezone
# from datetime import datetime, time
# from django.utils import timezone
import logging # Добавим логирование
from rest_framework import serializers
from tokenize import TokenError



logger = logging.getLogger(__name__) # Инициализируем логгер

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
         # ... (описание схемы как было) ...
     )
    def post(self, request, *args, **kwargs):
        logger.info(f"Попытка регистрации: {request.data.get('email')}")
        return super().post(request, *args, **kwargs)

    def perform_create(self, serializer):
        # Статус pending по умолчанию задается в модели
        user = serializer.save(role="partner")
        logger.info(f"Пользователь {user.email} успешно зарегистрирован со статусом pending.")


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        # ... (описание схемы как было) ...
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        try:
             serializer.is_valid(raise_exception=True)
        except serializers.ValidationError as e:
             logger.warning(f"Неудачная попытка входа: {request.data.get('email')}, ошибка: {e.detail}")
             # Возвращаем детали ошибки валидации
             return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)


        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)

        logger.info(f"Успешный вход пользователя: {user.email}")
        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user_id": user.id, # Добавим user_id
            "role": user.role   # Добавим роль
        }, status=status.HTTP_200_OK)


class PartnerProfileAPIView(APIView):
    permission_classes = [IsAuthenticated] # Общее разрешение, детали проверим ниже
    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(
         # ... (описание схемы как было) ...
     )
    def get(self, request):
        # Пользователь может видеть только свой профиль
        serializer = UserDetailSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        # ... (описание схемы как было) ...
                         )
    def patch(self, request):
        # Пользователь может обновлять только свой профиль
        serializer = UserUpdateSerializer(instance=request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        logger.info(f"Пользователь {request.user.email} обновил свой профиль (PATCH).")
        return Response(UserDetailSerializer(request.user).data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        # ... (описание схемы как было) ...
    )
    def put(self, request):
         # Пользователь может обновлять только свой профиль
        serializer = UserPutSerializer(instance=request.user, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        logger.info(f"Пользователь {request.user.email} обновил свой профиль (PUT).")
        return Response(UserDetailSerializer(request.user).data, status=status.HTTP_200_OK)


class AdminUserAPIView(APIView):
    permission_classes = [IsAdminUser] # Используем кастомный IsAdminUser

    @swagger_auto_schema(
        # ... (параметры как были) ...
        responses={200: UserDetailSerializer(many=True)}
    )
    def get(self, request):
        email = request.query_params.get('email')
        first_name = request.query_params.get('first_name')
        last_name = request.query_params.get('last_name')
        is_deleted_param = request.query_params.get('is_deleted') # Фильтр по удаленным

        # Начинаем с неудаленных пользователей
        users = User.objects.filter(is_deleted=False)

        # Позволяем админу видеть удаленных, если он явно запросил
        if is_deleted_param is not None:
             show_deleted = is_deleted_param.lower() == 'true'
             if show_deleted:
                  users = User.objects.filter(is_deleted=True) # Показываем только удаленных
             # Если is_deleted=false, то оставляем users = User.objects.filter(is_deleted=False)

        if email:
            users = users.filter(email__icontains=email)
        if first_name:
            users = users.filter(first_name__icontains=first_name)
        if last_name:
            users = users.filter(last_name__icontains=last_name)

        # Добавим сортировку
        users = users.order_by('last_name', 'first_name')

        serializer = UserDetailSerializer(users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminUserDetailAPIView(APIView):
    permission_classes = [IsAdminUser] # Только админ
    parser_classes = [MultiPartParser, FormParser]

    def get_object(self, pk):
         # Админ может смотреть и удаленных пользователей
        return get_object_or_404(User._base_manager.all(), pk=pk)

    @swagger_auto_schema(
        # ... (схема как была) ...
    )
    def get(self, request, pk):
        user = self.get_object(pk)
        serializer = UserDetailSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        # ... (схема как была) ...
    )
    def put(self, request, pk):
        user = self.get_object(pk)
        serializer = UserPutSerializer(instance=user, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        logger.info(f"Администратор {request.user.email} обновил профиль пользователя {user.email} (PUT).")
        return Response(UserDetailSerializer(user).data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
       # ... (схема как была) ...
    )
    def patch(self, request, pk):
        user = self.get_object(pk)
        serializer = UserUpdateSerializer(instance=user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        logger.info(f"Администратор {request.user.email} обновил профиль пользователя {user.email} (PATCH).")
        return Response(UserDetailSerializer(user).data, status=status.HTTP_200_OK)


class UserDeleteAPIView(APIView):
    """Мягкое удаление пользователя администратором."""
    permission_classes = [IsAdminUser] # Только админ

    def get_object(self, pk):
        # Получаем пользователя, даже если он уже удален (для идемпотентности)
        return get_object_or_404(User._base_manager.all(), pk=pk)

    @swagger_auto_schema(
        operation_summary="Мягкое удаление пользователя",
        responses={
            200: openapi.Response("Пользователь успешно помечен как удаленный"),
            400: 'Пользователь уже удален',
            404: 'Пользователь не найден'
        }
    )
    def delete(self, request, pk): # Используем метод DELETE
        user = self.get_object(pk)

        # Нельзя удалить самого себя
        if user == request.user:
             return Response(
                 {"detail": "Вы не можете удалить свой собственный аккаунт."},
                 status=status.HTTP_400_BAD_REQUEST
             )

        if user.is_deleted:
            return Response(
                {"detail": "Пользователь уже удален."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if user.soft_delete():
             logger.info(f"Администратор {request.user.email} удалил (мягко) пользователя {user.email}.")
             return Response({"detail": "Пользователь успешно помечен как удаленный"}, status=status.HTTP_200_OK)
        else:
             # soft_delete может вернуть False, если что-то пошло не так (хотя в текущей реализации не должен)
             logger.error(f"Ошибка при мягком удалении пользователя {user.email} администратором {request.user.email}.")
             return Response({"detail": "Не удалось удалить пользователя"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# --- НОВЫЙ View ---
class UserRestoreAPIView(APIView):
    """Восстановление мягко удаленного пользователя администратором."""
    permission_classes = [IsAdminUser] # Только админ

    def get_object(self, pk):
        # Получаем пользователя, даже если он удален
        return get_object_or_404(User._base_manager.all(), pk=pk)

    @swagger_auto_schema(
        operation_summary="Восстановление удаленного пользователя",
        responses={
            200: openapi.Response("Пользователь успешно восстановлен"),
            400: 'Пользователь не был удален',
            404: 'Пользователь не найден'
        }
    )
    def post(self, request, pk): # Используем метод POST для действия
        user = self.get_object(pk)

        if not user.is_deleted:
            return Response(
                {"detail": "Пользователь не был удален."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if user.restore():
             logger.info(f"Администратор {request.user.email} восстановил пользователя {user.email}.")
             return Response({"detail": "Пользователь успешно восстановлен"}, status=status.HTTP_200_OK)
        else:
             logger.error(f"Ошибка при восстановлении пользователя {user.email} администратором {request.user.email}.")
             return Response({"detail": "Не удалось восстановить пользователя"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DeactivateOwnAccountAPIView(APIView):
    """
    Деактивация собственного аккаунта (установка is_active=False).
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        # ... (схема как была) ...
    )
    def post(self, request):
        user = request.user

        if not user.is_active:
            return Response({"detail": "Аккаунт уже деактивирован."}, status=status.HTTP_400_BAD_REQUEST) # Изменен код на 400

        user.is_active = False
        user.save(update_fields=['is_active']) # Обновляем только одно поле
        logger.info(f"Пользователь {user.email} деактивировал свой аккаунт.")

        # Дополнительно: можно добавить логику выхода (инвалидация токенов)
        # try:
        #     refresh_token = request.data.get("refresh")
        #     if refresh_token:
        #         token = RefreshToken(refresh_token)
        #         token.blacklist()
        # except Exception as e:
        #     logger.warning(f"Не удалось добавить refresh токен в блэклист при деактивации аккаунта {user.email}: {e}")

        return Response({"detail": "Ваш аккаунт успешно деактивирован."}, status=status.HTTP_200_OK)


class UserBlockAPIView(APIView):
    permission_classes = [IsAdminUser] # Только админ

    def get_object(self, pk):
         # Работаем только с неудаленными пользователями
        return get_object_or_404(User, pk=pk, is_deleted=False)

    @swagger_auto_schema(
        # ... (схема как была) ...
        responses={
            200: openapi.Response("Пользователь успешно заблокирован", UserDetailSerializer), # Возвращаем данные
            400: "Пользователь уже заблокирован",
            404: "Пользователь не найден (или удален)"
        }
    )
    def post(self, request, pk):
        user = self.get_object(pk)

        if not user.is_active:
            return Response({"detail": "Пользователь уже заблокирован."}, status=status.HTTP_400_BAD_REQUEST)

        user.is_active = False
        user.save(update_fields=['is_active'])
        logger.info(f"Администратор {request.user.email} заблокировал пользователя {user.email}.")
        # Возвращаем обновленные данные пользователя
        return Response(UserDetailSerializer(user).data, status=status.HTTP_200_OK)


class UserUnblockAPIView(APIView):
    permission_classes = [IsAdminUser] # Только админ

    def get_object(self, pk):
         # Работаем только с неудаленными пользователями
        return get_object_or_404(User, pk=pk, is_deleted=False)

    @swagger_auto_schema(
        # ... (схема как была) ...
         responses={
            200: openapi.Response("Пользователь успешно разблокирован", UserDetailSerializer), # Возвращаем данные
            400: "Пользователь уже активен",
            404: "Пользователь не найден (или удален)"
        }
    )
    def post(self, request, pk):
        user = self.get_object(pk)

        if user.is_active:
            return Response({"detail": "Пользователь уже активен."}, status=status.HTTP_400_BAD_REQUEST)

        user.is_active = True
        user.save(update_fields=['is_active'])
        logger.info(f"Администратор {request.user.email} разблокировал пользователя {user.email}.")
        # Возвращаем обновленные данные пользователя
        return Response(UserDetailSerializer(user).data, status=status.HTTP_200_OK)


class PasswordResetView(APIView):
    permission_classes = [AllowAny]
    @swagger_auto_schema(
         # ... (схема как была) ...
    )
    def post(self, request):
        email = request.data.get("email")
        # Ищем только активных и не удаленных пользователей для сброса
        user = User.objects.filter(email=email, is_active=True, is_deleted=False).first()

        if not user:
             logger.warning(f"Попытка сброса пароля для несуществующего или неактивного пользователя: {email}")
             # Не говорим точно, найден ли email, для безопасности
             # return Response({"error": "Пользователь не найден или неактивен"}, status=status.HTTP_404_NOT_FOUND)
             # Вместо этого возвращаем общий успешный ответ, даже если пользователь не найден
             return Response({"message": "Если пользователь с таким email существует и активен, код отправлен."}, status=status.HTTP_200_OK)


        reset_token = str(random.randint(10000, 99999))
        user.token_reset = reset_token
        user.save(update_fields=['token_reset'])
        cache.set(f"reset_token_valid:{reset_token}", user.id, timeout=180) # Кешируем ID пользователя на 3 минуты

        if user.email:
            send_reset_email.delay(user.email, reset_token)
            logger.info(f"Отправлен код сброса пароля для пользователя {user.email}.")
            return Response({"message": "Код отправлен на email"}, status=status.HTTP_200_OK)

        # Эта часть не должна вызываться, если email есть
        logger.error(f"Не удалось отправить код сброса для пользователя {user.email}, т.к. email отсутствует (хотя он должен быть).")
        return Response({"error": "Не удалось отправить код"}, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetVerifyView(APIView):
    permission_classes = [AllowAny]
    @swagger_auto_schema(
        # ... (схема как была) ...
    )
    def post(self, request):
        reset_token = request.data.get("token")
        if not reset_token:
            return Response({"error": "Токен обязателен."}, status=status.HTTP_400_BAD_REQUEST)

        # Проверяем валидность токена в кеше
        user_id = cache.get(f"reset_token_valid:{reset_token}")
        if not user_id:
             logger.warning(f"Попытка верификации с невалидным или истекшим токеном: {reset_token}")
             return Response({"error": "Неверный код или срок его действия истёк."}, status=status.HTTP_400_BAD_REQUEST)

        # Проверяем, что токен соответствует пользователю в БД (на всякий случай)
        user = User.objects.filter(id=user_id, token_reset=reset_token, is_active=True, is_deleted=False).first()
        if not user:
             logger.error(f"Токен {reset_token} валиден в кеше для user_id {user_id}, но не найден в БД или пользователь неактивен.")
             # Удаляем невалидный токен из кеша
             cache.delete(f"reset_token_valid:{reset_token}")
             return Response({"error": "Неверный код или срок его действия истёк."}, status=status.HTTP_400_BAD_REQUEST)

        # Продлеваем жизнь токена в кеше еще на 5 минут для подтверждения
        cache.set(f"reset_token_valid:{reset_token}", user.id, timeout=300)
        logger.info(f"Код сброса {reset_token} успешно верифицирован для пользователя {user.email}.")
        return Response({"message": "Код подтверждён"}, status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    @swagger_auto_schema(
         # ... (схема как была) ...
    )
    def post(self, request):
        token = request.data.get("token")
        new_password = request.data.get("new_password")
        confirm_password = request.data.get("confirm_password")

        if not token:
            return Response({"error": "Токен подтверждения обязателен."}, status=status.HTTP_400_BAD_REQUEST)
        if not new_password or not confirm_password:
             return Response({"error": "Необходимо указать новый пароль и его подтверждение."}, status=status.HTTP_400_BAD_REQUEST)

        if new_password != confirm_password:
            return Response({"error": "Пароли не совпадают."}, status=status.HTTP_400_BAD_REQUEST)

        # Проверяем токен в кеше
        user_id = cache.get(f"reset_token_valid:{token}")
        if not user_id:
             logger.warning(f"Попытка смены пароля с невалидным или истекшим токеном: {token}")
             return Response({"error": "Неверный код или срок его действия истёк."}, status=status.HTTP_400_BAD_REQUEST)

        # Получаем пользователя
        user = User.objects.filter(id=user_id, token_reset=token, is_active=True, is_deleted=False).first()
        if not user:
             logger.error(f"Токен {token} валиден в кеше для user_id {user_id}, но не найден в БД или пользователь неактивен при подтверждении.")
             cache.delete(f"reset_token_valid:{token}")
             return Response({"error": "Неверный код или срок его действия истёк."}, status=status.HTTP_400_BAD_REQUEST)

        # Валидация пароля (используем валидатор)
        from .validators import validate_password
        try:
             validate_password(new_password)
        except serializers.ValidationError as e:
             return Response({"error": e.detail}, status=status.HTTP_400_BAD_REQUEST)

        if user.check_password(new_password):
            return Response({"error": "Новый пароль не должен совпадать с текущим."}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.token_reset = None # Сбрасываем токен
        user.save(update_fields=['password', 'token_reset'])

        # Удаляем токен из кеша
        cache.delete(f"reset_token_valid:{token}")

        logger.info(f"Пароль для пользователя {user.email} успешно изменен.")
        return Response({"message": "Пароль успешно изменён"}, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Выход пользователя из системы",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['refresh'],
            properties={
                'refresh': openapi.Schema(type=openapi.TYPE_STRING, description='Refresh токен для добавления в черный список')
            }
        ),
        responses={
             200: openapi.Response("Успешный выход"),
             400: "Неверный или отсутствующий токен",
             401: "Пользователь не аутентифицирован" # Хотя IsAuthenticated должна это покрыть
        }
    )
    def post(self, request):
        # IsAuthenticated уже проверил аутентификацию
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response({"error": "Refresh-токен обязателен"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token = RefreshToken(refresh_token)
            # Добавляем токен в черный список
            token.blacklist()
            logger.info(f"Пользователь {request.user.email} вышел из системы (токен {refresh_token[:10]}... добавлен в черный список).")
        except TokenError as e:
             # Если токен уже недействителен или в черном списке
             logger.warning(f"Ошибка при добавлении токена в черный список для пользователя {request.user.email}: {e}")
             # Можно вернуть успех, т.к. токен и так невалиден
             # return Response({"error": f"Неверный refresh-токен: {e}"}, status=status.HTTP_400_BAD_REQUEST)
             pass # Игнорируем ошибку, т.к. цель - разлогинить
        except (BlacklistedToken, OutstandingToken.DoesNotExist):
             # Токен уже в черном списке или не существует
             logger.info(f"Токен для пользователя {request.user.email} уже был в черном списке или не найден.")
             pass # Считаем выход успешным
        except Exception as e:
             logger.exception(f"Неожиданная ошибка при добавлении токена в черный список для пользователя {request.user.email}: {e}")
             # В этом случае лучше вернуть ошибку
             return Response({"error": "Произошла ошибка при выходе."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


        return Response({"message": "Вы успешно вышли"}, status=status.HTTP_200_OK)


class ApproveUserAPIView(APIView):
    permission_classes = [IsAdminUser] # Только админ

    def get_object(self, pk):
         # Работаем только с неудаленными пользователями
        return get_object_or_404(User, pk=pk, is_deleted=False)

    @swagger_auto_schema(
        # ... (схема как была) ...
        responses={
            200: UserDetailSerializer(), # Возвращаем пользователя
            400: "Пользователь уже одобрен или отклонен", # Объединяем ошибки 400
            404: "Пользователь не найден (или удален)"
        }
    )
    def post(self, request, pk):
        user = self.get_object(pk)
        if user.status == "approved":
            return Response({"detail": "Пользователь уже одобрен."}, status=status.HTTP_400_BAD_REQUEST)
        # Можно одобрить и после отклонения
        # if user.status == "rejected":
        #     return Response({"detail": "Нельзя одобрить отклоненного пользователя."}, status=status.HTTP_400_BAD_REQUEST)

        user.status = "approved"
        user.is_active = True # При одобрении делаем активным
        user.save(update_fields=['status', 'is_active'])
        logger.info(f"Администратор {request.user.email} одобрил пользователя {user.email}.")
        # Важно: Сигнал post_save создаст чаты и отправит уведомления
        return Response(UserDetailSerializer(user).data, status=status.HTTP_200_OK)


class RejectUserAPIView(APIView):
    permission_classes = [IsAdminUser] # Только админ

    def get_object(self, pk):
         # Работаем только с неудаленными пользователями
        return get_object_or_404(User, pk=pk, is_deleted=False)

    @swagger_auto_schema(
        # ... (схема как была) ...
        responses={
            200: UserDetailSerializer(), # Возвращаем пользователя
            400: "Пользователь уже отклонен или одобрен", # Объединяем ошибки 400
            404: "Пользователь не найден (или удален)"
        }
    )
    def post(self, request, pk):
        user = self.get_object(pk)
        if user.status == "rejected":
            return Response({"detail": "Пользователь уже отклонён."}, status=status.HTTP_400_BAD_REQUEST)
        if user.status == "approved":
             return Response({"detail": "Нельзя отклонить одобренного пользователя."}, status=status.HTTP_400_BAD_REQUEST)

        user.status = "rejected"
        user.is_active = False # При отклонении делаем неактивным
        user.save(update_fields=['status', 'is_active'])
        logger.info(f"Администратор {request.user.email} отклонил пользователя {user.email}.")
        # Сигнал post_save отправит уведомление
        return Response(UserDetailSerializer(user).data, status=status.HTTP_200_OK)


class CustomTokenRefreshView(TokenRefreshView):
    @swagger_auto_schema(
        operation_summary="Обновление Access токена",
        operation_description="Использует Refresh токен для получения нового Access токена.",
        responses={
             200: openapi.Response("Новый Access токен", schema=openapi.Schema(
                type=openapi.TYPE_OBJECT, properties={'access': openapi.Schema(type=openapi.TYPE_STRING)})),
             401: openapi.Response("Refresh токен недействителен или отсутствует")
        }
    )
    def post(self, request, *args, **kwargs):
        try:
            response = super().post(request, *args, **kwargs)
            # Дополнительно логируем успешное обновление
            if response.status_code == 200:
                 # Не можем получить user ID из refresh токена напрямую без валидации
                 logger.info(f"Access токен успешно обновлен (использован refresh токен).")
            return response
        except TokenError as e: # Используем конкретную ошибку
             logger.warning(f"Ошибка обновления токена: {e}")
             return Response({"detail": "Refresh-токен недействителен или срок его действия истек.", "code": "token_not_valid"},
                            status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
             logger.exception(f"Неожиданная ошибка при обновлении токена: {e}")
             return Response({"detail": "Произошла ошибка при обновлении токена."},
                             status=status.HTTP_500_INTERNAL_SERVER_ERROR)