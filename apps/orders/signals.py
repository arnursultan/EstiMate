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


@receiver(post_save, sender=ProductRequest)
def handle_product_request(sender, instance, created, **kwargs):
    """
    Обрабатывает создание и изменение запросов на товары
    """
    if created:
        # НОВАЯ ЛОГИКА: При создании SELF-запроса, товар уже уменьшен в каталоге админа в views.py
        # НОВАЯ ЛОГИКА: При создании STORE-запроса, товар уже уменьшен в каталоге партнера в views.py

        # Обновляем статистику для запросов SELF
        if instance.request_type == 'SELF':
            try:
                from apps.finance.services import update_partner_daily_stats
                update_partner_daily_stats(instance.user, instance.created_at.date())
            except Exception as e:
                logger.error(f"Ошибка при обновлении статистики партнера: {str(e)}")

        # Для запросов STORE - обновляем статистику магазина и партнера
        elif instance.request_type == 'STORE':
            try:
                from apps.finance.services import update_partner_daily_stats, update_store_daily_stats
                update_partner_daily_stats(instance.user, instance.created_at.date())
                if instance.store:
                    update_store_daily_stats(instance.store, instance.created_at.date())
            except Exception as e:
                logger.error(f"Ошибка при обновлении статистики: {str(e)}")
    else:
        # Изменение существующего запроса
        if hasattr(instance, 'previous_status') and instance.previous_status != instance.status:
            # Статус изменился

            # НОВАЯ ЛОГИКА: Если SELF-запрос одобрен админом, товар добавляется партнеру (это делается в views.py)
            # НОВАЯ ЛОГИКА: Если SELF-запрос отклонен админом, товар возвращается админу (это делается в views.py)

            # Обновляем статистику для всех случаев изменения статуса
            try:
                from apps.finance.services import update_partner_daily_stats
                update_partner_daily_stats(instance.user, instance.created_at.date())

                if instance.store:
                    from apps.finance.services import update_store_daily_stats
                    update_store_daily_stats(instance.store, instance.created_at.date())
            except Exception as e:
                logger.error(f"Ошибка при обновлении статистики после изменения статуса: {str(e)}")