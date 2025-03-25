import re

from django.core.cache import cache
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User
from .serializers import UserSerializer, LoginSerializer, UserDetailSerializer, UserUpdateSerializer
from apps.users.tasks import send_reset_email
from rest_framework_simplejwt.views import TokenRefreshView
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import random


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(request_body=openapi.Schema(type=openapi.TYPE_OBJECT,
        required=["email", "phone", "first_name", "last_name", "password"], properties={
        "email": openapi.Schema(type=openapi.TYPE_STRING, format="email", description="Email (max 50 символов)", maxLength=50),
        "phone": openapi.Schema(type=openapi.TYPE_STRING, description="Телефон (+996XXXXXXXXX)", pattern=r"^\+996\d{9}$"),
        "first_name": openapi.Schema(type=openapi.TYPE_STRING, description="Имя (2-24 символа)", minLength=2, maxLength=24),
        "last_name": openapi.Schema(type=openapi.TYPE_STRING, description="Фамилия (2-24 символа)", minLength=2, maxLength=24),
        "password": openapi.Schema(type=openapi.TYPE_STRING, description="Пароль (6-128 символов)", minLength=6, maxLength=128),
    }), responses={
        201: openapi.Response("Пользователь создан", UserSerializer),
        400: openapi.Response("Ошибка валидации", schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={
            "detail": openapi.Schema(type=openapi.TYPE_STRING),
            "errors": openapi.Schema(type=openapi.TYPE_OBJECT),
        })),
    })
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(role="partner", status="pending")



class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        request_body=LoginSerializer,
        responses={
            200: openapi.Response("Tokens", schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "refresh": openapi.Schema(type=openapi.TYPE_STRING),
                    "access": openapi.Schema(type=openapi.TYPE_STRING),
                },
            )),
            400: "Ошибка авторизации"
        },
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)

        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }, status=status.HTTP_200_OK)


class PartnerProfileAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(responses={
        200: openapi.Response("Данные пользователя", UserDetailSerializer),
        401: openapi.Response("Не авторизован"),
    })
    def get(self, request):
        serializer = UserDetailSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(request_body=UserUpdateSerializer,
                         responses={200: UserDetailSerializer,
                                    400: 'Ошибка валидации данных'})
    def patch(self, request):
        serializer = UserUpdateSerializer(instance=request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserDetailSerializer(request.user).data, status=200)

    @swagger_auto_schema(
        request_body=UserUpdateSerializer,
        responses={200: UserDetailSerializer()}
    )
    def put(self, request):
        serializer = UserUpdateSerializer(instance=request.user, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserDetailSerializer(request.user).data, status=200)


class AdminUserAPIView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter('email', openapi.IN_QUERY, type=openapi.TYPE_STRING, description="Поиск по email"),
            openapi.Parameter('first_name', openapi.IN_QUERY, type=openapi.TYPE_STRING, description="Поиск по имени"),
            openapi.Parameter('last_name', openapi.IN_QUERY, type=openapi.TYPE_STRING, description="Поиск по фамилии"),
        ],
        responses={200: UserDetailSerializer(many=True)}
    )
    def get(self, request):
        email = request.query_params.get('email')
        first_name = request.query_params.get('first_name')
        last_name = request.query_params.get('last_name')

        users = User.objects.all()
        if email:
            users = users.filter(email__icontains=email)
        if first_name:
            users = users.filter(first_name__icontains=first_name)
        if last_name:
            users = users.filter(last_name__icontains=last_name)

        serializer = UserDetailSerializer(users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminUserDetailAPIView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get_object(self, pk):
        return get_object_or_404(User, pk=pk)

    @swagger_auto_schema(
        responses={
            200: UserDetailSerializer(),
            404: 'Пользователь не найден'
        }
    )
    def get(self, request, pk):
        user = self.get_object(pk)
        serializer = UserDetailSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        request_body=UserUpdateSerializer,
        responses={
            200: UserDetailSerializer(),
            400: 'Ошибка валидации данных',
            404: 'Пользователь не найден'
        }
    )
    def put(self, request, pk):
        user = self.get_object(pk)
        serializer = UserUpdateSerializer(instance=user, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserDetailSerializer(user).data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        request_body=UserUpdateSerializer,
        responses={
            200: UserDetailSerializer(),
            400: 'Ошибка валидации данных',
            404: 'Пользователь не найден'
        }
    )
    def patch(self, request, pk):
        user = self.get_object(pk)
        serializer = UserUpdateSerializer(instance=user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserDetailSerializer(user).data, status=status.HTTP_200_OK)

class UserDeleteAPIView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get_object(self, pk):
        return get_object_or_404(User, pk=pk)

    @swagger_auto_schema(
        responses={
            204: 'Пользователь успешно удалён',
            403: 'Нет прав на удаление этого пользователя',
            404: 'Пользователь не найден'
        }
    )
    def delete(self, request, pk):
        user = self.get_object(pk)

        if not request.user.is_staff :
            return Response(
                {"detail": "Нет прав на удаление этого пользователя"},
                status=status.HTTP_403_FORBIDDEN
            )

        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)




class DeactivateOwnAccountAPIView(APIView):
    """
    Деактивация собственного аккаунта (установка is_active=False).
    """
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Пользователь деактивирует свой аккаунт. После этого он не сможет войти.",
        responses={
            200: openapi.Response(description="Аккаунт успешно деактивирован"),
            403: openapi.Response(description="Уже деактивирован"),
        }
    )
    def post(self, request):
        user = request.user

        if not user.is_active:
            return Response({"detail": "Аккаунт уже деактивирован."}, status=status.HTTP_403_FORBIDDEN)

        user.is_active = False
        user.save()

        return Response({"detail": "Ваш аккаунт успешно деактивирован."}, status=status.HTTP_200_OK)




class UserBlockAPIView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @swagger_auto_schema(
        operation_description="Блокировка пользователя (is_active=False)",
        responses={
            200: openapi.Response("Пользователь успешно заблокирован", UserDetailSerializer),
            400: "Пользователь уже заблокирован",
            404: "Пользователь не найден"
        }
    )
    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)

        if not user.is_active:
            return Response({"detail": "Пользователь уже заблокирован."}, status=400)

        user.is_active = False
        user.save()
        return Response({"detail":"Пользователь успешно заблокирован"}, status=200)


class UserUnblockAPIView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @swagger_auto_schema(
        operation_description="Разблокировка пользователя (is_active=True)",
        responses={
            200: openapi.Response("Пользователь успешно разблокирован", UserDetailSerializer),
            400: "Пользователь уже активен",
            404: "Пользователь не найден"
        }
    )
    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)

        if user.is_active:
            return Response({"detail": "Пользователь уже активен."}, status=400)

        user.is_active = True
        user.save()
        return Response({"detail":"Пользователь успешно разблокирован"}, status=200)


class PasswordResetView(APIView):
    """
    Отправка кода подтверждения на email
    """
    permission_classes = [AllowAny]
    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['email'],
            properties={
                'email': openapi.Schema(type=openapi.TYPE_STRING, description='Email'),
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
        email = request.data.get("email")
        user = User.objects.filter(email=email).first()

        if not user:
            return Response({"error": "Пользователь не найден"}, status=status.HTTP_404_NOT_FOUND)

        reset_token = str(random.randint(10000, 99999))
        user.token_reset = reset_token
        user.save()
        cache.set(f"reset_token_valid:{reset_token}", True, timeout=120)
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

        if not cache.get(f"reset_token_valid:{reset_token}"):
            return Response({"error": "Срок действия токена истёк."}, status=400)

        if not user:
            return Response({"error": "Неверный токен."}, status=400)

        user.save()

        return Response({"message": "Код подтверждён"}, status=status.HTTP_200_OK)




class PasswordResetConfirmView(APIView):
    """
    Установка нового пароля по коду подтверждения (token_reset).
    """
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['token', 'new_password', 'confirm_password'],
            properties={
                'token': openapi.Schema(type=openapi.TYPE_STRING, description='Код подтверждения (token_reset)'),
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
        token = request.data.get("token")
        new_password = request.data.get("new_password")
        confirm_password = request.data.get("confirm_password")

        if not token:
            return Response({"error": "Токен подтверждения обязателен."}, status=status.HTTP_400_BAD_REQUEST)

        if new_password != confirm_password:
            return Response({"error": "Пароли не совпадают."}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(token_reset=token).first()

        if not cache.get(f"reset_token_valid:{token}"):
            return Response({"error": "Срок действия токена истёк."}, status=400)

        if not user:
            return Response({"error": "Неверный токен."}, status=400)

        if user.check_password(new_password):
            return Response({"error": "Новый пароль не должен совпадать с текущим."}, status=status.HTTP_400_BAD_REQUEST)
        if len(new_password) < 8:
            return Response({"error": "Пароль должен быть не менее 8 символов."}, status=status.HTTP_400_BAD_REQUEST)
        if not re.search(r"[a-zA-Z]", new_password) or not re.search(r"\d", new_password):
            return Response({"error": "Пароль должен содержать буквы и цифры."}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.token_reset = None
        user.save()

        return Response({"message": "Пароль успешно изменён"}, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            if not request.user or not request.user.is_authenticated:
                return Response({"error": "Вы не авторизованы"}, status=status.HTTP_401_UNAUTHORIZED)

            refresh_token = request.data.get("refresh")

            if refresh_token:
                try:
                    token = RefreshToken(refresh_token)
                    token.blacklist()
                except Exception as e:
                    print(f"Ошибка при блокировке токена: {str(e)}")
                    return Response({"error": "Неверный refresh-токен"}, status=status.HTTP_400_BAD_REQUEST)

            return Response({"message": "Вы успешно вышли"}, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"❌ Ошибка при выходе: {str(e)}")
            return Response({"error": "Ошибка при выходе"}, status=status.HTTP_400_BAD_REQUEST)

class ApproveUserAPIView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @swagger_auto_schema(
        operation_description="Одобрить заявку партнёра",
        responses={
            200: UserDetailSerializer(),
            400: "Пользователь уже одобрен",
            404: "Пользователь не найден"
        }
    )
    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        if user.status == "approved":
            return Response({"detail": "Пользователь уже одобрен."}, status=status.HTTP_400_BAD_REQUEST)

        user.status = "approved"
        user.save()
        return Response(UserDetailSerializer(user).data, status=status.HTTP_200_OK)


class RejectUserAPIView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @swagger_auto_schema(
        operation_description="Отклонить заявку партнёра",
        responses={
            200: UserDetailSerializer(),
            400: "Пользователь уже отклонён",
            404: "Пользователь не найден"
        }
    )
    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        if user.status == "rejected":
            return Response({"detail": "Пользователь уже отклонён."}, status=status.HTTP_400_BAD_REQUEST)

        user.status = "rejected"
        user.save()
        return Response(UserDetailSerializer(user).data, status=status.HTTP_200_OK)

class CustomTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        try:
            response = super().post(request, *args, **kwargs)
            return response
        except Exception as e:
            return Response({"error": "Refresh-токен недействителен, войдите заново."},
                            status=status.HTTP_401_UNAUTHORIZED)


