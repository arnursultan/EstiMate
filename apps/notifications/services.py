from .models import Notification


def notify(user, title, message):
    Notification.objects.create(
        recipient=user,
        title=title,
        message=message
    )
