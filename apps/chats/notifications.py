from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Message
from apps.notifications.services import notify
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Message)
def notify_on_admin_message(sender, instance, created, **kwargs):
    """Отправка уведомления при получении сообщения от администратора"""
    if not created:
        return

    try:
        # Уведомления только для сообщений от администратора обычным пользователям
        if instance.sender.is_staff and instance.receiver and not instance.receiver.is_staff:
            notify(
                user=instance.receiver,
                title="Новое сообщение",
                message=f"Вы получили новое сообщение от администратора: {instance.text[:50]}..." if instance.text else "Вы получили новый файл от администратора"
            )

        # Уведомления администраторам о сообщениях от обычных пользователей
        elif not instance.sender.is_staff and instance.receiver and instance.receiver.is_staff:
            notify(
                user=instance.receiver,
                title="Новое сообщение от партнера",
                message=f"Партнер {instance.sender.first_name} {instance.sender.last_name} отправил вам сообщение: {instance.text[:50]}..." if instance.text else f"Партнер {instance.sender.first_name} {instance.sender.last_name} отправил вам файл"
            )
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления о сообщении: {str(e)}")