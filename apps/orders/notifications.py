from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import ProductRequest
from apps.notifications.services import notify


@receiver(post_save, sender=ProductRequest)
def product_request_notify(sender, instance, created, **kwargs):
    if created:
        notify(
            user=instance.user,
            title="Запрос отправлен",
            message=f"Ваш запрос на {instance.product.name} отправлен на рассмотрение."
        )
    else:
        if instance.status == 'approved':
            notify(
                user=instance.user,
                title="Запрос одобрен",
                message=f"Ваш запрос на {instance.product.name} был одобрен."
            )
        elif instance.status == 'rejected':
            notify(
                user=instance.user,
                title="Запрос отклонён",
                message=f"Ваш запрос на {instance.product.name} был отклонён."
            )
        elif instance.status == 'received':
            notify(
                user=instance.user,
                title="Запрос получен",
                message=f"Вы отметили получение товара: {instance.product.name}"
            )
