from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .models import ProductRequest


@receiver(pre_save, sender=ProductRequest)
def product_request_pre_save(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = ProductRequest.objects.get(pk=instance.pk)
            instance.previous_status = old.status
        except ProductRequest.DoesNotExist:
            instance.previous_status = None


@receiver(post_save, sender=ProductRequest)
def handle_status_change(sender, instance, created, **kwargs):
    if created:
        return

    if instance.for_store:
        return  # Складской запас не меняется, если запрос для магазина

    product = instance.product
    old_status = instance.previous_status
    new_status = instance.status

    if old_status != new_status:
        if old_status != 'approved' and new_status == 'approved':
            # Уменьшаем количество товара на складе при одобрении запроса
            try:
                product.reduce_quantity(instance.quantity)
            except Exception as e:
                # Логирование ошибки
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Ошибка при уменьшении количества товара: {str(e)}")

        elif old_status == 'approved' and new_status != 'approved':
            # Возвращаем товар на склад, если запрос был одобрен, а потом отклонен
            try:
                product.add_quantity(instance.quantity)
            except Exception as e:
                # Логирование ошибки
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Ошибка при возврате товара на склад: {str(e)}")


@receiver(post_save, sender=ProductRequest)
def create_debt_for_store(sender, instance, created, **kwargs):
    if (created or instance.previous_status != 'approved') and \
            instance.status == 'approved' and \
            instance.for_store and \
            instance.store and \
            instance.payment_method == 'debt':
        from apps.stores.models import StoreDebt
        StoreDebt.objects.create(
            store=instance.store,
            amount=instance.total_price,
            request=instance,
            created_by=instance.user
        )