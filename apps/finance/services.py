from decimal import Decimal
from datetime import datetime
from django.db.models import Sum, Q
from django.utils.timezone import make_aware
from apps.orders.models import Order, OrderItem, DefectItem
from apps.products.models import PartnerInventory
from apps.stores.models import Store, StoreExpense, StoreDebt, StoreDebtPayment
from apps.users.models import User


def parse_date_range(request):
    date_str = request.query_params.get("date")
    start_date = request.query_params.get("start_date")
    end_date = request.query_params.get("end_date")

    if date_str:
        date = datetime.strptime(date_str, "%Y-%m-%d").date()
        return make_aware(datetime.combine(date, datetime.min.time())), make_aware(datetime.combine(date, datetime.max.time()))
    elif start_date and end_date:
        s = datetime.strptime(start_date, "%Y-%m-%d")
        e = datetime.strptime(end_date, "%Y-%m-%d")
        return make_aware(datetime.combine(s, datetime.min.time())), make_aware(datetime.combine(e, datetime.max.time()))
    return None, None


def calc_partner_stats(user, start=None, end=None):
    partner_orders = Order.objects.filter(partner=user)

    if start and end:
        partner_orders = partner_orders.filter(created_at__range=(start, end))

    self_orders = partner_orders.filter(order_type="admin_to_partner", status="confirmed")
    store_orders = partner_orders.filter(order_type="partner_to_store", status="confirmed")

    requested_items = OrderItem.objects.filter(order__in=self_orders)
    sold_items = OrderItem.objects.filter(order__in=store_orders)

    total_requested = requested_items.aggregate(total=Sum('quantity'))['total'] or 0
    total_sold = sold_items.aggregate(total=Sum('quantity'))['total'] or 0
    sold_price = sold_items.aggregate(amount=Sum('total_price'))['amount'] or Decimal(0)

    expenses = StoreExpense.objects.filter(store__in=Store.objects.filter(
        id__in=Order.objects.filter(partner=user, order_type="partner_to_store").values_list('store_id', flat=True)
    ))
    if start and end:
        expenses = expenses.filter(expense_date__range=(start.date(), end.date()))
    total_expense = expenses.aggregate(amount=Sum('amount'))['amount'] or Decimal(0)

    defects = DefectItem.objects.filter(order__partner=user)
    if start and end:
        defects = defects.filter(created_at__range=(start, end))
    total_defects = defects.aggregate(qty=Sum('quantity'))['qty'] or 0

    inventory = PartnerInventory.objects.filter(partner=user)
    catalog_total = inventory.aggregate(qty=Sum('quantity'))['qty'] or 0

    profit = sold_price - total_expense

    return {
        "requested": total_requested,
        "sold": total_sold,
        "sold_amount": sold_price,
        "expense": total_expense,
        "defect": total_defects,
        "remaining": catalog_total,
        "profit": profit
    }


# Остальные функции (calc_store_stats, calc_admin_stats) без изменений


def calc_store_stats(store, start=None, end=None):
    """
    Статистика по магазину
    """
    orders = Order.objects.filter(store=store, status="confirmed")
    if start and end:
        orders = orders.filter(created_at__range=(start, end))

    items = OrderItem.objects.filter(order__in=orders)
    income = items.aggregate(amount=Sum('total_price'))['amount'] or Decimal(0)
    bonus_qty = items.aggregate(qty=Sum('bonus_quantity'))['qty'] or 0

    expenses = StoreExpense.objects.filter(store=store)
    if start and end:
        expenses = expenses.filter(expense_date__range=(start.date(), end.date()))
    expense_sum = expenses.aggregate(amount=Sum('amount'))['amount'] or Decimal(0)

    defects = DefectItem.objects.filter(order__store=store)
    if start and end:
        defects = defects.filter(created_at__range=(start, end))
    defect_qty = defects.aggregate(qty=Sum('quantity'))['qty'] or 0

    debt = StoreDebt.objects.filter(store=store).aggregate(amount=Sum('amount'))['amount'] or Decimal(0)
    paid = StoreDebtPayment.objects.filter(store=store).aggregate(amount=Sum('amount'))['amount'] or Decimal(0)

    balance = income - expense_sum - (bonus_qty * Decimal(0))  # цена бонуса по желанию можно добавить

    return {
        "income": income,
        "expenses": expense_sum,
        "defects": defect_qty,
        "bonus": bonus_qty,
        "debt": debt,
        "paid_debt": paid,
        "remaining_debt": debt - paid,
        "profit": income - expense_sum,
        "balance": balance
    }


def calc_admin_stats(filters: dict, start=None, end=None):
    """
    Админская сводная статистика
    """
    partner_id = filters.get("partner_id")
    store_id = filters.get("store_id")
    city_id = filters.get("city_id")

    stores = Store.objects.all()
    users = User.objects.filter(role="partner")
    if partner_id:
        users = users.filter(id=partner_id)
        stores = stores.filter(partner_id=partner_id)
    if store_id:
        stores = stores.filter(id=store_id)
    if city_id:
        stores = stores.filter(city_id=city_id)

    # Доход = все admin_to_partner заказы
    orders = Order.objects.filter(order_type="admin_to_partner", status="confirmed")
    if start and end:
        orders = orders.filter(created_at__range=(start, end))
    if partner_id:
        orders = orders.filter(partner_id=partner_id)

    income_items = OrderItem.objects.filter(order__in=orders)
    income = income_items.aggregate(amount=Sum('total_price'))['amount'] or Decimal(0)
    bonus_qty = income_items.aggregate(qty=Sum('bonus_quantity'))['qty'] or 0

    # Расходы
    expenses = StoreExpense.objects.filter(store__in=stores)
    if start and end:
        expenses = expenses.filter(expense_date__range=(start.date(), end.date()))
    total_expense = expenses.aggregate(amount=Sum('amount'))['amount'] or Decimal(0)

    # Брак
    defects = DefectItem.objects.filter(order__store__in=stores)
    if start and end:
        defects = defects.filter(created_at__range=(start, end))
    defect_qty = defects.aggregate(qty=Sum('quantity'))['qty'] or 0

    debt = StoreDebt.objects.filter(store__in=stores).aggregate(amount=Sum('amount'))['amount'] or Decimal(0)
    paid = StoreDebtPayment.objects.filter(store__in=stores).aggregate(amount=Sum('amount'))['amount'] or Decimal(0)

    # Остаток по инвентарю
    inventory = PartnerInventory.objects.filter(partner__in=users)
    remaining = inventory.aggregate(qty=Sum('quantity'))['qty'] or 0

    balance = income - total_expense - (bonus_qty * Decimal(0))  # если нужно учитывать стоимость бонуса

    return {
        "income": income,
        "expenses": total_expense,
        "bonus": bonus_qty,
        "defect": defect_qty,
        "debt": debt,
        "paid_debt": paid,
        "remaining_debt": debt - paid,
        "remaining_inventory": remaining,
        "balance": balance
    }
