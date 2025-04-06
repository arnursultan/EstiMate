from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Notification
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Notification)
def log_notification(sender, instance, created, **kwargs):
    """Логирование создания или обновления уведомления"""
    if created:
        logger.info(f"Создано новое уведомление для {instance.recipient.email}: {instance.title}")
    else:
        if instance.is_read:
            logger.info(f"Уведомление id={instance.id} отмечено как прочитанное")