# Обновляем apps/cart/signals.py

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from apps.orders.models import ProductRequest
from apps.cart.models import CartItem
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ProductRequest)
def handle_product_request_cart(sender, instance, created, update_fields, **kwargs):
    """
    Обрабатывает запросы на товары:
    - При создании запроса STORE добавляет его в корзину
    - При подтверждении запроса STORE удаляет его из корзины и добавляет в долг магазина
    """
    # Для новых запросов типа STORE в статусе pending
    if created and instance.request_type == 'STORE' and instance.status == 'pending':
        # Создаем элемент в корзине для нового запроса STORE
        try:
            CartItem.objects.create(
                user=instance.user,
                cart_type='STORE',
                partner_product=instance.partner_product,
                store=instance.store,
                quantity=instance.quantity,
                product_request=instance
            )
            logger.info(f"Создан элемент корзины для запроса #{instance.id}")
        except Exception as e:
            logger.error(f"Ошибка при создании элемента корзины: {str(e)}")

    # Обрабатываем изменение статуса
    elif not created:
        # Было изменение статуса
        if hasattr(instance, 'previous_status') and instance.previous_status != instance.status:
            # Запрос STORE подтвержден (партнером)
            if instance.request_type == 'STORE' and instance.previous_status == 'pending' and instance.status == 'approved':
                try:
                    # Удаляем элемент из корзины
                    CartItem.objects.filter(product_request=instance).delete()
                    logger.info(f"Удален элемент корзины для запроса #{instance.id}")

                    # Создаем долг магазина
                    from apps.stores.models import StoreDebt
                    debt = StoreDebt.objects.create(
                        store=instance.store,
                        amount=instance.total_price,
                        request=instance,
                        created_by=instance.user
                    )
                    logger.info(f"Создан долг магазина {instance.store.name} на сумму {instance.total_price}")

                    # Добавляем доход партнеру (не создаем запись, а только учитываем в статистике)
                    from apps.finance.services import update_partner_statistics
                    update_partner_statistics(
                        instance.user,
                        income_amount=instance.total_price,
                        date=timezone.now().date()
                    )

                    # Уменьшаем количество товара в каталоге партнера
                    if instance.partner_product:
                        instance.partner_product.update_quantity(instance.quantity, operation='subtract')
                except Exception as e:
                    logger.error(f"Ошибка при обработке подтверждения запроса #{instance.id}: {str(e)}")