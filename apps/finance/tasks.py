# apps/finance/tasks.py
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Sum, Count, Q
from datetime import timedelta, datetime
import json
import logging

from .services import PartnerStatisticsService, AdminStatisticsService
from apps.users.models import User
from .models import FinanceStatistics
from apps.orders.models import Order, OrderItem, DefectItem
from apps.stores.models import StoreDebt, StoreDebtPayment, StoreExpense

logger = logging.getLogger(__name__)


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
            logger.error(f"Ошибка при расчете статистики для партнера {partner.id}: {str(e)}")

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
            logger.error(f"Ошибка при расчете статистики для администратора {admin.id}: {str(e)}")

    # Сохраняем общую статистику в базу данных
    try:
        # Расчет общих показателей за день
        # ИСПРАВЛЕНО: Фильтрация заказов без элементов (пустых заказов)
        orders = Order.objects.filter(created_at__date=yesterday)
        valid_orders = []

        for order in orders:
            if order.order_items.count() > 0:
                valid_orders.append(order.id)

        # Продолжаем только с валидными заказами
        if valid_orders:
            orders = Order.objects.filter(id__in=valid_orders)
            # ИЗМЕНЕНО: Фильтруем только заказы от партнеров к магазинам
            store_orders = orders.filter(order_type='partner_to_store')
            order_items = OrderItem.objects.filter(order__in=store_orders)

            # Общее количество заказов
            total_orders = len(valid_orders)

            # Общая сумма продаж
            total_sales = order_items.aggregate(
                total=Sum('price', field='price * quantity')
            ).get('total', 0) or 0

            # Общая сумма расходов
            total_expenses = StoreExpense.objects.filter(
                expense_date=yesterday
            ).aggregate(total=Sum('amount')).get('total', 0) or 0

            # Количество бракованных товаров
            total_defects = DefectItem.objects.filter(
                order__in=store_orders
            ).aggregate(total=Sum('quantity')).get('total', 0) or 0

            # Количество бонусных товаров
            total_bonuses = order_items.aggregate(
                total=Sum('bonus_quantity')
            ).get('total', 0) or 0

            # Платежи по долгам
            total_debt_payments = StoreDebtPayment.objects.filter(
                payment_date__date=yesterday
            ).aggregate(total=Sum('amount')).get('total', 0) or 0

            # Долги за день
            daily_debt = StoreDebt.objects.filter(
                created_at__date=yesterday
            ).aggregate(total=Sum('amount')).get('total', 0) or 0

            # Оставшийся долг (долги - платежи)
            remaining_debt = daily_debt - total_debt_payments

            # Сформируем дополнительные данные в формате JSON
            additional_data = {
                'orders_by_type': {
                    'admin_to_partner': orders.filter(order_type='admin_to_partner').count(),
                    'partner_to_store': store_orders.count()
                },
                'financial': {
                    'total_debt': float(daily_debt),
                    'total_payments': float(total_debt_payments),
                    'remaining_debt': float(remaining_debt),
                    'total_expenses': float(total_expenses)
                },
                'products_summary': []
            }

            # Собираем данные по товарам
            product_stats = {}
            for item in order_items:
                product_id = item.product_id
                if product_id not in product_stats:
                    product_stats[product_id] = {
                        'id': product_id,
                        'name': item.product.name,
                        'quantity': 0,
                        'bonus_quantity': 0,
                        'total_price': 0
                    }
                product_stats[product_id]['quantity'] += item.quantity
                product_stats[product_id]['bonus_quantity'] += (item.bonus_quantity or 0)
                product_stats[product_id]['total_price'] += float(item.price * item.quantity)

            additional_data['products_summary'] = list(product_stats.values())

            # ИЗМЕНЕНО: Расчет общего баланса по новой формуле
            # Общий баланс = доходы + оставшийся долг - расходы - бонусы - брак
            avg_price = 0
            if order_items.count() > 0:
                avg_price = float(sum(item.price for item in order_items)) / order_items.count()

            bonuses_value = avg_price * total_bonuses
            defects_value = float(sum(
                defect.quantity * defect.product.price for defect in DefectItem.objects.filter(order__in=store_orders)))

            total_balance = float(total_sales) + float(remaining_debt) - float(
                total_expenses) - bonuses_value - defects_value

            # Сохраняем обновленную статистику в базу данных
            FinanceStatistics.objects.create(
                date=yesterday,
                total_orders=total_orders,
                total_sales=total_sales,
                total_expenses=total_expenses,
                total_defects=total_defects,
                total_bonuses=total_bonuses,
                data_json={
                    **additional_data,
                    'total_balance': total_balance,
                    'remaining_debt': float(remaining_debt),
                    'bonuses_value': float(bonuses_value),
                    'defects_value': float(defects_value)
                }
            )
            logger.info(f"Статистика за {yesterday} успешно сохранена")
        else:
            # Создаем пустую статистику
            FinanceStatistics.objects.create(
                date=yesterday,
                total_orders=0,
                total_sales=0,
                total_expenses=0,
                total_defects=0,
                total_bonuses=0,
                data_json={
                    'orders_by_type': {'admin_to_partner': 0, 'partner_to_store': 0},
                    'financial': {'total_debt': 0, 'total_payments': 0, 'remaining_debt': 0, 'total_expenses': 0},
                    'products_summary': [],
                    'total_balance': 0,
                    'bonuses_value': 0,
                    'defects_value': 0
                }
            )
            logger.info(f"Создана пустая статистика за {yesterday} (нет валидных заказов)")

    except Exception as e:
        logger.error(f"Ошибка при сохранении глобальной статистики: {str(e)}")


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

        # Фильтруем валидные заказы (имеющие элементы)
        valid_order_ids = []
        for order in orders:
            if order.order_items.count() > 0:
                valid_order_ids.append(order.id)

        # Продолжаем только с валидными заказами
        valid_orders = Order.objects.filter(id__in=valid_order_ids)

        # Группируем заказы по датам
        data_by_date = {}

        for order in valid_orders:
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
                'created_at': order.created_at.isoformat(),
                'items_count': order.order_items.count(),
                'total_price': float(order.total_price)
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

        logger.info(f"Архивация данных за период {month_ago} - {today} завершена успешно")

    except Exception as e:
        logger.error(f"Ошибка при архивации данных: {str(e)}")