from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from apps.orders.models import ProductRequest
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ProductRequest)
def log_cart_update(sender, instance, created, **kwargs):
    """Логирование изменений в корзине"""
    if not instance.for_store and instance.status in ['pending', 'approved']:
        if created:
            logger.info(f"Добавлен товар в корзину: {instance.product.name} (ID: {instance.id}) "
                        f"пользователем {instance.user.email}")
        else:
            logger.info(f"Обновлен товар в корзине: {instance.product.name} (ID: {instance.id}) "
                        f"пользователем {instance.user.email}, статус: {instance.status}")


@receiver(pre_delete, sender=ProductRequest)
def log_cart_delete(sender, instance, **kwargs):
    """Логирование удаления из корзины"""
    if not instance.for_store and instance.status == 'pending':
        logger.info(f"Удален товар из корзины: {instance.product.name} (ID: {instance.id}) "
                    f"пользователем {instance.user.email}")