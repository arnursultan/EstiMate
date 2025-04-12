# apps/finance/tasks.py
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Sum
from datetime import timedelta
import json

from .services import PartnerStatisticsService, AdminStatisticsService
from apps.users.models import User
from .models import FinanceStatistics
from apps.orders.models import Order, OrderItem, DefectItem
from apps.stores.models import StoreDebt, StoreDebtPayment, StoreExpense


@shared_task
def calculate_daily_finance_statistics():
    """
    Задача для ежедневного расчета и кэширования финансовой статистики
    """
    yesterday = timezone.now().date() - timedelta(days=1)

    # Рассчитываем статистику для каждого партнера
    for partner in User.objects.filter(role='partner', is_active=True):
        try:
            service = PartnerStatisticsService()
            statistics = service.get_partner_statistics(
                partner_id=partner.id,
                date=yesterday
            )

            # Кэшируем результат на сутки
            cache_key = f"partner_stats_{partner.id}_{yesterday}"
            cache.set(cache_key, statistics, 60 * 60 * 24)
        except Exception as e:
            print(f"Error calculating statistics for partner {partner.id}: {str(e)}")

    # Рассчитываем статистику для администраторов
    for admin in User.objects.filter(role='admin', is_active=True):
        try:
            service = AdminStatisticsService()
            statistics = service.get_admin_statistics(
                admin_id=admin.id,
                date=yesterday
            )

            # Кэшируем результат на сутки
            cache_key = f"admin_stats_{admin.id}_{yesterday}"
            cache.set(cache_key, statistics, 60 * 60 * 24)
        except Exception as e:
            print(f"Error calculating statistics for admin {admin.id}: {str(e)}")

    # Сохраняем общую статистику в базу данных
    try:
        # Расчет общих показателей за день
        orders = Order.objects.filter(created_at__date=yesterday)
        order_items = OrderItem.objects.filter(order__in=orders)

        # Общее количество заказов
        total_orders = orders.count()

        # Общая сумма продаж
        total_sales = order_items.aggregate(
            total=Sum('price', field='price * quantity')
        )['total'] or 0

        # Общая сумма расходов
        total_expenses = StoreExpense.objects.filter(
            expense_date=yesterday
        ).aggregate(total=Sum('amount'))['total'] or 0

        # Количество бракованных товаров
        total_defects = DefectItem.objects.filter(
            order__in=orders
        ).aggregate(total=Sum('quantity'))['total'] or 0

        # Количество бонусных товаров
        total_bonuses = order_items.aggregate(
            total=Sum('bonus_quantity')
        )['total'] or 0

        # Платежи по долгам
        total_debt_payments = StoreDebtPayment.objects.filter(
            payment_date__date=yesterday
        ).aggregate(total=Sum('amount'))['total'] or 0

        # Сформируем дополнительные данные в формате JSON
        additional_data = {
            'orders_by_type': {
                'admin_to_partner': orders.filter(order_type='admin_to_partner').count(),
                'partner_to_store': orders.filter(order_type='partner_to_store').count()
            },
            'financial': {
                'total_debt': float(
                    StoreDebt.objects.filter(created_at__date=yesterday).aggregate(total=Sum('amount'))['total'] or 0),
                'total_payments': float(total_debt_payments),
                'total_expenses': float(total_expenses)
            },
            'products_summary': []
        }

        # Сохраняем статистику в базу данных
        FinanceStatistics.objects.create(
            date=yesterday,
            total_orders=total_orders,
            total_sales=total_sales,
            total_expenses=total_expenses,
            total_defects=total_defects,
            total_bonuses=total_bonuses,
            data_json=additional_data
        )

    except Exception as e:
        print(f"Error saving global statistics: {str(e)}")


@shared_task
def run_daily_finance_statistics():
    """Запускает расчет финансовой статистики за вчерашний день"""
    calculate_daily_finance_statistics.delay()


@shared_task
def archive_daily_data():
    """Архивирует ежедневные данные за последний месяц в JSON формате"""
    today = timezone.now().date()
    month_ago = today - timedelta(days=30)

    try:
        # Получаем данные для архивации
        orders = Order.objects.filter(
            created_at__date__gte=month_ago,
            created_at__date__lt=today
        )

        # Группируем заказы по датам
        data_by_date = {}

        for order in orders:
            date_str = order.created_at.date().isoformat()

            if date_str not in data_by_date:
                data_by_date[date_str] = {
                    'orders_count': 0,
                    'orders': []
                }

            data_by_date[date_str]['orders_count'] += 1
            data_by_date[date_str]['orders'].append({
                'id': order.id,
                'order_type': order.order_type,
                'status': order.status,
                'partner_id': order.partner_id,
                'store_id': order.store_id if order.store else None,
                'created_at': order.created_at.isoformat()
            })

        # Сохраняем данные в модель FinanceStatistics
        for date_str, data in data_by_date.items():
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()

            # Проверяем, есть ли уже запись за эту дату
            stats, created = FinanceStatistics.objects.get_or_create(date=date_obj)

            # Обновляем поле data_json
            existing_data = stats.data_json or {}
            existing_data['archived_data'] = data

            stats.data_json = existing_data
            stats.save()

    except Exception as e:
        print(f"Error archiving daily data: {str(e)}")