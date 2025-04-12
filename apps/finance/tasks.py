from celery import shared_task
from django.utils import timezone
from django.db.models import Sum, F, Q
from django.db import transaction
from datetime import datetime, timedelta
from decimal import Decimal

from apps.users.models import User
from apps.stores.models import Store
from apps.products.models import Product, PartnerInventory
from apps.orders.models import Order, OrderItem, DefectItem
from .models import (
    PartnerFinanceEntry,
    StoreFinanceEntry,
    DailyStatistics,
    ProductDailyStatistics
)


@shared_task
def run_daily_finance_statistics():
    """Задача для ежедневного сбора финансовой статистики"""
    yesterday = timezone.now().date() - timedelta(days=1)

    # Архивация финансовых данных по всем партнерам
    partners = User.objects.filter(role='partner')
    for partner in partners:
        archive_partner_statistics(partner, yesterday)

    # Архивация финансовых данных по всем магазинам
    stores = Store.objects.filter(status='approved')
    for store in stores:
        archive_store_statistics(store, yesterday)

    # Архивация общей статистики
    archive_admin_statistics(yesterday)

    return f"Финансовая статистика за {yesterday} успешно архивирована"


@shared_task
def archive_daily_data(date_str=None):
    """Архивация данных за указанную дату или за вчерашний день"""
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return f"Ошибка формата даты: {date_str}. Используйте YYYY-MM-DD"
    else:
        target_date = timezone.now().date() - timedelta(days=1)

    # Архивация финансовых данных по всем партнерам
    partners = User.objects.filter(role='partner')
    for partner in partners:
        archive_partner_statistics(partner, target_date)

    # Архивация финансовых данных по всем магазинам
    stores = Store.objects.filter(status='approved')
    for store in stores:
        archive_store_statistics(store, target_date)

    # Архивация общей статистики
    archive_admin_statistics(target_date)

    return f"Финансовая статистика за {target_date} успешно архивирована"


@transaction.atomic
def archive_partner_statistics(partner, target_date):
    """Архивация финансовой статистики партнера за указанную дату"""
    # Проверяем, существует ли уже статистика за эту дату
    existing_stats = DailyStatistics.objects.filter(
        partner=partner,
        date=target_date
    ).first()

    if existing_stats:
        # Если статистика уже существует, пропускаем
        return

    # Получаем запрошенные товары (заказы партнера у администратора)
    requested_items = OrderItem.objects.filter(
        order__partner=partner,
        order__order_type='admin_to_partner',
        order__created_at__date=target_date
    ).values('product_id', 'product__name').annotate(
        total_quantity=Sum('quantity'),
        total_amount=Sum(F('quantity') * F('price'))
    )

    # Получаем проданные товары (заказы магазинов у партнера)
    sold_items = OrderItem.objects.filter(
        order__created_by=partner,
        order__order_type='partner_to_store',
        order__created_at__date=target_date
    ).values('product_id', 'product__name').annotate(
        total_quantity=Sum('quantity'),
        total_amount=Sum(F('quantity') * F('price')),
        total_bonus=Sum('bonus_quantity')
    )

    # Получаем расходы
    expenses = StoreFinanceEntry.objects.filter(
        store__partner=partner,
        entry_type='expense',
        date=target_date
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # Получаем бракованные товары
    defect_items = DefectItem.objects.filter(
        order__created_by=partner,
        order__created_at__date=target_date
    ).values('product_id', 'product__name').annotate(
        total_quantity=Sum('quantity')
    )

    # Получаем остаток товаров
    inventory_items = PartnerInventory.objects.filter(
        partner=partner
    ).values('product_id', 'product__name', 'quantity')

    # Считаем итоговые показатели
    total_requested = sum((item['total_amount'] for item in requested_items), Decimal('0.00'))
    total_sold = sum((item['total_amount'] for item in sold_items), Decimal('0.00'))
    total_bonus_items = sum((item['total_bonus'] for item in sold_items), 0)
    total_defect_items = sum((item['total_quantity'] for item in defect_items), 0)
    total_remaining_items = sum((item['quantity'] for item in inventory_items), 0)

    # Рассчитываем общий баланс
    total_balance = total_sold - expenses

    # Создаем запись статистики
    statistics = DailyStatistics.objects.create(
        date=target_date,
        partner=partner,
        total_income=total_requested,
        total_expense=expenses,
        total_debt=Decimal('0.00'),  # У партнера нет долгов
        total_debt_paid=Decimal('0.00'),  # У партнера нет погашенных долгов
        total_bonus_amount=Decimal('0.00'),  # Стоимость бонусных товаров считается отдельно
        total_bonus_items=total_bonus_items,
        total_defect_items=total_defect_items,
        total_remaining_items=total_remaining_items,
        total_balance=total_balance
    )

    # Создаем записи статистики по товарам
    # Добавляем запрошенные товары
    for item in requested_items:
        ProductDailyStatistics.objects.create(
            statistics=statistics,
            product_id=item['product_id'],
            product_name=item['product__name'],
            requested_quantity=item['total_quantity'],
            income_amount=item['total_amount']
        )

    # Добавляем проданные товары
    for item in sold_items:
        # Проверяем, есть ли уже запись для этого товара
        product_stat = ProductDailyStatistics.objects.filter(
            statistics=statistics,
            product_id=item['product_id']
        ).first()

        if product_stat:
            # Обновляем существующую запись
            product_stat.sold_quantity = item['total_quantity']
            product_stat.bonus_quantity = item['total_bonus']
            product_stat.save()
        else:
            # Создаем новую запись
            ProductDailyStatistics.objects.create(
                statistics=statistics,
                product_id=item['product_id'],
                product_name=item['product__name'],
                sold_quantity=item['total_quantity'],
                bonus_quantity=item['total_bonus']
            )

    # Добавляем бракованные товары
    for item in defect_items:
        # Проверяем, есть ли уже запись для этого товара
        product_stat = ProductDailyStatistics.objects.filter(
            statistics=statistics,
            product_id=item['product_id']
        ).first()

        if product_stat:
            # Обновляем существующую запись
            product_stat.defect_quantity = item['total_quantity']
            product_stat.save()
        else:
            # Создаем новую запись
            ProductDailyStatistics.objects.create(
                statistics=statistics,
                product_id=item['product_id'],
                product_name=item['product__name'],
                defect_quantity=item['total_quantity']
            )

    # Добавляем остаток товаров
    for item in inventory_items:
        # Проверяем, есть ли уже запись для этого товара
        product_stat = ProductDailyStatistics.objects.filter(
            statistics=statistics,
            product_id=item['product_id']
        ).first()

        if product_stat:
            # Обновляем существующую запись
            product_stat.remaining_quantity = item['quantity']
            product_stat.save()
        else:
            # Создаем новую запись
            ProductDailyStatistics.objects.create(
                statistics=statistics,
                product_id=item['product_id'],
                product_name=item['product__name'],
                remaining_quantity=item['quantity']
            )


@transaction.atomic
def archive_store_statistics(store, target_date):
    """Архивация финансовой статистики магазина за указанную дату"""
    # Проверяем, существует ли уже статистика за эту дату
    existing_stats = DailyStatistics.objects.filter(
        store=store,
        date=target_date
    ).first()

    if existing_stats:
        # Если статистика уже существует, пропускаем
        return

    # Получаем заказы магазина
    orders = Order.objects.filter(
        store=store,
        created_at__date=target_date
    )

    # Получаем элементы заказов
    order_items = OrderItem.objects.filter(
        order__in=orders
    ).values('product_id', 'product__name').annotate(
        total_quantity=Sum('quantity'),
        total_amount=Sum(F('quantity') * F('price')),
        total_bonus=Sum('bonus_quantity')
    )

    # Получаем дефектные товары
    defect_items = DefectItem.objects.filter(
        order__in=orders
    ).values('product_id', 'product__name').annotate(
        total_quantity=Sum('quantity')
    )

    # Получаем сумму долга
    store_debts = store.debts.filter(
        created_at__date=target_date,
        is_paid=False
    )
    total_debt = store_debts.aggregate(sum=Sum('amount'))['sum'] or Decimal('0.00')

    # Получаем сумму погашенного долга
    total_paid = store.debt_payments.filter(
        payment_date=target_date
    ).aggregate(sum=Sum('amount'))['sum'] or Decimal('0.00')

    # Получаем расходы
    total_expenses = store.expenses.filter(
        expense_date=target_date
    ).aggregate(sum=Sum('amount'))['sum'] or Decimal('0.00')

    # Рассчитываем общую стоимость заказов
    total_orders_amount = sum((item['total_amount'] for item in order_items), Decimal('0.00'))
    total_bonus_items = sum((item['total_bonus'] for item in order_items), 0)
    total_defect_items = sum((item['total_quantity'] for item in defect_items), 0)

    # Создаем запись статистики
    statistics = DailyStatistics.objects.create(
        date=target_date,
        store=store,
        total_income=total_orders_amount,
        total_expense=total_expenses,
        total_debt=total_debt,
        total_debt_paid=total_paid,
        total_bonus_items=total_bonus_items,
        total_defect_items=total_defect_items,
        total_remaining_items=0,  # У магазина нет остатка товаров
        total_balance=total_orders_amount - total_expenses
    )

    # Создаем записи статистики по товарам
    for item in order_items:
        ProductDailyStatistics.objects.create(
            statistics=statistics,
            product_id=item['product_id'],
            product_name=item['product__name'],
            sold_quantity=item['total_quantity'],
            bonus_quantity=item['total_bonus'],
            income_amount=item['total_amount']
        )

    # Добавляем бракованные товары
    for item in defect_items:
        # Проверяем, есть ли уже запись для этого товара
        product_stat = ProductDailyStatistics.objects.filter(
            statistics=statistics,
            product_id=item['product_id']
        ).first()

        if product_stat:
            # Обновляем существующую запись
            product_stat.defect_quantity = item['total_quantity']
            product_stat.save()
        else:
            # Создаем новую запись
            ProductDailyStatistics.objects.create(
                statistics=statistics,
                product_id=item['product_id'],
                product_name=item['product__name'],
                defect_quantity=item['total_quantity']
            )


@transaction.atomic
def archive_admin_statistics(target_date):
    """Архивация общей финансовой статистики для администратора"""
    # Собираем статистику на основе уже архивированной статистики
    # партнеров и магазинов для избежания дублирования расчетов

    partner_stats = DailyStatistics.objects.filter(
        partner__isnull=False,
        date=target_date
    )

    store_stats = DailyStatistics.objects.filter(
        store__isnull=False,
        date=target_date
    )

    # Если нет никакой статистики за этот день, пропускаем
    if not partner_stats.exists() and not store_stats.exists():
        return

    # Агрегируем данные
    partner_summary = partner_stats.aggregate(
        total_income=Sum('total_income'),
        total_expense=Sum('total_expense'),
        total_bonus_items=Sum('total_bonus_items'),
        total_defect_items=Sum('total_defect_items'),
        total_remaining_items=Sum('total_remaining_items'),
        total_balance=Sum('total_balance')
    )

    store_summary = store_stats.aggregate(
        total_income=Sum('total_income'),
        total_expense=Sum('total_expense'),
        total_debt=Sum('total_debt'),
        total_debt_paid=Sum('total_debt_paid'),
        total_bonus_items=Sum('total_bonus_items'),
        total_defect_items=Sum('total_defect_items')
    )

    # Собираем общую статистику по товарам из статистики партнеров и магазинов
    product_stats = {}

    # Собираем данные о товарах из статистики партнеров
    partner_product_stats = ProductDailyStatistics.objects.filter(
        statistics__in=partner_stats
    )

    for ps in partner_product_stats:
        product_id = ps.product_id
        if product_id not in product_stats:
            product_stats[product_id] = {
                'product_id': product_id,
                'product_name': ps.product_name,
                'requested_quantity': 0,
                'sold_quantity': 0,
                'bonus_quantity': 0,
                'defect_quantity': 0,
                'remaining_quantity': 0,
                'income_amount': Decimal('0.00')
            }

        product_stats[product_id]['requested_quantity'] += ps.requested_quantity
        product_stats[product_id]['sold_quantity'] += ps.sold_quantity
        product_stats[product_id]['bonus_quantity'] += ps.bonus_quantity
        product_stats[product_id]['defect_quantity'] += ps.defect_quantity
        product_stats[product_id]['remaining_quantity'] += ps.remaining_quantity
        product_stats[product_id]['income_amount'] += ps.income_amount

    # Собираем данные о товарах из статистики магазинов
    store_product_stats = ProductDailyStatistics.objects.filter(
        statistics__in=store_stats
    )

    for ps in store_product_stats:
        product_id = ps.product_id
        if product_id not in product_stats:
            product_stats[product_id] = {
                'product_id': product_id,
                'product_name': ps.product_name,
                'requested_quantity': 0,
                'sold_quantity': 0,
                'bonus_quantity': 0,
                'defect_quantity': 0,
                'remaining_quantity': 0,
                'income_amount': Decimal('0.00')
            }

        # Не добавляем снова sold_quantity, так как это уже учтено в статистике партнеров
        product_stats[product_id]['bonus_quantity'] += ps.bonus_quantity
        product_stats[product_id]['defect_quantity'] += ps.defect_quantity
        product_stats[product_id]['income_amount'] += ps.income_amount

    # Создаем общую статистику
    # В общей статистике не указываем ни партнера, ни магазин
    admin_stats = DailyStatistics.objects.create(
        date=target_date,
        total_income=partner_summary['total_income'] or Decimal('0.00'),
        total_expense=partner_summary['total_expense'] or Decimal('0.00'),
        total_debt=store_summary['total_debt'] or Decimal('0.00'),
        total_debt_paid=store_summary['total_debt_paid'] or Decimal('0.00'),
        total_bonus_items=partner_summary['total_bonus_items'] or 0,
        total_defect_items=partner_summary['total_defect_items'] or 0,
        total_remaining_items=partner_summary['total_remaining_items'] or 0,
        total_balance=partner_summary['total_balance'] or Decimal('0.00')
    )

    # Создаем статистику по товарам
    for product_id, stat in product_stats.items():
        ProductDailyStatistics.objects.create(
            statistics=admin_stats,
            product_id=stat['product_id'],
            product_name=stat['product_name'],
            requested_quantity=stat['requested_quantity'],
            sold_quantity=stat['sold_quantity'],
            bonus_quantity=stat['bonus_quantity'],
            defect_quantity=stat['defect_quantity'],
            remaining_quantity=stat['remaining_quantity'],
            income_amount=stat['income_amount']
        )