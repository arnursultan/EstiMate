# apps/notifications/views.py
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification, NotificationSettings
from .serializers import NotificationSerializer, NotificationSettingsSerializer
from .services import NotificationService


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Представление для работы с уведомлениями пользователя
    """
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Возвращает уведомления текущего пользователя"""
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')

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

    @action(detail=True, methods=['delete'])
    def delete(self, request, pk=None):
        """Удаляет уведомление"""
        notification = self.get_object()
        notification.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def unread(self, request):
        """Возвращает непрочитанные уведомления"""
        unread_notifications = self.get_queryset().filter(is_read=False)
        serializer = self.get_serializer(unread_notifications, many=True)

        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def count_unread(self, request):
        """Возвращает количество непрочитанных уведомлений"""
        count = self.get_queryset().filter(is_read=False).count()

        return Response({"count": count})


class NotificationSettingsView(APIView):
    """
    Представление для работы с настройками уведомлений
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Получение настроек уведомлений пользователя"""
        settings, created = NotificationSettings.objects.get_or_create(user=request.user)
        serializer = NotificationSettingsSerializer(settings)

        return Response(serializer.data)

    def put(self, request):
        """Обновление настроек уведомлений пользователя"""
        settings, created = NotificationSettings.objects.get_or_create(user=request.user)
        serializer = NotificationSettingsSerializer(settings, data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)