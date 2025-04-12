# apps/notifications/services.py
from .models import Notification, NotificationSettings
from apps.users.models import User
from django.utils import timezone


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

            return notification

        except User.DoesNotExist:
            print(f"User with ID {user_id} not found")
            return None
        except Exception as e:
            print(f"Error creating notification: {str(e)}")
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
            print(f"Error getting notifications: {str(e)}")
            return []

    @staticmethod
    def mark_as_read(notification_id):
        """Отмечает уведомление как прочитанное"""
        try:
            notification = Notification.objects.get(id=notification_id)
            notification.is_read = True
            notification.save()
            return True
        except Notification.DoesNotExist:
            return False
        except Exception as e:
            print(f"Error marking notification as read: {str(e)}")
            return False

    @staticmethod
    def mark_all_as_read(user_id):
        """Отмечает все уведомления пользователя как прочитанные"""
        try:
            Notification.objects.filter(user_id=user_id, is_read=False).update(is_read=True)
            return True
        except Exception as e:
            print(f"Error marking all notifications as read: {str(e)}")
            return False

    @staticmethod
    def delete_notification(notification_id):
        """Удаляет уведомление"""
        try:
            notification = Notification.objects.get(id=notification_id)
            notification.delete()
            return True
        except Notification.DoesNotExist:
            return False
        except Exception as e:
            print(f"Error deleting notification: {str(e)}")
            return False