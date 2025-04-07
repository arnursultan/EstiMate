from datetime import date
from django.db.models import Sum
from django.core.exceptions import ValidationError
from apps.orders.models import ProductRequest
from apps.products.models import PartnerProduct
from .models import PartnerFinanceStat, StoreFinanceStat, CalendarStatistics, InventorySummary
from datetime import timezone


def generate_partner_finance_stat(user):
    """Генерация финансовой статистики для партнера"""
    today = date.today()

    # Статистика по запросам STORE
    store_requests = ProductRequest.objects.filter(
        user=user,
        status='received',
        request_type='STORE',
        created_at__date=today
    )

    # Общая сумма долга (отложенный доход)
    total_debt = store_requests.aggregate(total=Sum('total_price'))['total'] or 0

    # Расчет убытков от брака
    damaged_loss = sum([
        max((r.damaged_quantity * r.partner_product.price), 0)
        for r in store_requests if r.partner_product
    ])

    # Расчет стоимости бонусов
    bonus_value = sum([
        max((r.bonus_quantity * r.partner_product.price), 0)
        for r in store_requests if r.partner_product
    ])

    # Получаем ручные записи за сегодня
    from .models import FinanceEntry
    entries = FinanceEntry.objects.filter(user=user, date=today)

    # Ручные расходы
    expenses = entries.filter(entry_type='expense').aggregate(total=Sum('amount'))['total'] or 0

    # Ручные продажи
    sales = entries.filter(entry_type='sale').aggregate(total=Sum('amount'))['total'] or 0
    sales_quantity = entries.filter(entry_type='sale').aggregate(total=Sum('quantity'))['total'] or 0

    # Расчет прибыли
    profit = total_debt - damaged_loss - expenses + bonus_value

    return PartnerFinanceStat.objects.update_or_create(
        user=user,
        date=today,
        defaults={
            'total_approved_debt': total_debt,
            'total_damaged_loss': damaged_loss,
            'total_bonus_value': bonus_value,
            'total_profit': profit,
            'total_expenses': expenses,
            'total_sold': sales,
            'total_sold_quantity': sales_quantity
        }
    )[0]  # Возвращаем обновленный или созданный объект


def generate_store_finance_stat(store):
    """Генерация финансовой статистики для магазина"""
    today = date.today()
    requests = ProductRequest.objects.filter(
        store=store,
        status='received',
        request_type='STORE',
        created_at__date=today
    )

    total_approved = requests.aggregate(total=Sum('total_price'))['total'] or 0
    total_damaged = sum([max(r.damaged_quantity * r.partner_product.price, 0) for r in requests if r.partner_product])
    total_debt = requests.aggregate(total=Sum('total_price'))['total'] or 0
    total_bonus = sum([max(r.bonus_quantity * r.partner_product.price, 0) for r in requests if r.partner_product])

    # Погашенный долг
    from apps.stores.models import StoreDebt
    paid_debt = StoreDebt.objects.filter(
        store=store,
        is_paid=True,
        paid_at__date=today
    ).aggregate(total=Sum('amount'))['total'] or 0

    return StoreFinanceStat.objects.update_or_create(
        store=store,
        date=today,
        defaults={
            'total_approved': total_approved,
            'total_damaged': total_damaged,
            'total_debt': total_debt,
            'total_bonus': total_bonus,
            'total_paid': paid_debt
        }
    )[0]  # Возвращаем обновленный или созданный объект


def update_calendar_statistics(date_obj, user=None, store=None, city=None, **kwargs):
    """
    Обновляет статистику календаря для указанной даты

    :param date_obj: Дата для обновления статистики
    :param user: Объект пользователя (если статистика привязана к пользователю)
    :param store: Объект магазина (если статистика привязана к магазину)
    :param city: Объект города (если статистика привязана к городу)
    :param kwargs: Дополнительные флаги
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


def generate_inventory_summary(user):
    """Генерация сводки по остаткам товаров партнера"""
    today = date.today()

    # Получаем все товары партнера
    partner_products = PartnerProduct.objects.filter(partner=user)

    if not partner_products.exists():
        return None

    # Суммируем показатели
    total_quantity = sum(p.quantity for p in partner_products)
    total_sold = sum(p.sold_quantity for p in partner_products)
    total_damaged = sum(p.damaged_quantity for p in partner_products)
    total_bonus = sum(p.bonus_quantity for p in partner_products)
    total_returned = sum(p.returned_quantity for p in partner_products)
    total_remaining = sum(p.remaining_quantity for p in partner_products)

    # Расчет стоимости
    total_value = sum(p.quantity * p.price for p in partner_products)
    total_sold_value = sum(p.sold_quantity * p.price for p in partner_products)
    total_damaged_value = sum(p.damaged_quantity * p.price for p in partner_products)
    total_bonus_value = sum(p.bonus_quantity * p.price for p in partner_products)
    total_remaining_value = sum(p.remaining_quantity * p.price for p in partner_products)

    # Создаем детализацию по товарам
    products_data = [
        {
            "id": p.id,
            "product_id": p.product.id,
            "name": p.product.name,
            "price": float(p.price),
            "quantity": p.quantity,
            "sold": p.sold_quantity,
            "damaged": p.damaged_quantity,
            "bonus": p.bonus_quantity,
            "returned": p.returned_quantity,
            "remaining": p.remaining_quantity,
            "total_value": float(p.quantity * p.price),
            "sold_value": float(p.sold_quantity * p.price),
            "damaged_value": float(p.damaged_quantity * p.price),
            "bonus_value": float(p.bonus_quantity * p.price),
            "remaining_value": float(p.remaining_quantity * p.price)
        }
        for p in partner_products
    ]

    # Сортируем по оставшемуся количеству по убыванию
    products_data.sort(key=lambda x: x["remaining"], reverse=True)

    return InventorySummary.objects.update_or_create(
        user=user,
        date=today,
        defaults={
            "total_quantity": total_quantity,
            "total_sold": total_sold,
            "total_damaged": total_damaged,
            "total_bonus": total_bonus,
            "total_returned": total_returned,
            "total_remaining": total_remaining,
            "total_value": total_value,
            "total_sold_value": total_sold_value,
            "total_damaged_value": total_damaged_value,
            "total_bonus_value": total_bonus_value,
            "total_remaining_value": total_remaining_value,
            "data": {
                "products": products_data
            }
        }
    )[0]  # Возвращаем обновленный или созданный объект


# Добавляем в apps/finance/services.py

def update_partner_statistics(user, income_amount=0, expense_amount=0, date=None):
    """
    Обновляет финансовую статистику партнера

    :param user: Пользователь-партнер
    :param income_amount: Сумма дохода для добавления
    :param expense_amount: Сумма расхода для добавления
    :param date: Дата статистики (по умолчанию - сегодня)
    """
    from .models import PartnerFinanceStat
    if date is None:
        date = timezone.now().date()

    # Получаем или создаем статистику на указанную дату
    stat, created = PartnerFinanceStat.objects.get_or_create(
        user=user,
        date=date,
        defaults={
            'total_approved_debt': 0,
            'total_damaged_loss': 0,
            'total_bonus_value': 0,
            'total_profit': 0,
            'total_expenses': 0,
            'total_sold': 0,
            'total_sold_quantity': 0
        }
    )

    # Обновляем показатели
    if income_amount > 0:
        stat.total_approved_debt += income_amount
        stat.total_profit += income_amount

    if expense_amount > 0:
        stat.total_expenses += expense_amount
        stat.total_profit -= expense_amount

    stat.save()

    # Обновляем метки календаря
    update_calendar_statistics(
        date,
        user=user,
        has_sales=(income_amount > 0),
        has_expenses=(expense_amount > 0)
    )

    return stat


# Модифицируем apps/finance/services.py

def update_partner_daily_stats(user, date=None):
    """
    Обновляет ежедневную статистику партнера

    :param user: Пользователь-партнер
    :param date: Дата (по умолчанию - сегодня)
    :return: Обновленный или созданный объект статистики
    """
    if date is None:
        date = timezone.now().date()

    from apps.orders.models import ProductRequest
    from apps.products.models import PartnerProduct
    from apps.finance.models import FinanceEntry

    # Получаем или создаем статистику
    from apps.finance.models import PartnerFinanceStat
    stats, created = PartnerFinanceStat.objects.get_or_create(
        user=user,
        date=date,
        defaults={
            'total_requested_quantity': 0,
            'total_requested_amount': 0,
            'total_sold_quantity': 0,
            'total_sold_amount': 0,
            'total_debt_to_admin': 0,
            'total_expenses': 0,
            'total_damaged_quantity': 0,
            'total_bonus_quantity': 0,
            'total_remaining_quantity': 0,
            'detailed_data': {}
        }
    )

    # 1. Запрошенные товары для себя (SELF) за этот день
    self_requests = ProductRequest.objects.filter(
        user=user,
        request_type='SELF',
        created_at__date=date
    )

    total_requested_quantity = self_requests.aggregate(total=Sum('quantity'))['total'] or 0
    total_requested_amount = sum(r.quantity * r.product.price for r in self_requests if r.product)

    # Детали по запрошенным товарам
    requested_details = {}
    for request in self_requests:
        product_name = request.product.name
        if product_name not in requested_details:
            requested_details[product_name] = {
                'quantity': 0,
                'amount': 0,
                'bonus': 0
            }
        requested_details[product_name]['quantity'] += request.quantity
        requested_details[product_name]['amount'] += request.quantity * request.product.price
        requested_details[product_name]['bonus'] += request.bonus_quantity

    # 2. Проданные товары (STORE) за этот день
    store_requests = ProductRequest.objects.filter(
        user=user,
        request_type='STORE',
        created_at__date=date
    )

    total_sold_quantity = store_requests.aggregate(total=Sum('quantity'))['total'] or 0
    total_sold_amount = sum(r.quantity * r.partner_product.price for r in store_requests if r.partner_product)

    # Детали по проданным товарам
    sold_details = {}
    for request in store_requests:
        if not request.partner_product or not request.partner_product.product:
            continue

        product_name = request.partner_product.product.name
        if product_name not in sold_details:
            sold_details[product_name] = {
                'quantity': 0,
                'amount': 0,
                'bonus': 0
            }
        sold_details[product_name]['quantity'] += request.quantity
        sold_details[product_name]['amount'] += request.quantity * request.partner_product.price
        sold_details[product_name]['bonus'] += request.bonus_quantity

    # 3. Долг администратору (по подтвержденным SELF-запросам)
    debt_to_admin = ProductRequest.objects.filter(
        user=user,
        request_type='SELF',
        status='approved'
    ).aggregate(total=Sum('total_price'))['total'] or 0

    # 4. Расходы партнера
    expenses = FinanceEntry.objects.filter(
        user=user,
        entry_type='expense',
        date=date
    ).aggregate(total=Sum('amount'))['total'] or 0

    # 5. Бракованные товары
    damaged_entries = FinanceEntry.objects.filter(
        user=user,
        entry_type='damage',
        date=date
    )

    total_damaged_quantity = damaged_entries.aggregate(total=Sum('quantity'))['total'] or 0

    # Детали по бракованным товарам
    damaged_details = {}
    for entry in damaged_entries:
        if not entry.partner_product or not entry.partner_product.product:
            continue

        product_name = entry.partner_product.product.name
        if product_name not in damaged_details:
            damaged_details[product_name] = 0
        damaged_details[product_name] += entry.quantity

    # 6. Бонусные товары (общая сумма бонусов из запросов STORE)
    bonus_quantity = store_requests.aggregate(total=Sum('bonus_quantity'))['total'] or 0

    # 7. Остаток товаров (из PartnerProduct)
    partner_products = PartnerProduct.objects.filter(partner=user)
    remaining_quantity = sum(p.remaining_quantity for p in partner_products)

    # Детали по остаткам
    remaining_details = {}
    for p in partner_products:
        product_name = p.product.name
        remaining_details[product_name] = p.remaining_quantity

    # Обновляем статистику
    stats.total_requested_quantity = total_requested_quantity
    stats.total_requested_amount = total_requested_amount
    stats.total_sold_quantity = total_sold_quantity
    stats.total_sold_amount = total_sold_amount
    stats.total_debt_to_admin = debt_to_admin
    stats.total_expenses = expenses
    stats.total_damaged_quantity = total_damaged_quantity
    stats.total_bonus_quantity = bonus_quantity
    stats.total_remaining_quantity = remaining_quantity

    # Обновляем детализацию
    stats.detailed_data = {
        'requested': requested_details,
        'sold': sold_details,
        'damaged': damaged_details,
        'remaining': remaining_details
    }

    stats.save()
    return stats


def update_store_daily_stats(store, date=None):
    """
    Обновляет ежедневную статистику магазина

    :param store: Магазин
    :param date: Дата (по умолчанию - сегодня)
    :return: Обновленный или созданный объект статистики
    """
    if date is None:
        date = timezone.now().date()

    from apps.orders.models import ProductRequest
    from apps.stores.models import StoreDebt

    # Получаем или создаем статистику
    from apps.finance.models import StoreFinanceStat
    stats, created = StoreFinanceStat.objects.get_or_create(
        store=store,
        date=date,
        defaults={
            'total_received_quantity': 0,
            'total_bonus_quantity': 0,
            'total_damaged_quantity': 0,
            'total_debt': 0,
            'total_paid_debt': 0,
            'total_partner_expenses': 0,
            'detailed_data': {}
        }
    )

    # 1. Полученные товары
    store_requests = ProductRequest.objects.filter(
        store=store,
        request_type='STORE',
        created_at__date=date
    )

    total_received_quantity = store_requests.aggregate(total=Sum('quantity'))['total'] or 0

    # Детали по полученным товарам
    received_details = {}
    for request in store_requests:
        if not request.partner_product or not request.partner_product.product:
            continue

        product_name = request.partner_product.product.name
        if product_name not in received_details:
            received_details[product_name] = {
                'quantity': 0,
                'bonus': 0,
                'damaged': 0
            }
        received_details[product_name]['quantity'] += request.quantity
        received_details[product_name]['bonus'] += request.bonus_quantity
        received_details[product_name]['damaged'] += request.damaged_quantity

    # 2. Бонусные товары
    bonus_quantity = store_requests.aggregate(total=Sum('bonus_quantity'))['total'] or 0

    # 3. Бракованные товары
    damaged_quantity = store_requests.aggregate(total=Sum('damaged_quantity'))['total'] or 0

    # 4. Долг магазина
    # Находим все долги, созданные в этот день
    new_debts = StoreDebt.objects.filter(
        store=store,
        created_at__date=date,
        is_paid=False
    )
    total_debt = new_debts.aggregate(total=Sum('amount'))['total'] or 0

    # 5. Погашенный долг
    paid_debts = StoreDebt.objects.filter(
        store=store,
        is_paid=True,
        paid_at__date=date
    )
    total_paid_debt = paid_debts.aggregate(total=Sum('amount'))['total'] or 0

    # 6. Расходы партнеров, связанные с этим магазином
    from apps.finance.models import FinanceEntry
    partner_expenses = FinanceEntry.objects.filter(
        entry_type='expense',
        date=date,
        store=store  # Предполагается, что в FinanceEntry есть поле store
    ).aggregate(total=Sum('amount'))['total'] or 0

    # Обновляем статистику
    stats.total_received_quantity = total_received_quantity
    stats.total_bonus_quantity = bonus_quantity
    stats.total_damaged_quantity = damaged_quantity
    stats.total_debt = total_debt
    stats.total_paid_debt = total_paid_debt
    stats.total_partner_expenses = partner_expenses

    # Обновляем детализацию
    stats.detailed_data = {
        'received': received_details
    }

    stats.save()
    return stats