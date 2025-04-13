from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Message
from apps.notifications.services import notify
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Message)
def notify_on_message(sender, instance, created, **kwargs):
    """Отправка уведомления при получении сообщения"""
    if not created:
        return

    try:
        # Уведомления для админа о сообщениях от партнеров
        if instance.sender.role == 'partner' and instance.chat.admin:
            notify(
                user=instance.chat.admin,
                title="Новое сообщение от партнера",
                message=f"Партнер {instance.sender.first_name} {instance.sender.last_name} отправил вам сообщение: {instance.content[:50]}..." if instance.content else f"Партнер {instance.sender.first_name} {instance.sender.last_name} отправил вам файл"
            )

        # Уведомления для партнеров о сообщениях от админов
        elif instance.sender.role == 'admin' and instance.chat.partner:
            notify(
                user=instance.chat.partner,
                title="Новое сообщение",
                message=f"Вы получили новое сообщение от администратора: {instance.content[:50]}..." if instance.content else "Вы получили новый файл от администратора"
            )
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления о сообщении: {str(e)}")