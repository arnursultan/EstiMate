from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.orders.models import ProductRequest
from apps.finance.models import FinanceEntry
from apps.finance.services import update_calendar_statistics
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ProductRequest)
def update_calendar_on_request(sender, instance, created, **kwargs):
    """Обновляет календарную статистику при изменении запроса на товар"""
    date_obj = instance.created_at.date()

    try:
        # Обновляем для партнера
        if instance.user:
            update_calendar_statistics(
                date_obj,
                user=instance.user,
                has_requests=True
            )

        # Обновляем для магазина, если запрос для магазина
        if instance.request_type == 'STORE' and instance.store:
            update_calendar_statistics(
                date_obj,
                store=instance.store,
                has_requests=True
            )

            # Обновляем для города магазина
            if instance.store.city:
                update_calendar_statistics(
                    date_obj,
                    city=instance.store.city,
                    has_requests=True
                )

        # Если запрос получен, обновляем метки продаж
        if instance.status == 'received':
            if instance.user:
                update_calendar_statistics(
                    date_obj,
                    user=instance.user,
                    has_sales=True
                )

            if instance.request_type == 'STORE' and instance.store:
                update_calendar_statistics(
                    date_obj,
                    store=instance.store,
                    has_sales=True
                )

                if instance.store.city:
                    update_calendar_statistics(
                        date_obj,
                        city=instance.store.city,
                        has_sales=True
                    )
    except Exception as e:
        logger.error(f"Ошибка при обновлении календарной статистики: {str(e)}")


@receiver(post_save, sender=FinanceEntry)
def update_calendar_on_finance(sender, instance, created, **kwargs):
    """Обновляет календарную статистику при финансовой операции"""
    try:
        # Обновляем метки в зависимости от типа записи
        has_expenses = instance.entry_type == 'expense'
        has_sales = instance.entry_type == 'sale'
        has_damages = instance.entry_type == 'damage'
        has_returns = instance.entry_type == 'return'

        update_calendar_statistics(
            instance.date,
            user=instance.user,
            has_expenses=has_expenses,
            has_sales=has_sales,
            has_damages=has_damages,
            has_returns=has_returns
        )

        if instance.city:
            update_calendar_statistics(
                instance.date,
                city=instance.city,
                has_expenses=has_expenses,
                has_sales=has_sales,
                has_damages=has_damages,
                has_returns=has_returns
            )
    except Exception as e:
        logger.error(f"Ошибка при обновлении календарной статистики для финансовой записи: {str(e)}")