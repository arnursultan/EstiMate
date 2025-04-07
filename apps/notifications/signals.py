from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Notification
from apps.finance.models import FinanceEntry
from apps.orders.models import ProductRequest
from apps.products.models import PartnerProduct
from .services import notify_finance_entry_created, notify_partner_product_update, notify_request_status_change
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Notification)
def log_notification(sender, instance, created, **kwargs):
    """Логирование создания или обновления уведомления"""
    if created:
        logger.info(f"Создано новое уведомление для {instance.recipient.email}: {instance.title}")
    else:
        if instance.is_read:
            logger.info(f"Уведомление id={instance.id} отмечено как прочитанное")


@receiver(post_save, sender=FinanceEntry)
def handle_finance_entry_notification(sender, instance, created, **kwargs):
    """Отправка уведомлений при создании финансовой записи"""
    if created:
        notify_finance_entry_created(instance.user, instance)


@receiver(post_save, sender=ProductRequest)
def handle_request_status_notification(sender, instance, created, **kwargs):
    """Отправка уведомлений при изменении статуса запроса"""
    if not created and hasattr(instance, 'previous_status') and instance.previous_status != instance.status:
        notify_request_status_change(instance)


@receiver(post_save, sender=PartnerProduct)
def handle_partner_product_update_notification(sender, instance, created, **kwargs):
    """Отправка уведомлений при значительных изменениях в товаре партнера"""
    if not created:
        # Проверяем, что это не первое сохранение
        try:
            original = sender.objects.get(pk=instance.pk)

            # Проверяем существенные изменения
            if instance.sold_quantity > original.sold_quantity:
                notify_partner_product_update(instance.partner, instance, 'sold')

            if instance.damaged_quantity > original.damaged_quantity:
                notify_partner_product_update(instance.partner, instance, 'damaged')

            if instance.returned_quantity > original.returned_quantity:
                notify_partner_product_update(instance.partner, instance, 'returned')

        except sender.DoesNotExist:
            pass  # Если объект еще не существует, не делаем ничего