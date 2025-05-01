from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Message # Убрали Chat
from django.contrib.auth import get_user_model
from apps.notifications.services import NotificationService # Используем сервис
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

@receiver(post_save, sender=Message)
def message_notification(sender, instance, created, **kwargs):
    """Создает уведомления при получении НОВОГО сообщения"""
    if created: # Только для новых сообщений
        try:
            chat = instance.chat
            sender_user = instance.sender

            # Определяем получателя (не отправителя)
            receiver = None
            if chat.admin == sender_user:
                receiver = chat.partner
            elif chat.partner == sender_user: # Добавляем elif для ясности
                receiver = chat.admin
            else:
                 # Ситуация не должна возникать, если модель Chat настроена правильно
                 logger.error(f"Не удалось определить получателя для сообщения {instance.id} в чате {chat.id}. Отправитель {sender_user.id} не является участником?")
                 return

            # Если получатель найден
            if receiver:
                # Формируем предварительный текст сообщения
                if instance.content:
                    message_preview = instance.content[:50] + ('...' if len(instance.content) > 50 else '')
                else:
                    # Используем file_type для описания
                    file_type_display = instance.get_message_type_display() # 'Изображение', 'Видео' и т.д.
                    message_preview = f"Новый файл ({file_type_display})"

                # Создаем уведомление через сервис
                notification = NotificationService.create_notification(
                    user_id=receiver.id,
                    notification_type='message',
                    title=f'Новое сообщение от {sender_user.first_name}', # Укоротим заголовок
                    message=message_preview, # Используем превью как сообщение
                    extra_data={
                        'chat_id': chat.id,
                        'sender_id': sender_user.id,
                        'sender_name': f'{sender_user.first_name} {sender_user.last_name}',
                        # 'message_preview': message_preview, # Уже в message
                        'message_type': instance.message_type
                    }
                )
                if notification:
                    logger.info(f"Уведомление о сообщении {instance.id} отправлено пользователю {receiver.id}")
                else:
                    logger.warning(f"Не удалось создать уведомление о сообщении {instance.id} для пользователя {receiver.id} (возможно, отключены в настройках)")

        except Exception as e:
            # Логируем ошибку, но не прерываем работу основного процесса сохранения сообщения
            logger.exception(f"Ошибка при создании уведомления о сообщении {instance.id}: {str(e)}")