from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import ProductRequest
from apps.notifications.services import notify


@receiver(post_save, sender=ProductRequest)
def notify_product_request_status_change(sender, instance, created, **kwargs):
    if created:
        # Уведомление администраторам о новом запросе
        from django.contrib.auth import get_user_model
        User = get_user_model()
        admin_users = User.objects.filter(is_staff=True)

        request_type = "для себя" if instance.request_type == 'SELF' else f"для магазина {instance.store.name}"

        for admin in admin_users:
            notify(
                user=admin,
                title="Новый запрос на товар",
                message=f"Пользователь {instance.user} запросил {instance.quantity} шт. {instance.product.name} ({request_type})"
            )
        return

    # Предыдущий статус должен быть установлен в __init__
    if hasattr(instance, 'previous_status') and instance.previous_status != instance.status:
        request_type = "для себя" if instance.request_type == 'SELF' else f"для магазина {instance.store.name if instance.store else 'не указан'}"

        if instance.status == 'approved':
            notify(
                user=instance.user,
                title="Запрос одобрен",
                message=f"Ваш запрос на {instance.product.name} ({instance.quantity} шт.) {request_type} одобрен."
            )

            # Если это запрос SELF, сообщаем, что товар добавлен в каталог
            if instance.request_type == 'SELF':
                notify(
                    user=instance.user,
                    title="Товар добавлен в ваш каталог",
                    message=f"Товар {instance.product.name} ({instance.quantity} шт.) добавлен в ваш личный каталог."
                )

        elif instance.status == 'rejected':
            notify(
                user=instance.user,
                title="Запрос отклонён",
                message=f"Ваш запрос на {instance.product.name} ({instance.quantity} шт.) {request_type} был отклонён."
            )

        elif instance.status == 'received':
            # Уведомление администраторам о получении товара
            from django.contrib.auth import get_user_model
            User = get_user_model()
            admin_users = User.objects.filter(is_staff=True)

            for admin in admin_users:
                notify(
                    user=admin,
                    title="Товар получен",
                    message=f"Пользователь {instance.user} получил {instance.quantity} шт. {instance.product.name} {request_type}"
                )