# apps/notifications/models.py
from django.db import models
from django.utils import timezone
from apps.users.models import User


class Notification(models.Model):
    """Модель уведомления"""

    NOTIFICATION_TYPES = [
        ('order_status', 'Статус заказа'),
        ('store_approval', 'Одобрение магазина'),
        ('registration', 'Регистрация'),
        ('message', 'Сообщение'),
        ('financial', 'Финансовое уведомление'),
        ('system', 'Системное уведомление'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name='Пользователь'
    )
    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPES,
        verbose_name='Тип уведомления'
    )
    title = models.CharField(
        max_length=255,
        verbose_name='Заголовок'
    )
    message = models.TextField(
        verbose_name='Сообщение'
    )
    is_read = models.BooleanField(
        default=False,
        verbose_name='Прочитано'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    extra_data = models.JSONField(
        null=True,
        blank=True,
        verbose_name='Дополнительные данные'
    )

    class Meta:
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_notification_type_display()}: {self.title}"


class NotificationSettings(models.Model):
    """Настройки уведомлений пользователя"""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='notification_settings',
        verbose_name='Пользователь'
    )
    order_status_notifications = models.BooleanField(
        default=True,
        verbose_name='Уведомления о статусе заказа'
    )
    store_approval_notifications = models.BooleanField(
        default=True,
        verbose_name='Уведомления об одобрении магазина'
    )
    registration_notifications = models.BooleanField(
        default=True,
        verbose_name='Уведомления о регистрации'
    )
    message_notifications = models.BooleanField(
        default=True,
        verbose_name='Уведомления о сообщениях'
    )
    financial_notifications = models.BooleanField(
        default=True,
        verbose_name='Финансовые уведомления'
    )
    system_notifications = models.BooleanField(
        default=True,
        verbose_name='Системные уведомления'
    )

    class Meta:
        verbose_name = 'Настройки уведомлений'
        verbose_name_plural = 'Настройки уведомлений'

    def __str__(self):
        return f"Настройки уведомлений - {self.user.email}"