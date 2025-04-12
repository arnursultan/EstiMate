# apps/chats/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Message  # Предполагаемая модель для сообщений
from apps.notifications.services import NotificationService

@receiver(post_save, sender=Message)
def message_notification(sender, instance, created, **kwargs):
    """Создает уведомления при получении нового сообщения"""
    if created:
        # Отправляем уведомление получателю сообщения
        NotificationService.create_notification(
            user_id=instance.receiver.id,
            notification_type='message',
            title='Новое сообщение',
            message=f'У вас новое сообщение от {instance.sender.first_name} {instance.sender.last_name}',
            extra_data={
                'sender_id': instance.sender.id,
                'sender_name': f'{instance.sender.first_name} {instance.sender.last_name}',
                'message_preview': instance.text[:50] + ('...' if len(instance.text) > 50 else '')
            }
        )
