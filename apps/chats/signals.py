from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Message, Chat
from django.contrib.auth import get_user_model
from apps.notifications.services import NotificationService
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


@receiver(post_save, sender=Message)
def message_notification(sender, instance, created, **kwargs):
    """Создает уведомления при получении нового сообщения"""
    if created:
        try:
            # Определяем получателя (не отправителя)
            receiver = None
            if instance.chat.admin == instance.sender:
                receiver = instance.chat.partner
            else:
                receiver = instance.chat.admin

            # Формируем предварительный текст сообщения
            if instance.content:
                message_preview = instance.content[:50] + ('...' if len(instance.content) > 50 else '')
            else:
                message_preview = f"Новый файл ({instance.message_type})"

            # Создаем уведомление
            NotificationService.create_notification(
                user_id=receiver.id,
                notification_type='message',
                title='Новое сообщение',
                message=f'У вас новое сообщение от {instance.sender.first_name} {instance.sender.last_name}',
                extra_data={
                    'chat_id': instance.chat.id,
                    'sender_id': instance.sender.id,
                    'sender_name': f'{instance.sender.first_name} {instance.sender.last_name}',
                    'message_preview': message_preview,
                    'message_type': instance.message_type
                }
            )
        except Exception as e:
            logger.error(f"Ошибка при создании уведомления о сообщении: {str(e)}")


@receiver(post_save, sender=User)
def create_chat_on_partner_approval(sender, instance, **kwargs):
    """Создает чат с администраторами при одобрении партнера"""
    # Проверяем, что это партнер и его статус изменился на 'approved'
    if instance.role == 'partner' and instance.status == 'approved':
        try:
            # Проверяем, есть ли уже чаты с этим партнером
            existing_chats = Chat.objects.filter(partner=instance).exists()

            # Если чатов нет, создаем чаты с каждым активным администратором
            if not existing_chats:
                # Получаем всех активных администраторов
                admins = User.objects.filter(role='admin', is_active=True)

                # Создаем чат с каждым администратором
                for admin in admins:
                    Chat.objects.create(admin=admin, partner=instance)

                    # Отправляем уведомление администратору о новом чате
                    NotificationService.create_notification(
                        user_id=admin.id,
                        notification_type='message',
                        title='Новый чат с партнером',
                        message=f'Создан новый чат с партнером {instance.first_name} {instance.last_name}',
                        extra_data={
                            'partner_id': instance.id,
                            'partner_name': f'{instance.first_name} {instance.last_name}'
                        }
                    )

                # Отправляем уведомление партнеру о созданных чатах
                NotificationService.create_notification(
                    user_id=instance.id,
                    notification_type='system',
                    title='Для вас созданы чаты',
                    message='Ваша учетная запись одобрена. Для вас созданы чаты с администраторами системы.'
                )

                logger.info(f"Созданы чаты для партнера {instance.id} со всеми администраторами")

        except Exception as e:
            logger.error(f"Ошибка при создании чатов для партнера {instance.id}: {str(e)}")