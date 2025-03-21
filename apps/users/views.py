import random
from django.core.mail import send_mail
from django.contrib.auth import authenticate, get_user_model
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import generics, permissions, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User
from .serializers import UserSerializer, LoginSerializer
from apps.users.tasks import send_reset_email
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.response import Response
from rest_framework import status

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["email", "first_name", "last_name", "password"],
            properties={
                "email": openapi.Schema(type=openapi.TYPE_STRING, format="email", description="Email", maxLength=50),
                "login": openapi.Schema(type=openapi.TYPE_STRING, description="Логин", maxLength=50, nullable=True),
                "phone": openapi.Schema(type=openapi.TYPE_STRING, description="Телефон", maxLength=15, nullable=True),
                "first_name": openapi.Schema(type=openapi.TYPE_STRING, description="Имя", maxLength=24, minLength=2),
                "last_name": openapi.Schema(type=openapi.TYPE_STRING, description="Фамилия", maxLength=24, minLength=2),
                "password": openapi.Schema(type=openapi.TYPE_STRING, description="Пароль", maxLength=128, minLength=1),
            },
        ),
        responses={201: openapi.Response("Пользователь создан", UserSerializer)}
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(role="partner")


class LoginView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=LoginSerializer,
        responses={200: openapi.Response("Tokens", schema=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "refresh": openapi.Schema(type=openapi.TYPE_STRING),
                "access": openapi.Schema(type=openapi.TYPE_STRING),
            },
        ))},
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        login_or_phone_or_email = serializer.validated_data["login_or_phone_or_email"]
        password = serializer.validated_data["password"]

        user = User.objects.filter(email=login_or_phone_or_email).first() or \
               User.objects.filter(phone=login_or_phone_or_email).first() or \
               User.objects.filter(login=login_or_phone_or_email).first()

        if user and user.check_password(password):
            refresh = RefreshToken.for_user(user)
            return Response({
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            }, status=200)

        return Response({"error": "Неверные учетные данные"}, status=400)


class ProfileView(generics.RetrieveUpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        """ Возвращает текущего аутентифицированного пользователя """
        user = self.request.user

        # Защита от AnonymousUser
        if not user.is_authenticated:
            return Response({"error": "Вы не авторизованы"}, status=status.HTTP_401_UNAUTHORIZED)

        return user

    def update(self, request, *args, **kwargs):
        """ Обновляет профиль пользователя, запрещая изменение роли """
        user = self.get_object()

        if isinstance(user, Response):
            return user

        data = request.data

        if "role" in data and not user.is_staff:
            return Response({"error": "Вы не можете изменить свою роль"}, status=status.HTTP_403_FORBIDDEN)


        if "password" in data:
            user.set_password(data.pop("password"))

        if "first_name" in data:
            user.first_name = data["first_name"]

        if "last_name" in data:
            user.last_name = data["last_name"]

        user.save()

        return Response({"message": "Профиль обновлён успешно!"}, status=status.HTTP_200_OK)


from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import random

class PasswordResetView(APIView):
    """
    Отправка кода подтверждения на email
    """
    permission_classes = [AllowAny]
    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['email_or_phone'],
            properties={
                'email_or_phone': openapi.Schema(type=openapi.TYPE_STRING, description='Email или телефон пользователя'),
            },
        ),
        responses={
            200: openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                'message': openapi.Schema(type=openapi.TYPE_STRING, description='Сообщение об отправке кода'),
            }),
            404: openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                'error': openapi.Schema(type=openapi.TYPE_STRING, description='Ошибка, если пользователь не найден'),
            }),
        }
    )
    def post(self, request):
        email_or_phone = request.data.get("email_or_phone")
        user = User.objects.filter(email=email_or_phone).first() or \
               User.objects.filter(phone=email_or_phone).first()

        if not user:
            return Response({"error": "Пользователь не найден"}, status=status.HTTP_404_NOT_FOUND)

        reset_token = str(random.randint(10000, 99999))
        user.token_reset = reset_token
        user.save()

        if user.email:
            send_reset_email.delay(user.email, reset_token)
            return Response({"message": "Код отправлен на email"}, status=status.HTTP_200_OK)

        return Response({"error": "Не удалось отправить код"}, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetVerifyView(APIView):
    """
    Верификация кода подтверждения перед сменой пароля.
    """
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['token'],
            properties={
                'token': openapi.Schema(type=openapi.TYPE_STRING, description='Код подтверждения'),
            },
        ),
        responses={
            200: openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                'message': openapi.Schema(type=openapi.TYPE_STRING, description='Код подтверждён'),
            }),
            400: openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                'error': openapi.Schema(type=openapi.TYPE_STRING, description='Неверный код подтверждения'),
            }),
        }
    )
    def post(self, request):
        reset_token = request.data.get("token")

        user = User.objects.filter(token_reset=reset_token).first()

        if not user:
            return Response({"error": "Неверный код подтверждения"}, status=status.HTTP_400_BAD_REQUEST)

        # Сохраняем факт подтверждения кода
        user.is_reset_verified = True
        user.save()

        return Response({"message": "Код подтверждён"}, status=status.HTTP_200_OK)

class PasswordResetConfirmView(APIView):
    """
    Установка нового пароля после успешного подтверждения кода.
    """
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['new_password', 'confirm_password'],
            properties={
                'new_password': openapi.Schema(type=openapi.TYPE_STRING, description='Новый пароль'),
                'confirm_password': openapi.Schema(type=openapi.TYPE_STRING, description='Подтверждение пароля'),
            },
        ),
        responses={
            200: openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                'message': openapi.Schema(type=openapi.TYPE_STRING, description='Пароль успешно изменён'),
            }),
            400: openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                'error': openapi.Schema(type=openapi.TYPE_STRING, description='Ошибка при смене пароля'),
            }),
        }
    )
    def post(self, request):
        new_password = request.data.get("new_password")
        confirm_password = request.data.get("confirm_password")

        if new_password != confirm_password:
            return Response({"error": "Пароли не совпадают"}, status=status.HTTP_400_BAD_REQUEST)

        # Получаем пользователя, который уже подтвердил код
        user = User.objects.filter(is_reset_verified=True).first()

        if not user:
            return Response({"error": "Ошибка при смене пароля"}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.token_reset = None  # Очистка кода
        user.is_reset_verified = False  # Сбрасываем флаг подтверждения
        user.save()

        return Response({"message": "Пароль успешно изменён"}, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            # Проверяем, что пользователь аутентифицирован
            if not request.user or not request.user.is_authenticated:
                return Response({"error": "Вы не авторизованы"}, status=status.HTTP_401_UNAUTHORIZED)

            # Опционально получаем refresh-токен
            refresh_token = request.data.get("refresh")

            if refresh_token:
                try:
                    token = RefreshToken(refresh_token)
                    token.blacklist()  # Добавляем в blacklist
                except Exception as e:
                    print(f"Ошибка при блокировке токена: {str(e)}")
                    return Response({"error": "Неверный refresh-токен"}, status=status.HTTP_400_BAD_REQUEST)

            return Response({"message": "Вы успешно вышли"}, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"❌ Ошибка при выходе: {str(e)}")
            return Response({"error": "Ошибка при выходе"}, status=status.HTTP_400_BAD_REQUEST)


class CustomTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        try:
            response = super().post(request, *args, **kwargs)
            return response
        except Exception as e:
            return Response({"error": "Refresh-токен недействителен, войдите заново."},
                            status=status.HTTP_401_UNAUTHORIZED)