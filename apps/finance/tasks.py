# apps/finance/tasks.py
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Sum, Count, Q, F
from datetime import timedelta, datetime
import json
import logging
from decimal import Decimal # Добавим Decimal

from .services import PartnerStatisticsService, AdminStatisticsService
from apps.users.models import User
# Импортируем PartnerExpense вместо StoreExpense
from .models import FinanceStatistics, PartnerExpense
from apps.orders.models import Order, OrderItem, DefectItem
from apps.stores.models import StoreDebt, StoreDebtPayment # StoreExpense удален
from apps.products.models import Product # Импортируем Product для расчета стоимости брака/бонусов

logger = logging.getLogger(__name__)


@shared_task
def calculate_daily_finance_statistics():
    """
    Задача для ежедневного расчета и кэширования финансовой статистики за ВЧЕРАШНИЙ день.
    """
    yesterday = timezone.now().date() - timedelta(days=1)
    logger.info(f"Запуск расчета статистики за {yesterday}...")
    date_range = (yesterday, yesterday) # Определяем диапазон

    # --- Расчет и кэширование статистики для партнеров ---
    active_partners = User.objects.filter(role='partner', is_active=True, is_deleted=False, status='approved')
    logger.info(f"Найдено {active_partners.count()} активных партнеров для расчета статистики.")
    service_partner = PartnerStatisticsService()
    for partner in active_partners:
        try:
            statistics = service_partner.get_partner_statistics(
                partner_id=partner.id,
                date_range=date_range
            )
            if "error" not in statistics:
                 # Кэшируем результат на сутки
                 date_cache_key = f"{yesterday.isoformat()}_{yesterday.isoformat()}"
                 cache_key = f"partner_stats_{partner.id}_{date_cache_key}"
                 cache.set(cache_key, statistics, 60 * 60 * 24)
                 logger.debug(f"Статистика для партнера {partner.id} за {yesterday} рассчитана и закэширована.")
            else:
                 logger.warning(f"Ошибка при расчете статистики для партнера {partner.id}: {statistics['error']}")

        except Exception as e:
            logger.exception(f"Критическая ошибка при расчете статистики для партнера {partner.id}: {str(e)}")

    # --- Расчет и кэширование статистики для админов ---
    active_admins = User.objects.filter(role='admin', is_active=True)
    logger.info(f"Найдено {active_admins.count()} активных администраторов для расчета статистики.")
    service_admin = AdminStatisticsService()
    for admin in active_admins:
        try:
            statistics = service_admin.get_admin_statistics(
                admin_id=admin.id,
                date_range=date_range
            )
            if "error" not in statistics:
                 # Кэшируем результат на сутки
                 date_cache_key = f"{yesterday.isoformat()}_{yesterday.isoformat()}"
                 cache_key = f"admin_stats_{admin.id}_{date_cache_key}"
                 cache.set(cache_key, statistics, 60 * 60 * 24)
                 logger.debug(f"Статистика для администратора {admin.id} за {yesterday} рассчитана и закэширована.")
            else:
                  logger.warning(f"Ошибка при расчете статистики для администратора {admin.id}: {statistics['error']}")
        except Exception as e:
            logger.exception(f"Критическая ошибка при расчете статистики для администратора {admin.id}: {str(e)}")

    # --- Сохранение ОБЩЕЙ статистики в базу данных ---
    logger.info(f"Расчет общей статистики за {yesterday} для сохранения в БД...")
    try:
        # Заказы за вчерашний день
        orders_qs = Order.objects.filter(created_at__date=yesterday)

        # --- ВАЖНО: Фильтруем "пустые" заказы (без OrderItem) ---
        valid_order_ids = OrderItem.objects.filter(order__in=orders_qs).values_list('order_id', flat=True).distinct()
        valid_orders_qs = orders_qs.filter(id__in=valid_order_ids)
        total_orders = valid_orders_qs.count()
        logger.info(f"Найдено {total_orders} валидных заказов за {yesterday}.")

        # Заказы В МАГАЗИНЫ (для расчета продаж, брака, бонусов)
        store_orders_qs = valid_orders_qs.filter(order_type='partner_to_store')
        store_order_items = OrderItem.objects.filter(order__in=store_orders_qs).select_related('product')

        # Общая сумма продаж (созданный долг магазинов)
        total_sales = store_order_items.aggregate(
             total=Sum(F('price') * F('quantity'))
         )['total'] or Decimal('0.00')

        # Общая сумма расходов ВСЕХ ПАРТНЕРОВ за день
        total_expenses = PartnerExpense.objects.filter(
            expense_date=yesterday
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        # Количество и стоимость бракованных товаров
        defect_items = DefectItem.objects.filter(order__in=store_orders_qs).select_related('product')
        total_defects_count = defect_items.aggregate(total=Sum('quantity'))['total'] or 0
        total_defects_cost = sum(d.quantity * d.product.price for d in defect_items) or Decimal('0.00')

        # Количество бонусных товаров
        total_bonuses_count = store_order_items.aggregate(total=Sum('bonus_quantity'))['total'] or 0

        # Платежи по долгам за день
        total_debt_payments = StoreDebtPayment.objects.filter(
            payment_date__date=yesterday
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        # Долги, созданные за день
        daily_debt_created = StoreDebt.objects.filter(
            created_at__date=yesterday
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        # Проверка: daily_debt_created должно быть ~= total_sales

        # Сохраняем статистику в базу данных
        stats_obj, created = FinanceStatistics.objects.update_or_create(
            date=yesterday,
            defaults={
                'total_orders': total_orders,
                'total_sales': total_sales,
                'total_expenses': total_expenses,
                'total_defects': total_defects_count,
                'total_bonuses': total_bonuses_count,
                'data_json': { # Дополнительные данные
                    'daily_debt_created': float(daily_debt_created),
                    'daily_payments_received': float(total_debt_payments),
                    'daily_defect_cost': float(total_defects_cost),
                     # Можно добавить еще что-то при необходимости
                 }
            }
        )
        if created:
             logger.info(f"Создана запись статистики в БД за {yesterday}.")
        else:
             logger.info(f"Обновлена запись статистики в БД за {yesterday}.")

    except Exception as e:
        logger.exception(f"Ошибка при сохранении общей статистики за {yesterday}: {str(e)}")


@shared_task
def run_daily_finance_statistics():
    """Запускает расчет финансовой статистики за вчерашний день"""
    logger.info("Запуск задачи run_daily_finance_statistics...")
    calculate_daily_finance_statistics.delay() # Используем .delay() для асинхронного вызова

# Задача архивации остается без изменений, т.к. она работает с Order


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