from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from .models import Notification
from .serializers import NotificationSerializer
import logging

logger = logging.getLogger(__name__)


class NotificationViewSet(viewsets.ModelViewSet):
    """API для работы с уведомлениями"""
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['is_read', 'notification_type']
    ordering_fields = ['created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        """
        Возвращает уведомления текущего пользователя.
        Для Swagger возвращает пустой QuerySet.
        """
        if getattr(self, 'swagger_fake_view', False):
            return Notification.objects.none()

        return Notification.objects.filter(recipient=self.request.user).order_by('-created_at')

    def perform_update(self, serializer):
        """Обновление уведомления"""
        # Разрешаем менять только поле is_read
        serializer.save()

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Отметить уведомление как прочитанное"""
        notification = self.get_object()

        if notification.is_read:
            return Response({"message": "Уведомление уже отмечено как прочитанное"})

        try:
            notification.mark_as_read()
            serializer = self.get_serializer(notification)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Ошибка при отметке уведомления как прочитанного: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Отметить все уведомления как прочитанные"""
        try:
            updated = self.get_queryset().filter(is_read=False).update(is_read=True)
            return Response({"detail": f"{updated} уведомлений отмечено как прочитанные"})
        except Exception as e:
            logger.error(f"Ошибка при отметке всех уведомлений как прочитанных: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Получить количество непрочитанных уведомлений"""
        count = self.get_queryset().filter(is_read=False).count()
        return Response({"unread_count": count})

    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """Получить уведомления по типу"""
        notification_type = request.query_params.get('type')
        if not notification_type:
            return Response(
                {"error": "Необходимо указать параметр 'type'"},
                status=status.HTTP_400_BAD_REQUEST
            )

        notifications = self.get_queryset().filter(notification_type=notification_type)
        page = self.paginate_queryset(notifications)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(notifications, many=True)
        return Response(serializer.data)