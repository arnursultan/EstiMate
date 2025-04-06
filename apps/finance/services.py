from datetime import date
from django.db.models import Sum
from django.core.exceptions import ValidationError
from apps.orders.models import ProductRequest
from .models import PartnerFinanceStat, StoreFinanceStat, CalendarStatistics


def generate_partner_finance_stat(user):
    """Генерация финансовой статистики для партнера"""
    today = date.today()
    requests = ProductRequest.objects.filter(user=user, status='received', created_at__date=today)

    total_cash = requests.filter(payment_method='cash').aggregate(total=Sum('total_price'))['total'] or 0
    damaged_loss = sum([max(r.damaged_quantity * r.product.price, 0) for r in requests])
    profit = total_cash - damaged_loss

    return PartnerFinanceStat.objects.update_or_create(
        user=user,
        date=today,
        defaults={
            'total_approved_cash': total_cash,
            'total_damaged_loss': damaged_loss,
            'total_profit': profit
        }
    )[0]  # Возвращаем обновленный или созданный объект


def generate_store_finance_stat(store):
    """Генерация финансовой статистики для магазина"""
    today = date.today()
    requests = ProductRequest.objects.filter(store=store, status='received', created_at__date=today)

    total_approved = requests.aggregate(total=Sum('total_price'))['total'] or 0
    total_damaged = sum([max(r.damaged_quantity * r.product.price, 0) for r in requests])
    total_debt = requests.filter(payment_method='debt').aggregate(total=Sum('total_price'))['total'] or 0

    return StoreFinanceStat.objects.update_or_create(
        store=store,
        date=today,
        defaults={
            'total_approved': total_approved,
            'total_damaged': total_damaged,
            'total_debt': total_debt
        }
    )[0]  # Возвращаем обновленный или созданный объект


def update_calendar_statistics(date_obj, user=None, store=None, city=None, **kwargs):
    """
    Обновляет статистику календаря для указанной даты

    :param date_obj: Дата для обновления статистики
    :param user: Объект пользователя (если статистика привязана к пользователю)
    :param store: Объект магазина (если статистика привязана к магазину)
    :param city: Объект города (если статистика привязана к городу)
    :param kwargs: Дополнительные флаги статистики для обновления
    """
    # Валидация: должен быть указан хотя бы один из параметров user, store, city
    if not any([user, store, city]):
        raise ValidationError("Должен быть указан хотя бы один параметр: user, store или city")

    # Создаем или получаем существующую запись
    stats, created = CalendarStatistics.objects.get_or_create(
        date=date_obj,
        user=user,
        store=store,
        city=city,
        defaults=kwargs
    )

    if not created:
        # Обновляем только те поля, которые переданы и имеют значение True
        updated = False
        for key, value in kwargs.items():
            if value and hasattr(stats, key):
                setattr(stats, key, value)
                updated = True

        if updated:
            stats.save()

    return stats