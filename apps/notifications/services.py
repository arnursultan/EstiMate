# apps/notifications/services.py
from .models import Notification, NotificationSettings
from apps.users.models import User
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class NotificationService:
    """Сервис для работы с уведомлениями"""

    @staticmethod
    def create_notification(user_id, notification_type, title, message, extra_data=None):
        """
        Создает новое уведомление

        Параметры:
        - user_id: ID пользователя
        - notification_type: Тип уведомления
        - title: Заголовок уведомления
        - message: Текст уведомления
        - extra_data: Дополнительные данные (опционально)
        """
        try:
            user = User.objects.get(id=user_id)

            # Проверяем, активен ли пользователь
            if not user.is_active:
                logger.warning(f"Попытка отправить уведомление неактивному пользователю ID={user_id}")
                return None

            # Проверяем настройки уведомлений пользователя
            settings, created = NotificationSettings.objects.get_or_create(user=user)

            # Проверяем, включено ли уведомление данного типа
            if notification_type == 'order_status' and not settings.order_status_notifications:
                return None
            elif notification_type == 'store_approval' and not settings.store_approval_notifications:
                return None
            elif notification_type == 'registration' and not settings.registration_notifications:
                return None
            elif notification_type == 'message' and not settings.message_notifications:
                return None
            elif notification_type == 'financial' and not settings.financial_notifications:
                return None
            elif notification_type == 'system' and not settings.system_notifications:
                return None

            # Создаем новое уведомление
            notification = Notification.objects.create(
                user=user,
                notification_type=notification_type,
                title=title,
                message=message,
                extra_data=extra_data
            )

            # Здесь можно добавить код для отправки push-уведомлений
            # например, через Firebase или другой сервис

            logger.info(f"Успешно создано уведомление ID={notification.id} для пользователя ID={user_id}")
            return notification

        except User.DoesNotExist:
            logger.error(f"Пользователь с ID {user_id} не найден")
            return None
        except Exception as e:
            logger.error(f"Ошибка при создании уведомления: {str(e)}")
            return None

    @staticmethod
    def get_user_notifications(user_id, is_read=None, notification_type=None, limit=None):
        """
        Получает уведомления пользователя

        Параметры:
        - user_id: ID пользователя
        - is_read: Статус прочтения (опционально)
        - notification_type: Тип уведомления (опционально)
        - limit: Ограничение количества (опционально)
        """
        try:
            # Базовый запрос
            query = Notification.objects.filter(user_id=user_id)

            # Применяем фильтры
            if is_read is not None:
                query = query.filter(is_read=is_read)

            if notification_type:
                query = query.filter(notification_type=notification_type)

            # Сортируем по дате создания (новые сверху)
            query = query.order_by('-created_at')

            # Ограничиваем количество, если указано
            if limit:
                query = query[:limit]

            return query

        except Exception as e:
            logger.error(f"Ошибка при получении уведомлений: {str(e)}")
            return []

    @staticmethod
    def mark_as_read(notification_id):
        """Отмечает уведомление как прочитанное"""
        try:
            notification = Notification.objects.get(id=notification_id)
            notification.is_read = True
            notification.save(update_fields=['is_read'])
            logger.info(f"Уведомление ID={notification_id} отмечено как прочитанное")
            return True
        except Notification.DoesNotExist:
            logger.warning(f"Уведомление ID={notification_id} не найдено")
            return False
        except Exception as e:
            logger.error(f"Ошибка при отметке уведомления как прочитанного: {str(e)}")
            return False

    @staticmethod
    def mark_all_as_read(user_id):
        """Отмечает все уведомления пользователя как прочитанные"""
        try:
            count = Notification.objects.filter(user_id=user_id, is_read=False).update(is_read=True)
            logger.info(f"Отмечено {count} уведомлений как прочитанные для пользователя ID={user_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отметке всех уведомлений как прочитанных: {str(e)}")
            return False

    @staticmethod
    def delete_notification(notification_id):
        """Удаляет уведомление"""
        try:
            notification = Notification.objects.get(id=notification_id)
            notification.delete()
            logger.info(f"Уведомление ID={notification_id} удалено")
            return True
        except Notification.DoesNotExist:
            logger.warning(f"Уведомление ID={notification_id} не найдено")
            return False
        except Exception as e:
            logger.error(f"Ошибка при удалении уведомления: {str(e)}")
            return False