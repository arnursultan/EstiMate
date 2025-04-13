# apps/notifications/views.py
from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Notification, NotificationSettings
from .serializers import NotificationSerializer, NotificationSettingsSerializer
from .services import NotificationService
import logging

logger = logging.getLogger(__name__)


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Представление для работы с уведомлениями пользователя
    """
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['is_read', 'notification_type']
    ordering_fields = ['created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        """Возвращает уведомления текущего пользователя"""
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')

    @swagger_auto_schema(
        operation_summary="Отметить уведомление как прочитанное",
        responses={
            200: openapi.Response("Уведомление отмечено как прочитанное"),
            400: "Уведомление уже прочитано",
            404: "Уведомление не найдено"
        }
    )
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Отмечает уведомление как прочитанное"""
        notification = self.get_object()

        if notification.is_read:
            return Response(
                {"detail": "Уведомление уже отмечено как прочитанное"},
                status=status.HTTP_400_BAD_REQUEST
            )

        notification.is_read = True
        notification.save()

        return Response(
            {"detail": "Уведомление отмечено как прочитанное"},
            status=status.HTTP_200_OK
        )

    @swagger_auto_schema(
        operation_summary="Отметить все уведомления как прочитанные",
        responses={
            200: openapi.Response("Все уведомления отмечены как прочитанные"),
            500: "Ошибка при отметке уведомлений"
        }
    )
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Отмечает все уведомления пользователя как прочитанные"""
        result = NotificationService.mark_all_as_read(request.user.id)

        if result:
            return Response(
                {"detail": "Все уведомления отмечены как прочитанные"},
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {"detail": "Не удалось отметить все уведомления как прочитанные"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        operation_summary="Удалить уведомление",
        responses={
            204: "Уведомление удалено",
            404: "Уведомление не найдено"
        }
    )
    @action(detail=True, methods=['delete'])
    def delete(self, request, pk=None):
        """Удаляет уведомление"""
        notification = self.get_object()
        notification.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)

    @swagger_auto_schema(
        operation_summary="Получить непрочитанные уведомления",
        responses={
            200: NotificationSerializer(many=True)
        }
    )
    @action(detail=False, methods=['get'])
    def unread(self, request):
        """Возвращает непрочитанные уведомления"""
        unread_notifications = self.get_queryset().filter(is_read=False)
        serializer = self.get_serializer(unread_notifications, many=True)

        return Response(serializer.data)

    @swagger_auto_schema(
        operation_summary="Получить количество непрочитанных уведомлений",
        responses={
            200: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'count': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'by_type': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'order_status': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'store_approval': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'registration': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'message': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'financial': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'system': openapi.Schema(type=openapi.TYPE_INTEGER),
                        }
                    )
                }
            )
        }
    )
    @action(detail=False, methods=['get'])
    def count_unread(self, request):
        """Возвращает количество непрочитанных уведомлений"""
        # Общее количество
        count = self.get_queryset().filter(is_read=False).count()

        # По типам
        by_type = {}
        for notification_type, _ in Notification.NOTIFICATION_TYPES:
            by_type[notification_type] = self.get_queryset().filter(
                is_read=False,
                notification_type=notification_type
            ).count()

        return Response({
            "count": count,
            "by_type": by_type
        })


class NotificationSettingsView(APIView):
    """
    Представление для работы с настройками уведомлений
    """
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Получить настройки уведомлений",
        responses={
            200: NotificationSettingsSerializer()
        }
    )
    def get(self, request):
        """Получение настроек уведомлений пользователя"""
        settings, created = NotificationSettings.objects.get_or_create(user=request.user)
        serializer = NotificationSettingsSerializer(settings)

        return Response(serializer.data)

    @swagger_auto_schema(
        operation_summary="Обновить настройки уведомлений",
        request_body=NotificationSettingsSerializer,
        responses={
            200: NotificationSettingsSerializer(),
            400: "Ошибка валидации"
        }
    )
    def put(self, request):
        """Обновление настроек уведомлений пользователя"""
        settings, created = NotificationSettings.objects.get_or_create(user=request.user)
        serializer = NotificationSettingsSerializer(settings, data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class FirebaseTokenView(APIView):
    """
    Представление для сохранения Firebase токена пользователя для push-уведомлений
    """
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Сохранить Firebase токен для push-уведомлений",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['token'],
            properties={
                'token': openapi.Schema(type=openapi.TYPE_STRING, description="Firebase токен")
            }
        ),
        responses={
            200: openapi.Response("Токен сохранен"),
            400: "Токен не предоставлен"
        }
    )
    def post(self, request):
        """Сохранить Firebase токен пользователя"""
        token = request.data.get('token')

        if not token:
            return Response(
                {"error": "Токен не предоставлен"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Здесь должна быть логика сохранения токена
        # Например, в профиле пользователя или отдельной модели

        # Для примера просто логируем
        logger.info(f"Firebase токен сохранен для пользователя {request.user.id}")

        return Response({"detail": "Токен успешно сохранен"})