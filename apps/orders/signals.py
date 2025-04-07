from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .models import ProductRequest
from apps.products.models import PartnerProduct
import logging

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=ProductRequest)
def product_request_pre_save(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = ProductRequest.objects.get(pk=instance.pk)
            instance.previous_status = old.status
        except ProductRequest.DoesNotExist:
            instance.previous_status = None


# Модифицируем обработчик изменения статуса запроса в apps/orders/signals.py

@receiver(post_save, sender=ProductRequest)
def handle_status_change(sender, instance, created, update_fields, **kwargs):
    """
    Обрабатывает изменения в запросах:
    - Создание запроса STORE -> добавление в корзину
    - Подтверждение запроса STORE -> удаление из корзины, создание долга
    - Подтверждение/получение запроса -> обновление статистики
    """
    if created:
        # Новый запрос создан
        if instance.request_type == 'STORE':
            # Добавляем запрос в корзину
            from apps.cart.models import CartItem
            try:
                CartItem.objects.create(
                    user=instance.user,
                    cart_type='STORE',
                    partner_product=instance.partner_product,
                    store=instance.store,
                    quantity=instance.quantity,
                    product_request=instance
                )
                logger.info(f"Добавлен элемент корзины для запроса #{instance.id}")
            except Exception as e:
                logger.error(f"Ошибка при добавлении запроса в корзину: {str(e)}")

        # Обновляем статистику для запросов SELF
        if instance.request_type == 'SELF':
            try:
                from apps.finance.services import update_partner_daily_stats
                update_partner_daily_stats(instance.user, instance.created_at.date())
            except Exception as e:
                logger.error(f"Ошибка при обновлении статистики партнера: {str(e)}")
    else:
        # Изменение существующего запроса
        if hasattr(instance, 'previous_status') and instance.previous_status != instance.status:
            # Статус изменился

            # Запрос STORE подтвержден партнером
            if instance.request_type == 'STORE' and instance.previous_status == 'pending' and instance.status == 'approved':
                try:
                    # Удаляем из корзины
                    from apps.cart.models import CartItem
                    CartItem.objects.filter(product_request=instance).delete()
                    logger.info(f"Удален элемент корзины для запроса #{instance.id}")

                    # Создаем долг магазина
                    from apps.stores.models import StoreDebt
                    StoreDebt.objects.create(
                        store=instance.store,
                        amount=instance.total_price,
                        request=instance,
                        created_by=instance.user
                    )
                    logger.info(f"Создан долг магазина {instance.store.name} на сумму {instance.total_price}")

                    # Уменьшаем количество товара в каталоге партнера
                    if instance.partner_product:
                        instance.partner_product.update_quantity(instance.quantity, operation='subtract')

                    # Обновляем статистику партнера и магазина
                    from apps.finance.services import update_partner_daily_stats, update_store_daily_stats
                    update_partner_daily_stats(instance.user, instance.created_at.date())
                    update_store_daily_stats(instance.store, instance.created_at.date())
                except Exception as e:
                    logger.error(f"Ошибка при обработке подтверждения запроса #{instance.id}: {str(e)}")

            # Запрос SELF подтвержден админом
            elif instance.request_type == 'SELF' and instance.previous_status == 'pending' and instance.status == 'approved':
                try:
                    # Обновляем статистику партнера (долг админу)
                    from apps.finance.services import update_partner_daily_stats
                    update_partner_daily_stats(instance.user, instance.created_at.date())
                except Exception as e:
                    logger.error(f"Ошибка при обновлении статистики после подтверждения SELF-запроса: {str(e)}")

            # Запрос SELF получен партнером
            elif instance.request_type == 'SELF' and instance.previous_status == 'approved' and instance.status == 'received':
                try:
                    # Создаем или обновляем товар в каталоге партнера
                    from apps.products.models import PartnerProduct
                    partner_product, created = PartnerProduct.objects.get_or_create(
                        partner=instance.user,
                        product=instance.product,
                        defaults={
                            'price': instance.product.price,
                            'quantity': 0
                        }
                    )

                    # Увеличиваем количество товара
                    partner_product.quantity += instance.quantity
                    if instance.bonus_quantity > 0:
                        partner_product.bonus_quantity += instance.bonus_quantity
                    partner_product.save()

                    # Обновляем статистику партнера
                    from apps.finance.services import update_partner_daily_stats
                    update_partner_daily_stats(instance.user, instance.created_at.date())
                except Exception as e:
                    logger.error(f"Ошибка при добавлении товара в каталог партнера: {str(e)}")