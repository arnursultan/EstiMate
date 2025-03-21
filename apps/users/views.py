import random
from django.core.mail import send_mail
from django.contrib.auth import authenticate
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
        return self.request.user

    def update(self, request, *args, **kwargs):
        user = self.get_object()
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


class PasswordResetView(APIView):
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

class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email_or_phone = request.data.get("email_or_phone")
        reset_token = request.data.get("token")
        new_password = request.data.get("new_password")

        user = User.objects.filter(email=email_or_phone).first() or \
               User.objects.filter(phone=email_or_phone).first()

        if not user or user.token_reset != reset_token:
            return Response({"error": "Неверный код подтверждения"}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.token_reset = None
        user.save()

        return Response({"message": "Пароль успешно изменён"}, status=status.HTTP_200_OK)

class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response({"error": "Refresh-токен обязателен"}, status=status.HTTP_400_BAD_REQUEST)

            token = RefreshToken(refresh_token)
            token.blacklist()
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