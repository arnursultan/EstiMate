from .models import Notification
import logging

logger = logging.getLogger(__name__)


def notify(user, title, message):
    """
    Создает новое уведомление для пользователя

    :param user: Пользователь-получатель уведомления
    :param title: Заголовок уведомления
    :param message: Текст уведомления
    :return: Созданное уведомление или None в случае ошибки
    """
    try:
        # Если пользователь не указан, уведомление не создается
        if user is None:
            # Можно отправить всем администраторам
            from django.contrib.auth import get_user_model
            User = get_user_model()
            admin_users = User.objects.filter(is_staff=True)

            notifications = []
            for admin in admin_users:
                notification = Notification.objects.create(
                    recipient=admin,
                    title=title,
                    message=message
                )
                notifications.append(notification)

            return notifications
        else:
            notification = Notification.objects.create(
                recipient=user,
                title=title,
                message=message
            )
            return notification
    except Exception as e:
        logger.error(f"Ошибка при создании уведомления: {str(e)}")
        return None