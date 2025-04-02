from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Product
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Product)
def log_product_update(sender, instance, created, **kwargs):
    """Логирование изменений в продукте"""
    if created:
        logger.info(f"Создан новый продукт: {instance.name} (ID: {instance.id})")
    else:
        logger.info(f"Обновлен продукт: {instance.name} (ID: {instance.id})")

    # Логирование низкого запаса
    if instance.quantity < 10 and instance.quantity > 0:
        logger.warning(f"Низкий запас продукта: {instance.name} (ID: {instance.id}, Остаток: {instance.quantity})")
    elif instance.quantity == 0:
        logger.warning(f"Продукт закончился на складе: {instance.name} (ID: {instance.id})")