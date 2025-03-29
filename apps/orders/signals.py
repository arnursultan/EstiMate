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

    if not instance.for_store:
        product = instance.product
        old_status = instance.previous_status
        new_status = instance.status

        if old_status != new_status:
            if old_status != 'approved' and new_status == 'approved':
                product.quantity -= instance.quantity
                product.save()
            elif old_status == 'approved' and new_status != 'approved':
                product.quantity += instance.quantity
                product.save()


@receiver(post_save, sender=ProductRequest)
def create_debt_for_store(sender, instance, created, **kwargs):
    """Создает запись о долге магазина, если выбран метод оплаты 'debt'"""
    # Проверяем, что это для магазина и метод оплаты - в долг
    if (created or instance.previous_status != 'approved') and \
            instance.status == 'approved' and \
            instance.for_store and \
            instance.store and \
            instance.payment_method == 'debt':
        # Создаем запись о долге
        from apps.stores.models import StoreDebt
        StoreDebt.objects.create(
            store=instance.store,
            amount=instance.total_price,
            request=instance
        )