from django.http import HttpResponseForbidden
from rest_framework import generics, permissions, status, filters
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q, Max, OuterRef, Subquery
from django.shortcuts import get_object_or_404
from .models import Chat, Message
from .serializers import (
    ChatSerializer,
    ChatCreateSerializer,
    MessageSerializer,
    MessageCreateSerializer
)
from django.contrib.auth import get_user_model
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.pagination import PageNumberPagination
import os
from .utils import BetterFileResponse

User = get_user_model()


class MessagePagination(PageNumberPagination):
    """Пагинатор для сообщений с измененным порядком."""
    page_size = 30
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'links': {
                'next': self.get_next_link(),
                'previous': self.get_previous_link()
            },
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'results': data
        })


class ChatListView(generics.ListAPIView):
    """Представление для получения списка чатов текущего пользователя."""
    serializer_class = ChatSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['updated_at']
    ordering = ['-updated_at']

    @swagger_auto_schema(
        operation_summary="Получение списка чатов пользователя",
        operation_description="""
        Для администратора: все чаты с партнерами.
        Для партнера: только его чаты с администраторами.
        """
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user

        if user.role == 'admin':
            # Администраторы видят все свои чаты с партнерами
            return Chat.objects.filter(admin=user)
        else:
            # Партнеры видят только свои чаты с администраторами
            return Chat.objects.filter(partner=user)


class AdminChatListView(generics.ListAPIView):
    """Представление для администраторов для получения списка всех партнеров с чатами."""
    serializer_class = ChatSerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    ordering_fields = ['updated_at', 'partner__first_name', 'partner__last_name']
    ordering = ['-updated_at']
    search_fields = ['partner__first_name', 'partner__last_name', 'partner__email']

    @swagger_auto_schema(
        operation_summary="Получение списка всех чатов с партнерами для администратора",
        manual_parameters=[
            openapi.Parameter(
                'q',
                openapi.IN_QUERY,
                description="Поиск по имени, фамилии или email партнера",
                type=openapi.TYPE_STRING
            ),
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        admin = self.request.user

        # Получаем всех активных партнеров
        partners = User.objects.filter(role='partner', is_active=True)

        # Создаем или получаем чаты с каждым партнером
        chat_ids = []
        for partner in partners:
            chat, created = Chat.objects.get_or_create(
                admin=admin,
                partner=partner,
                defaults={'admin': admin, 'partner': partner}
            )
            chat_ids.append(chat.id)

        return Chat.objects.filter(id__in=chat_ids)


class ChatCreateView(generics.CreateAPIView):
    """Представление для создания нового чата."""
    serializer_class = ChatCreateSerializer
    permission_classes = [permissions.IsAdminUser]  # Только администраторы могут создавать чаты

    @swagger_auto_schema(
        operation_summary="Создание нового чата с партнером",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['partner_id'],
            properties={
                'partner_id': openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description="ID партнера для создания чата"
                ),
            }
        ),
        responses={
            201: ChatSerializer,
            400: "Ошибка валидации"
        }
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        chat = serializer.save()

        # Возвращаем полные данные чата
        return Response(
            ChatSerializer(chat, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )


class ChatDetailView(generics.RetrieveAPIView):
    """Представление для получения информации о конкретном чате."""
    serializer_class = ChatSerializer
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Получение данных конкретного чата",
        operation_description="Возвращает данные чата, включая последнее сообщение и количество непрочитанных сообщений"
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return Chat.objects.filter(admin=user)
        else:
            return Chat.objects.filter(partner=user)


class MessageListView(generics.ListAPIView):
    """Представление для получения списка сообщений в чате."""
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = MessagePagination

    @swagger_auto_schema(
        operation_summary="Получение истории сообщений чата",
        operation_description="Возвращает сообщения в обратном хронологическом порядке (новые сверху)",
        manual_parameters=[
            openapi.Parameter(
                'page_size',
                openapi.IN_QUERY,
                description="Количество сообщений на странице",
                type=openapi.TYPE_INTEGER
            ),
            openapi.Parameter(
                'page',
                openapi.IN_QUERY,
                description="Номер страницы",
                type=openapi.TYPE_INTEGER
            ),
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        chat_id = self.kwargs['chat_id']

        # Проверка доступа к чату
        chat = get_object_or_404(Chat, id=chat_id)
        if user.role == 'admin' and chat.admin != user:
            return Message.objects.none()
        elif user.role == 'partner' and chat.partner != user:
            return Message.objects.none()

        # Отмечаем сообщения как прочитанные (кроме своих)
        Message.objects.filter(chat=chat).exclude(sender=user).update(is_read=True)

        # Возвращаем сообщения от новых к старым
        return Message.objects.filter(chat=chat).order_by('-timestamp')


class MessageCreateView(generics.CreateAPIView):
    """Представление для создания нового сообщения."""
    serializer_class = MessageCreateSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(
        operation_summary="Отправка нового сообщения",
        request_body=MessageCreateSerializer,
        responses={
            201: MessageSerializer,
            400: "Ошибка валидации данных",
            403: "Нет доступа к чату",
            404: "Чат не найден"
        }
    )
    def post(self, request, *args, **kwargs):
        # Дополнительная проверка перед созданием сообщения
        chat_id = self.kwargs['chat_id']
        user = self.request.user

        try:
            chat = Chat.objects.get(id=chat_id)

            # Проверка доступа к чату
            if user.role == 'admin' and chat.admin != user:
                return Response(
                    {"error": "У вас нет доступа к этому чату"},
                    status=status.HTTP_403_FORBIDDEN
                )
            elif user.role == 'partner' and chat.partner != user:
                return Response(
                    {"error": "У вас нет доступа к этому чату"},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Дополнительная проверка для партнеров
            if user.role == 'partner' and chat.admin.role != 'admin':
                return Response(
                    {"error": "Партнеры могут общаться только с администраторами"},
                    status=status.HTTP_403_FORBIDDEN
                )
        except Chat.DoesNotExist:
            return Response(
                {"error": "Чат не найден"},
                status=status.HTTP_404_NOT_FOUND
            )

        return super().post(request, *args, **kwargs)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['chat_id'] = self.kwargs['chat_id']
        return context


class UnreadMessagesCountView(APIView):
    """Представление для получения количества непрочитанных сообщений."""
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Получение количества непрочитанных сообщений",
        operation_description="Возвращает общее количество непрочитанных сообщений и разбивку по чатам",
        responses={
            200: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'total_unread': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'chats': openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'chat_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'unread_count': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'last_message_timestamp': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    format='date-time'
                                ),
                            }
                        )
                    )
                }
            )
        }
    )
    def get(self, request, format=None):
        user = request.user

        # Получаем все чаты пользователя
        if user.role == 'admin':
            chats = Chat.objects.filter(admin=user)
        else:
            chats = Chat.objects.filter(partner=user)

        # Получаем непрочитанные сообщения по чатам
        result = {
            'total_unread': 0,
            'chats': []
        }

        for chat in chats:
            # Получаем количество непрочитанных сообщений
            unread_messages = Message.objects.filter(
                chat=chat,
                is_read=False
            ).exclude(sender=user)

            unread_count = unread_messages.count()

            if unread_count > 0:
                # Получаем время последнего непрочитанного сообщения
                latest_message = unread_messages.order_by('-timestamp').first()

                result['chats'].append({
                    'chat_id': chat.id,
                    'unread_count': unread_count,
                    'last_message_timestamp': latest_message.timestamp.isoformat() if latest_message else None
                })
                result['total_unread'] += unread_count

        return Response(result)


class MarkMessagesAsReadView(APIView):
    """Представление для отметки сообщений в чате как прочитанных."""
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Отметка сообщений как прочитанных",
        operation_description="Отмечает все сообщения в чате как прочитанные",
        responses={
            200: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'status': openapi.Schema(type=openapi.TYPE_STRING),
                    'marked_count': openapi.Schema(type=openapi.TYPE_INTEGER)
                }
            ),
            403: "Нет доступа к чату",
            404: "Чат не найден"
        }
    )
    def post(self, request, chat_id, format=None):
        user = request.user

        # Проверка доступа к чату
        chat = get_object_or_404(Chat, id=chat_id)
        if user.role == 'admin' and chat.admin != user:
            return Response(
                {'error': 'У вас нет доступа к этому чату'},
                status=status.HTTP_403_FORBIDDEN
            )
        elif user.role == 'partner' and chat.partner != user:
            return Response(
                {'error': 'У вас нет доступа к этому чату'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Отмечаем все сообщения от других пользователей как прочитанные
        marked_count = Message.objects.filter(
            chat=chat
        ).exclude(
            sender=user
        ).exclude(
            is_read=True
        ).update(
            is_read=True
        )

        return Response({
            'status': 'Сообщения отмечены как прочитанные',
            'marked_count': marked_count
        })


class FileAccessView(APIView):
    """Представление для прямого доступа к файлам чата."""
    permission_classes = [IsAuthenticated]

    def get(self, request, message_id, *args, **kwargs):
        # Получаем сообщение
        message = get_object_or_404(Message, id=message_id)

        # Проверяем доступ пользователя к чату
        user = request.user
        if user.role == 'admin' and message.chat.admin != user:
            return HttpResponseForbidden("У вас нет доступа к этому файлу")
        elif user.role == 'partner' and message.chat.partner != user:
            return HttpResponseForbidden("У вас нет доступа к этому файлу")

        # Дополнительная проверка: партнер может общаться только с админом
        if user.role == 'partner' and message.chat.admin.role != 'admin':
            return HttpResponseForbidden("Партнеры могут общаться только с администраторами")

        # Проверяем наличие файла
        if not message.file:
            return Response({"error": "Файл не найден"}, status=404)

        # Получаем путь к файлу
        file_path = message.file.path
        filename = os.path.basename(file_path)

        # Отдаем файл с улучшенными заголовками
        return BetterFileResponse(
            open(file_path, 'rb'),
            filename=filename
        )