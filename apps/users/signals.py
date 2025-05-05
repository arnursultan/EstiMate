# apps/users/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User  # Импортируем нашу модель User
from apps.notifications.services import NotificationService
from apps.chats.models import Chat # Импортируем Chat
import logging

logger = logging.getLogger(__name__) # Используем стандартный логгер Django

@receiver(post_save, sender=User)
@receiver(post_save, sender=User)
def user_status_notification(sender, instance: User, created: bool, **kwargs):
    logger.error(f"!!!!!!!!!!!!!!! СИГНАЛ post_save ДЛЯ USER {instance.pk} СРАБОТАЛ! created={created}, role={instance.role}, status={instance.status} !!!!!!!!!!!!!!")
    # --- УВЕДОМЛЕНИЕ АДМИНА О НОВОЙ РЕГИСТРАЦИИ ---
    if created and instance.role == 'partner':
        admins = User.objects.filter(role='admin', is_active=True, is_deleted=False)
        if admins.exists():
            logger.info(f"[Signal] Отправка уведомлений админам о регистрации партнера ID: {instance.id} ({instance.email})")
            for admin in admins:
                NotificationService.create_notification(
                    user_id=admin.id,
                    notification_type='registration',
                    title='Новый пользователь зарегистрирован',
                    message=f'Новый партнер {instance.first_name} {instance.last_name} ({instance.email}) зарегистрировался и ожидает подтверждения.',
                    extra_data={
                        'user_id': instance.id,
                        'user_name': f'{instance.first_name} {instance.last_name}',
                        'user_email': instance.email
                    }
                )
        else:
            logger.warning("[Signal] Нет активных администраторов для отправки уведомления о новой регистрации.")

    # --- ОБРАБОТКА ИЗМЕНЕНИЯ СТАТУСА СУЩЕСТВУЮЩЕГО ПАРТНЕРА ---
    # Используем tracker для проверки изменения статуса
    # Срабатывает только при ОБНОВЛЕНИИ (not created) существующего пользователя-партнера
    # и ТОЛЬКО если поле 'status' действительно изменилось
    if not created and instance.role == 'partner' and instance.tracker.has_changed('status'):
        # Логируем предыдущее и текущее значение статуса
        old_status = instance.tracker.previous('status')
        new_status = instance.status
        logger.info(f"[Signal] Статус пользователя {instance.pk} ({instance.email}) изменился с '{old_status}' на '{new_status}'")

        # --- ЛОГИКА ДЛЯ СТАТУСА 'approved' ---
        if new_status == 'approved':
            title = 'Ваша учетная запись одобрена'
            message = 'Администратор одобрил вашу учетную запись. Теперь вы можете полноценно использовать систему.'
            logger.info(f"[Signal] Пользователь {instance.id} ({instance.email}) одобрен. Запуск создания чатов...")

            # --- Создание чатов ---
            try:
                # Проверяем активность партнера перед созданием чатов
                if not instance.is_active:
                     logger.warning(f"[Signal] Партнер {instance.id} одобрен, но НЕ активен. Чаты не создаются.")
                # Проверяем, нужно ли создавать чаты (если их еще нет)
                elif not Chat.objects.filter(partner=instance).exists():
                    # Получаем активных, не удаленных админов
                    admins = User.objects.filter(role='admin', is_active=True, is_deleted=False)
                    if admins.exists():
                        created_chat_count = 0
                        logger.info(f"[Signal] Найдено {admins.count()} активных админов для создания чатов с партнером {instance.id}.")
                        # Создаем чат с каждым админом
                        for admin in admins:
                            try:
                                 chat, chat_created = Chat.objects.get_or_create(admin=admin, partner=instance)
                                 if chat_created:
                                     created_chat_count += 1
                                     logger.info(f"[Signal] УСПЕШНО СОЗДАН чат ID:{chat.id} между админом {admin.id} ({admin.email}) и партнером {instance.id} ({instance.email})")
                                     # Уведомляем админа о НОВОМ чате
                                     NotificationService.create_notification(
                                         user_id=admin.id, notification_type='message',
                                         title='Новый чат с партнером',
                                         message=f'Создан чат с партнером {instance.first_name} {instance.last_name}',
                                         extra_data={'chat_id': chat.id, 'partner_id': instance.id, 'partner_name': f'{instance.first_name} {instance.last_name}'}
                                     )
                                 else:
                                      logger.info(f"[Signal] Чат между админом {admin.id} и партнером {instance.id} уже существовал.")
                            except Exception as chat_err:
                                 logger.exception(f"[Signal] Ошибка при создании/получении чата между админом {admin.id} и партнером {instance.id}: {chat_err}")

                        # Отправляем уведомление партнеру, если были созданы НОВЫЕ чаты
                        if created_chat_count > 0:
                            logger.info(f"[Signal] Успешно создано {created_chat_count} НОВЫХ чатов для партнера {instance.id}")
                            NotificationService.create_notification(
                                user_id=instance.id, notification_type='system',
                                title='Чаты с администраторами созданы',
                                message=f'Для вас создано {created_chat_count} чатов для общения с администрацией.'
                            )
                    else:
                        logger.warning(f"[Signal] Нет активных админов для создания чатов для партнера {instance.id}")
                else:
                    logger.info(f"[Signal] Чаты для партнера {instance.id} уже существуют (проверено).")

            except Exception as e:
                logger.exception(f"[Signal] Общая ошибка в блоке создания чатов для партнера {instance.id}: {str(e)}")
            # --- КОНЕЦ СОЗДАНИЯ ЧАТОВ ---

            # Отправляем уведомление партнеру об одобрении
            logger.info(f"[Signal] Отправка уведомления партнеру {instance.id} о статусе '{instance.status}'")
            NotificationService.create_notification(
                 user_id=instance.id, notification_type='registration',
                 title=title, message=message, extra_data={'status': instance.status}
             )

        # --- ЛОГИКА ДЛЯ СТАТУСА 'rejected' ---
        elif new_status == 'rejected':
            title = 'Ваша учетная запись отклонена'
            message = 'К сожалению, администратор отклонил вашу регистрацию.'
            logger.info(f"[Signal] Пользователь {instance.id} ({instance.email}) отклонен.")
            # Деактивация пользователя обычно происходит во View, но можно добавить и здесь для надежности
            # if instance.is_active:
            #     instance.is_active = False
            #     instance.save(update_fields=['is_active']) # ОСТОРОЖНО: может вызвать рекурсию сигнала! Лучше делать во View.

            # Отправляем уведомление партнеру об отклонении
            logger.info(f"[Signal] Отправка уведомления партнеру {instance.id} о статусе '{instance.status}'")
            NotificationService.create_notification(
                user_id=instance.id, notification_type='registration',
                title=title, message=message, extra_data={'status': instance.status}
            )
        # --- КОНЕЦ ЛОГИКИ ДЛЯ REJECTED ---

    # Можно добавить логирование для других случаев обновления партнера, если нужно
    # elif not created and instance.role == 'partner':
    #      logger.debug(f"[Signal] Пользователь {instance.pk} обновлен, но статус ('{instance.status}') не изменился или не 'approved'/'rejected'.")