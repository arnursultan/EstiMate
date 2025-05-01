# apps/users/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User  # Импортируем нашу модель User
from apps.notifications.services import NotificationService
# Импорты для создания чатов
from apps.chats.models import Chat
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def user_status_notification(sender, instance: User, created: bool, **kwargs):
    """
    Создает уведомления при регистрации, изменении статуса пользователя
    и СОЗДАЕТ ЧАТЫ при одобрении партнера.
    Использует запрос к БД для проверки изменения статуса.
    """

    # --- УВЕДОМЛЕНИЕ АДМИНА О НОВОЙ РЕГИСТРАЦИИ ---
    if created and instance.role == 'partner':
        admins = User.objects.filter(role='admin', is_active=True, is_deleted=False)
        if admins.exists():
            admin_ids = admins.values_list('id', flat=True)
            logger.info(f"Отправка уведомлений о новой регистрации партнера {instance.id} администраторам: {list(admin_ids)}")
            for admin_id in admin_ids:
                NotificationService.create_notification(
                    user_id=admin_id,
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
            logger.warning("Нет активных администраторов для отправки уведомления о новой регистрации.")

    # --- УВЕДОМЛЕНИЕ ПАРТНЕРА ОБ ИЗМЕНЕНИИ СТАТУСА + СОЗДАНИЕ ЧАТОВ ---
    # Срабатывает только при ОБНОВЛЕНИИ существующего пользователя-партнера
    if not created and instance.role == 'partner':
        status_changed = False
        old_status = None

        # Пытаемся получить предыдущее значение статуса
        # Используем .only('status') для небольшой оптимизации
        try:
            # Важно: используем _base_manager, если нужно отловить изменение статуса у удаленного пользователя
            # Но скорее всего, статус меняется только у неудаленных. Оставим objects.
            old_instance = User.objects.only('status').get(pk=instance.pk)
            old_status = old_instance.status
            if old_status != instance.status:
                status_changed = True
                logger.info(f"Статус пользователя {instance.pk} изменился с '{old_status}' на '{instance.status}'")
            else:
                 # Логируем, что статус не изменился, если нужно для отладки
                 # logger.debug(f"Статус пользователя {instance.pk} не изменился ('{instance.status}').")
                 pass

        except User.DoesNotExist:
            # Это странная ситуация для created=False, но обработаем ее
            logger.error(f"Не удалось найти пользователя {instance.pk} в базе данных при проверке изменения статуса (created=False).")
            # Если не можем проверить, не делаем ничего

        # Если статус действительно изменился на 'approved' или 'rejected'
        if status_changed and instance.status in ['approved', 'rejected']:
            notification_type = 'registration'
            title = None
            message = None

            if instance.status == 'approved':
                title = 'Ваша учетная запись одобрена'
                message = 'Администратор одобрил вашу учетную запись. Теперь вы можете полноценно использовать систему.'

                # --- ЛОГИКА СОЗДАНИЯ ЧАТОВ ---
                try:
                    # Проверяем, есть ли уже чаты с этим партнером
                    if not Chat.objects.filter(partner=instance).exists():
                        # Получаем всех активных, неудаленных администраторов
                        admins = User.objects.filter(role='admin', is_active=True, is_deleted=False)
                        if admins.exists():
                            created_chat_count = 0
                            logger.info(f"Создание чатов для одобренного партнера {instance.id} с {admins.count()} админами.")
                            for admin in admins:
                                chat, chat_created = Chat.objects.get_or_create(admin=admin, partner=instance)
                                if chat_created:
                                    created_chat_count += 1
                                    logger.info(f"Создан чат ({chat.id}) между админом {admin.id} и партнером {instance.id}")
                                    # Уведомляем админа о НОВОМ чате
                                    NotificationService.create_notification(
                                        user_id=admin.id,
                                        notification_type='message', # Тип "сообщение" для чата
                                        title='Новый чат с партнером',
                                        message=f'Создан новый чат с партнером {instance.first_name} {instance.last_name}',
                                        extra_data={
                                            'chat_id': chat.id,
                                            'partner_id': instance.id,
                                            'partner_name': f'{instance.first_name} {instance.last_name}'
                                        }
                                    )
                            if created_chat_count > 0:
                                # Уведомляем партнера о создании чатов
                                NotificationService.create_notification(
                                    user_id=instance.id,
                                    notification_type='system',
                                    title='Чаты с администраторами созданы',
                                    message=f'Для вас создано {created_chat_count} чатов для общения с администрацией.'
                                )
                        else:
                             logger.warning(f"Не найдено активных администраторов для создания чатов для партнера {instance.id}")
                    else:
                        logger.info(f"Чаты для партнера {instance.id} уже существуют, новые не создаются.")

                except Exception as e:
                    # Логируем ошибку, но не прерываем основной процесс сигнала
                    logger.exception(f"Ошибка при создании чатов для партнера {instance.id} после одобрения: {str(e)}")
                # --- КОНЕЦ ЛОГИКИ СОЗДАНИЯ ЧАТОВ ---

            elif instance.status == 'rejected':
                title = 'Ваша учетная запись отклонена'
                message = 'К сожалению, администратор отклонил вашу регистрацию.'
                # Дополнительно: можно деактивировать пользователя при отклонении, если это не сделано в View
                if instance.is_active:
                    instance.is_active = False
                    instance.save(update_fields=['is_active'])
                    logger.info(f"Пользователь {instance.id} деактивирован при отклонении регистрации.")


            # Отправляем уведомление партнеру об изменении статуса
            if title and message:
                logger.info(f"Отправка уведомления партнеру {instance.id} о статусе '{instance.status}'")
                NotificationService.create_notification(
                    user_id=instance.id,
                    notification_type=notification_type,
                    title=title,
                    message=message,
                    extra_data={
                        'status': instance.status
                    }
                )