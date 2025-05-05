# apps/finance/services.py
from django.db.models import Sum, F, Q, Count, Prefetch, OuterRef, Subquery, Value, CharField, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import datetime, timedelta, date, time
from decimal import Decimal

# Импорты моделей из соответствующих приложений
from apps.users.models import User
from apps.products.models import Product, PartnerInventory
from apps.orders.models import Order, OrderItem, DefectItem # OrderItem/DefectItem теперь могут иметь product=None
from apps.stores.models import Store, StoreDebt, StoreDebtPayment # StoreExpense удален
from .models import PartnerExpense # Импортируем расходы партнера

import logging

logger = logging.getLogger(__name__)

# Определим константу для "Товар удален"
DELETED_PRODUCT_NAME = "Товар удален"

class PartnerStatisticsService:
    """Сервис для работы со статистикой партнера"""

    def get_partner_statistics(self, partner_id, date_range):
        """
        Получение статистики партнера за указанный диапазон дат.
        date_range: tuple (start_date, end_date), где start_date МОЖЕТ БЫТЬ None для 'all'.
        """
        start_date, end_date = date_range
        # Определяем начальную дату для запросов, если она None (для 'all')
        query_start_date = start_date or date(2000, 1, 1) # Очень ранняя дата

        print(f"\n--- [Service] Статистика для Партнера ID={partner_id} за Даты: {start_date} - {end_date} ---") # Лог исходных дат

        try:
            partner = User.objects.get(id=partner_id, role='partner')
            print(f"[Service] Партнер найден: {partner.first_name} {partner.last_name}")
        except User.DoesNotExist:
            print(f"[Service] Ошибка: Партнер с ID={partner_id} не найден.")
            return {"error": "Партнер не найден"}

        # --- Создаем timezone-aware datetime для диапазона ---
        try:
            tz = timezone.get_current_timezone() # Получаем активный часовой пояс
            # Начало первого дня (00:00:00)
            start_datetime = timezone.make_aware(datetime.combine(query_start_date, time.min), tz)
            # Конец последнего дня (23:59:59.999999)
            end_datetime = timezone.make_aware(datetime.combine(end_date, time.max), tz)
            print(f"[Service] Диапазон Datetime для запросов (TZ: {tz}): {start_datetime} - {end_datetime}")
        except Exception as e:
            logger.exception("Критическая ошибка при создании timezone-aware datetime диапазона")
            return {"error": "Ошибка обработки диапазона дат"}

        # --- ПОЛУЧЕНИЕ ДАННЫХ (Используем datetime диапазон для DateTimeField) ---
        print("[Service] Получение данных...")

        # --- Заказы и связанные данные (используем prefetch) ---
        # Заказы админ->партнер
        requested_orders_qs = Order.objects.filter(
            partner_id=partner_id, order_type='admin_to_partner', status='confirmed',
            created_at__gte=start_datetime, created_at__lte=end_datetime
        ).prefetch_related(
            Prefetch('order_items', queryset=OrderItem.objects.select_related('product'))
        )

        # Заказы партнер->магазин
        sold_orders_qs = Order.objects.filter(
            created_by_id=partner_id, order_type='partner_to_store', status='confirmed',
            created_at__gte=start_datetime, created_at__lte=end_datetime
        ).select_related('store').prefetch_related(
             Prefetch('order_items', queryset=OrderItem.objects.select_related('product')),
             Prefetch('defect_items', queryset=DefectItem.objects.select_related('product'))
         )

        requested_orders_count = requested_orders_qs.count()
        sold_orders_count = sold_orders_qs.count()
        print(f"[Service] Найденные Requested Orders ({requested_orders_count})")
        print(f"[Service] Найденные Sold Orders ({sold_orders_count})")

        # Извлекаем предзагруженные данные
        requested_items = [item for order in requested_orders_qs for item in order.order_items.all()]
        sold_items = [item for order in sold_orders_qs for item in order.order_items.all()]
        defect_items = [defect for order in sold_orders_qs for defect in order.defect_items.all()]
        requested_items_count = len(requested_items)
        sold_items_count = len(sold_items)
        defect_items_count = len(defect_items)
        print(f"[Service] Найденные Requested Items ({requested_items_count})")
        print(f"[Service] Найденные Sold Items ({sold_items_count})")
        print(f"[Service] Найденные Defect Items ({defect_items_count})")

        # --- Расходы ПАРТНЕРА (DateField) ---
        partner_expenses = PartnerExpense.objects.filter(
            partner_id=partner_id,
            expense_date__gte=query_start_date, # Сравнение DateField с date
            expense_date__lte=end_date
        )
        expenses_agg = partner_expenses.aggregate(total=Sum('amount'))
        print(f"[Service] Найденные Partner Expenses ({partner_expenses.count()}): Agg={expenses_agg}")

        # --- Платежи магазинов партнера (DateTimeField) ---
        partner_store_payments = StoreDebtPayment.objects.filter(
             store__partner_id=partner_id,
             payment_date__gte=start_datetime, # Сравнение DateTimeField с datetime
             payment_date__lte=end_datetime
         )
        payments_agg = partner_store_payments.aggregate(total=Sum('amount'))
        print(f"[Service] Найденные Payments ({partner_store_payments.count()}): Agg={payments_agg}")


        # --- РАСЧЕТЫ ---
        print("[Service] Расчет показателей...")
        total_requested_amount = sum(item.total_price or Decimal('0.00') for item in requested_items)
        # Сумма проданного = сумма ПЛАТНЫХ товаров
        total_sold_amount = sum(item.paid_items_price for item in sold_items)
        total_partner_expenses = expenses_agg['total'] or Decimal('0.00')
        total_expenses = total_partner_expenses

        # Стоимость брака (используем свойство модели DefectItem)
        total_defects_count = sum(d.quantity for d in defect_items)
        total_defect_cost = sum(d.total_price for d in defect_items) or Decimal('0.00')

        # Бонусы (количество и стоимость)
        total_bonus_count = sum(item.bonus_quantity or 0 for item in sold_items)
        total_bonus_cost = sum(
             (item.bonus_quantity or 0) * (item.price or Decimal('0.00'))
             for item in sold_items
        ) or Decimal('0.00')

        total_payments_received = payments_agg['total'] or Decimal('0.00')
        # Прибыль = ПолученныеОплаты - РасходыПартнера - СтоимостьБрака - СтоимостьБонусов
        profit = total_payments_received - total_expenses - total_defect_cost - total_bonus_cost

        print(f"[Service] Расчет: Sold={total_sold_amount}, Payments={total_payments_received}, Expenses={total_expenses}, DefectCost={total_defect_cost}, BonusCost={total_bonus_cost}, Profit={profit}")

        # --- Инвентарь ---
        inventory_items = PartnerInventory.objects.filter(partner_id=partner_id)
        remaining_items_count = inventory_items.aggregate(total=Sum('quantity'))['total'] or 0
        print(f"[Service] Remaining Inventory Count: {remaining_items_count}")

        # --- ДЕТАЛИЗАЦИЯ ---
        print("[Service] Формирование детализации...")
        sold_products_detail = [
            {"product_id": item.product.id if item.product else None,
             "product_name": item.product.name if item.product else DELETED_PRODUCT_NAME,
             "quantity": item.quantity, "price": float(item.price or 0),
             "total_price": float(item.total_price or 0),
             "bonus_quantity": item.bonus_quantity or 0,
             "order_id": item.order_id,
             "store_id": item.order.store_id, "store_name": item.order.store.name if item.order.store else None,
             "created_at": item.created_at.isoformat()}
            for item in sold_items
        ]

        stores_data = {}
        for order in sold_orders_qs:
            if not order.store_id: continue
            store_id = order.store_id
            summary = stores_data.setdefault(store_id, {
                "store_id": store_id, "store_name": order.store.name,
                "total_sold": Decimal('0.00'), "total_items": 0, "orders_count": 0
            })
            summary["orders_count"] += 1
            # Сумма долга по заказу (платные товары)
            order_debt = order.total_price # Используем свойство заказа
            summary["total_sold"] += order_debt
            summary["total_items"] += order.total_items_quantity # Используем свойство заказа

        expenses_detail = [
            {"id": exp.id, "amount": float(exp.amount or 0), "description": exp.description,
             "date": exp.expense_date.isoformat(), "created_at": exp.created_at.isoformat()}
            for exp in partner_expenses
        ]

        defects_detail = [
            {"id": defect.id, "product_id": defect.product_id if defect.product else None,
             "product_name": defect.product.name if defect.product else DELETED_PRODUCT_NAME,
             "quantity": defect.quantity,
             "price": float(defect.product.price if defect.product and defect.product.price is not None else 0),
             "total_price": float(defect.total_price or 0), # Используем свойство DefectItem
             "order_id": defect.order_id, "description": defect.description,
             "created_at": defect.created_at.isoformat()}
            for defect in defect_items
        ]

        products_summary = self._get_products_summary(requested_items, sold_items)
        print("[Service] Детализация сформирована.")

        # --- ФОРМИРОВАНИЕ ОТВЕТА ---
        result = {
            "partner_id": partner.id,
            "partner_name": f"{partner.first_name} {partner.last_name}",
            "date_range": {
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat(),
                "formatted": "За все время" if start_date is None else (start_date.strftime("%d.%m.%Y") if start_date == end_date else f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}")
            },
            "requested_from_admin": {
                "total_amount": float(total_requested_amount),
                "items_count": requested_items_count,
                "orders_count": requested_orders_count,
            },
            "sold_to_stores": {
                "total_amount": float(total_sold_amount), # Сумма платных товаров
                "items_count": sold_items_count, # Общее количество строк товаров
                "quantity_sold": sum(item.quantity for item in sold_items), # Общее кол-во штук
                "orders_count": sold_orders_count,
                "products_detail": sold_products_detail,
                "stores_summary": list(stores_data.values())
            },
            "finances": {
                 "payments_received": float(total_payments_received), # Сколько получено от магазинов
                 "expenses": float(total_expenses), # Расходы партнера
                 "defect_cost": float(total_defect_cost), # Стоимость брака
                 "bonus_items_count": total_bonus_count, # Количество бонусных штук
                 "bonus_cost": float(total_bonus_cost), # Стоимость бонусных штук
                 "profit": float(profit), # Прибыль (с учетом расходов, брака, бонусов)
                 "expenses_detail": expenses_detail,
                 "defects_detail": defects_detail
            },
            "inventory": {
                "remaining_items_count": remaining_items_count,
            },
            "products_summary": products_summary # Сводка по товарам (запрошено/продано)
        }
        print(f"[Service] Итоговый результат для партнера {partner_id}: Финансы = {result.get('finances', {})}")
        return result

    def _get_dates_from_period(self, period):
        """Получение начальной и конечной даты на основе периода"""
        today = timezone.now().date()
        start_date, end_date = today, today
        if period == 'today': pass
        elif period == 'yesterday': start_date = end_date = today - timedelta(days=1)
        elif period == 'this_week': start_date = today - timedelta(days=today.weekday())
        elif period == 'last_week': end_date = today - timedelta(days=today.weekday() + 1); start_date = end_date - timedelta(days=6)
        elif period == 'this_month': start_date = today.replace(day=1)
        elif period == 'last_month': end_date = today.replace(day=1) - timedelta(days=1); start_date = end_date.replace(day=1)
        elif period == 'this_quarter': quarter = (today.month - 1) // 3 + 1; start_date = date(today.year, 3 * quarter - 2, 1)
        elif period == 'last_quarter':
            if today.month <= 3: year = today.year - 1; start_date = date(year, 10, 1); end_date = date(year, 12, 31)
            else: quarter = (today.month - 1) // 3; end_date = date(today.year, 3 * quarter, 1) - timedelta(days=1); start_date = end_date.replace(month=end_date.month - 2, day=1)
        elif period == 'this_year': start_date = today.replace(month=1, day=1)
        elif period == 'last_year': year = today.year - 1; start_date = date(year, 1, 1); end_date = date(year, 12, 31)
        else: logger.warning(f"Неизвестный период '{period}'. Используется 'today'.")
        return start_date, end_date

    def _get_products_summary(self, requested_items, sold_items):
        """Получение сводки по товарам (запрошено vs продано)"""
        products_summary = {}
        # Обработка запрошенных
        for item in requested_items:
            product_id = item.product_id
            if not product_id: continue
            product_name = item.product.name if item.product else DELETED_PRODUCT_NAME
            summary = products_summary.setdefault(product_id, {"product_id": product_id, "product_name": product_name,"requested_quantity": 0, "sold_quantity": 0,"price": float(item.price or 0),"total_requested_amount": 0.0, "total_sold_amount": 0.0})
            summary["requested_quantity"] += item.quantity
            summary["total_requested_amount"] += float(item.total_price or 0)
        # Обработка проданных
        for item in sold_items:
            product_id = item.product_id
            if not product_id: continue
            product_name = item.product.name if item.product else DELETED_PRODUCT_NAME
            summary = products_summary.setdefault(product_id, {"product_id": product_id, "product_name": product_name,"requested_quantity": 0, "sold_quantity": 0,"price": float(item.price or 0),"total_requested_amount": 0.0, "total_sold_amount": 0.0})
            summary["sold_quantity"] += item.quantity
            summary["total_sold_amount"] += float(item.paid_items_price) # Используем стоимость платных
        return list(products_summary.values())


# --- AdminStatisticsService ---
class AdminStatisticsService:
    """Сервис для работы со статистикой администратора"""

    _get_dates_from_period = PartnerStatisticsService._get_dates_from_period

    def get_admin_statistics(self, admin_id, date_range):
        """
        Получение общей статистики администратора за период.
        date_range: tuple (start_date, end_date), start_date МОЖЕТ БЫТЬ None.
        """
        start_date, end_date = date_range
        query_start_date = start_date or date(2000, 1, 1)
        print(f"\n--- [Service] Статистика для Админа ID={admin_id} за Даты: {query_start_date} - {end_date} ---")

        try:
            admin = User.objects.get(id=admin_id, role='admin')
            print(f"[Service] Администратор найден: {admin.first_name} {admin.last_name}")
        except User.DoesNotExist:
            print(f"[Service] Ошибка: Администратор с ID={admin_id} не найден.")
            return {"error": "Администратор не найден"}

        # --- Создаем timezone-aware datetime для диапазона ---
        try:
            tz = timezone.get_current_timezone()
            start_datetime = timezone.make_aware(datetime.combine(query_start_date, time.min), tz)
            end_datetime = timezone.make_aware(datetime.combine(end_date, time.max), tz)
            print(f"[Service] Админ диапазон Datetime (TZ: {tz}): {start_datetime} - {end_datetime}")
        except Exception as e:
            logger.exception("Критическая ошибка при создании timezone-aware datetime диапазона для админа")
            return {"error": "Ошибка обработки диапазона дат"}

        # --- ПОЛУЧЕНИЕ ДАННЫХ ---
        print("[Service] Получение данных для админ статистики...")

        store_orders_qs = Order.objects.filter(
            order_type='partner_to_store', status='confirmed',
            created_at__gte=start_datetime, created_at__lte=end_datetime
        ).prefetch_related(
            Prefetch('order_items', queryset=OrderItem.objects.select_related('product')),
            Prefetch('defect_items', queryset=DefectItem.objects.select_related('product'))
        )
        partner_orders_qs = Order.objects.filter(
            order_type='admin_to_partner', status='confirmed',
            created_at__gte=start_datetime, created_at__lte=end_datetime
        ).prefetch_related(
            Prefetch('order_items', queryset=OrderItem.objects.select_related('product'))
        )
        store_orders_count = store_orders_qs.count()
        print(f"[Service] Админ: Найденные Store Orders ({store_orders_count})")
        partner_orders_count = partner_orders_qs.count()
        print(f"[Service] Админ: Найденные Partner Orders ({partner_orders_count})")

        store_order_items = [item for order in store_orders_qs for item in order.order_items.all()]
        partner_order_items = [item for order in partner_orders_qs for item in order.order_items.all()]
        defect_items = [defect for order in store_orders_qs for defect in order.defect_items.all()]
        print(f"[Service] Админ: Найденные Store Order Items ({len(store_order_items)})")
        print(f"[Service] Админ: Найденные Partner Order Items ({len(partner_order_items)})")
        print(f"[Service] Админ: Найденные Defect Items ({len(defect_items)})")

        period_store_debts = StoreDebt.objects.filter(
            created_at__date__gte=query_start_date, created_at__date__lte=end_date)
        print(f"[Service] Админ: Найденные Period Store Debts ({period_store_debts.count()})")

        period_store_payments = StoreDebtPayment.objects.filter(
            payment_date__gte=start_datetime, payment_date__lte=end_datetime)
        print(f"[Service] Админ: Найденные Period Store Payments ({period_store_payments.count()})")

        all_partner_expenses = PartnerExpense.objects.filter(
            expense_date__gte=query_start_date, expense_date__lte=end_date)
        expenses_agg = all_partner_expenses.aggregate(total=Sum('amount'))
        print(f"[Service] Админ: Найденные Partner Expenses ({all_partner_expenses.count()}): Agg={expenses_agg}")

        admin_inventory = Product.objects.filter(is_deleted=False)
        remaining_inventory_count = admin_inventory.aggregate(total=Sum('quantity'))['total'] or 0
        remaining_inventory_value = sum(
            p.quantity * p.price for p in admin_inventory if p.quantity and p.price is not None) or Decimal('0.00')
        print(f"[Service] Админ: Inventory: Count={remaining_inventory_count}, Value={remaining_inventory_value}")

        # --- РАСЧЕТЫ ---
        print("[Service] Расчет админ показателей...")
        total_sales_amount_period = sum(item.paid_items_price for item in store_order_items)  # Сумма платных
        total_requested_by_partners_amount_period = sum(
            item.total_price or Decimal('0.00') for item in partner_order_items)
        total_debt_created_period = period_store_debts.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        total_paid_debt_period = period_store_payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        total_expenses_amount_period = expenses_agg['total'] or Decimal('0.00')
        total_defect_cost_period = sum(d.total_price for d in defect_items) or Decimal('0.00')  # Используем свойство
        total_defect_count_period = sum(d.quantity for d in defect_items)
        total_bonus_count_period = sum(item.bonus_quantity or 0 for item in store_order_items)
        total_bonus_cost_period = sum(
            (item.bonus_quantity or 0) * (item.price or Decimal('0.00'))
            for item in store_order_items
        ) or Decimal('0.00')

        # Расчет общего баланса: sales_amount - bonus_cost - defect_cost
        total_balance = total_sales_amount_period - total_bonus_cost_period - total_defect_cost_period

        print(
            f"[Service] Админ Расчет: Sales={total_sales_amount_period}, Paid={total_paid_debt_period}, Expenses={total_expenses_amount_period}, DefectCost={total_defect_cost_period}, BonusCost={total_bonus_cost_period}, GivenToPartners={total_requested_by_partners_amount_period}")
        print(f"[Service] Админ Расчет: Total Balance={total_balance}")

        # --- ФОРМИРОВАНИЕ ОТВЕТА ---
        result = {
            "admin_id": admin.id,
            "admin_name": f"{admin.first_name} {admin.last_name}",
            "date_range": {
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat(),
                "formatted": "За все время" if start_date is None else (start_date.strftime(
                    "%d.%m.%Y") if start_date == end_date else f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}")
            },
            "period_summary": {
                "sales_amount": float(total_sales_amount_period),  # Сумма платных товаров
                "payments_received": float(total_paid_debt_period),
                "partner_expenses_total": float(total_expenses_amount_period),
                "defect_cost": float(total_defect_cost_period),
                "bonus_cost": float(total_bonus_cost_period),  # Добавлено
                "products_given_to_partners": float(total_requested_by_partners_amount_period),
                "orders_to_stores_count": store_orders_count,
                "orders_to_partners_count": partner_orders_count,
                "bonus_items_count": total_bonus_count_period,
                "defect_items_count": total_defect_count_period,
                "total_balance": float(total_balance),  # Добавлен общий баланс
            },
            "inventory_status": {
                "remaining_items_count": remaining_inventory_count,
                "remaining_items_value": float(remaining_inventory_value),
            },
        }
        print(f"[Service] Итоговый результат для админа {admin_id}: {result}")
        return result

    def get_partners_statistics(self, admin_id, date_range):
        """Получение статистики по всем партнерам для администратора"""
        start_date, end_date = date_range
        print(f"\n--- [Service] Статистика по партнерам для Админа ID={admin_id} за Даты: {start_date} - {end_date} ---")

        try: admin = User.objects.get(id=admin_id, role='admin')
        except User.DoesNotExist: return {"error": "Администратор не найден"}

        partners = User.objects.filter(role='partner', is_active=True, is_deleted=False, status='approved')
        print(f"[Service] Найдено {partners.count()} партнеров для обсчета.")
        partners_data = []
        partner_service = PartnerStatisticsService()

        total_requested = Decimal('0.00')
        total_sold = Decimal('0.00') # Сумма платных товаров
        total_expenses = Decimal('0.00')
        total_profit = Decimal('0.00')
        total_payments_received = Decimal('0.00')
        total_bonus_cost = Decimal('0.00') # Добавили total_bonus_cost

        for partner in partners:
            print(f"[Service] Расчет статистики для партнера ID={partner.id}...")
            try:
                partner_stats = partner_service.get_partner_statistics(partner_id=partner.id, date_range=date_range)
                if "error" in partner_stats: print(f"[Service] Ошибка получения статистики для партнера {partner.id}: {partner_stats['error']}"); continue

                # Извлекаем показатели, используя float() для безопасности
                requested = Decimal(str(partner_stats.get("requested_from_admin", {}).get("total_amount", 0.0)))
                sold = Decimal(str(partner_stats.get("sold_to_stores", {}).get("total_amount", 0.0))) # Это уже сумма платных
                payments = Decimal(str(partner_stats.get("finances", {}).get("payments_received", 0.0)))
                expenses = Decimal(str(partner_stats.get("finances", {}).get("expenses", 0.0)))
                profit = Decimal(str(partner_stats.get("finances", {}).get("profit", 0.0)))
                bonus_cost = Decimal(str(partner_stats.get("finances", {}).get("bonus_cost", 0.0)))
                remaining_items = partner_stats.get("inventory", {}).get("remaining_items_count", 0)

                total_requested += requested; total_sold += sold; total_payments_received += payments; total_expenses += expenses; total_profit += profit; total_bonus_cost += bonus_cost

                partners_data.append({
                    "partner_id": partner.id,
                    "partner_name": f"{partner.first_name} {partner.last_name}",
                    "requested_amount": float(requested),
                    "sold_amount": float(sold), # Сумма платных
                    "payments_received": float(payments),
                    "expenses": float(expenses),
                    "bonus_cost": float(bonus_cost), # Добавляем
                    "profit": float(profit),
                    "remaining_items": remaining_items
                    })
                print(f"[Service] Статистика для партнера {partner.id} успешно рассчитана.")
            except Exception as e: logger.exception(f"Критическая ошибка получения статистики для партнера {partner.id}: {str(e)}"); print(f"[Service] КРИТИЧЕСКАЯ ОШИБКА получения статистики для партнера {partner.id}: {str(e)}")

        result = {
            "date_range": {"start_date": start_date.isoformat() if start_date else None,"end_date": end_date.isoformat(),"formatted": "За все время" if start_date is None else (start_date.strftime("%d.%m.%Y") if start_date == end_date else f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}")},
            "total": {
                "partners_count": len(partners_data),
                "requested_amount": float(total_requested),
                "sold_amount": float(total_sold), # Общая сумма платных товаров
                "payments_received": float(total_payments_received),
                "expenses": float(total_expenses),
                "bonus_cost": float(total_bonus_cost), # Добавляем общую стоимость бонусов
                "profit": float(total_profit)
                },
            "partners": partners_data
        }
        print(f"[Service] Итоговая статистика по партнерам: {result}")
        return result


class StoreGroupStatisticsService:
    """Сервис для расчета статистики по группе магазинов."""

    # Используем метод для получения дат из другого сервиса
    _get_dates_from_period = PartnerStatisticsService._get_dates_from_period

    def get_stores_statistics(self, user, date_range, city_id=None, partner_id=None):
        """
        Расчет статистики по группе магазинов.
        user: Запрашивающий пользователь (для определения прав)
        date_range: tuple (start_date, end_date), start_date может быть None
        city_id: опциональный ID города
        partner_id: опциональный ID партнера (для админа)
        """
        start_date, end_date = date_range
        query_start_date = start_date or date(2000, 1, 1)
        print(f"\n--- [Service] Статистика по Магазинам для User={user.id} за Даты: {query_start_date} - {end_date}, City={city_id}, Partner={partner_id} ---")

        # --- Фильтруем магазины ---
        stores_qs = Store.objects.filter(is_deleted=False, is_active=True, status='approved')
        if user.role == 'partner':
            stores_qs = stores_qs.filter(partner=user)
        elif user.role == 'admin':
            if partner_id:
                try: stores_qs = stores_qs.filter(partner_id=int(partner_id))
                except (ValueError, TypeError): stores_qs = Store.objects.none()
        else:
            return {"error": "Доступ запрещен"}

        if city_id:
             try: stores_qs = stores_qs.filter(city_id=int(city_id))
             except (ValueError, TypeError): stores_qs = Store.objects.none()

        store_ids = list(stores_qs.values_list('id', flat=True))
        stores_count = len(store_ids)
        print(f"[Service Stores] Найдено {stores_count} магазинов для статистики.")
        if stores_count == 0:
             return self._get_empty_stats(start_date, end_date, city_id, partner_id, user) # Передаем фильтры

        # --- Создаем datetime диапазон ---
        try:
            tz = timezone.get_current_timezone()
            start_datetime = timezone.make_aware(datetime.combine(query_start_date, time.min), tz)
            end_datetime = timezone.make_aware(datetime.combine(end_date, time.max), tz)
        except Exception as e:
            logger.exception("Ошибка при создании timezone-aware datetime диапазона для магазинов")
            return {"error": "Ошибка обработки диапазона дат"}

        # --- Получаем данные для ВСЕХ отфильтрованных магазинов ---
        orders_qs = Order.objects.filter(
            store_id__in=store_ids, order_type='partner_to_store', status='confirmed',
            created_at__gte=start_datetime, created_at__lte=end_datetime
        ).prefetch_related(
             Prefetch('order_items', queryset=OrderItem.objects.select_related('product')),
             Prefetch('defect_items', queryset=DefectItem.objects.select_related('product'))
         )
        orders_count = orders_qs.count()

        order_items = [item for order in orders_qs for item in order.order_items.all()]
        defect_items = [defect for order in orders_qs for defect in order.defect_items.all()]

        period_debts = StoreDebt.objects.filter(
            store_id__in=store_ids, created_at__date__gte=query_start_date, created_at__date__lte=end_date
        )
        period_payments = StoreDebtPayment.objects.filter(
            store_id__in=store_ids, payment_date__gte=start_datetime, payment_date__lte=end_datetime
        )
        partner_ids = list(stores_qs.values_list('partner_id', flat=True).distinct())
        period_partner_expenses = PartnerExpense.objects.filter(
             partner_id__in=partner_ids, expense_date__gte=query_start_date, expense_date__lte=end_date
         )

        # --- Агрегированные расчеты ---
        total_sales = sum(item.paid_items_price for item in order_items) # Сумма платных
        total_ordered_quantity = sum(item.quantity or 0 for item in order_items)
        total_bonus_quantity = sum(item.bonus_quantity or 0 for item in order_items)
        total_defect_cost = sum(d.total_price for d in defect_items) # Используем свойство
        total_defect_quantity = sum(d.quantity for d in defect_items)
        total_debt_created = period_debts.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        total_payments_received = period_payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        total_partner_expenses = period_partner_expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        # Общий ОСТАТОК долга по этим магазинам
        # Правильнее считать по каждому магазину и суммировать, либо использовать аннотацию
        # Упрощенный вариант (может быть неточным, если были платежи вне периода):
        # total_remaining_debt_all_time = stores_qs.aggregate(rem_debt=Sum('debts__amount') - Sum('debt_payments__amount'))['rem_debt'] or Decimal('0.00')
        # Более точный, но медленный:
        total_remaining_debt_all_time = sum(store.remaining_debt for store in stores_qs) or Decimal('0.00')


        # Общая прибыль за период = Оплаты - РасходыПартнеров - СтоимостьБрака - СтоимостьБонусов
        total_bonus_cost = sum(
             (item.bonus_quantity or 0) * (item.price or Decimal('0.00'))
             for item in order_items
        ) or Decimal('0.00')
        total_profit_period = total_payments_received - total_partner_expenses - total_defect_cost - total_bonus_cost

        return {
            "date_range": {
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat(),
                "formatted": "За все время" if start_date is None else (start_date.strftime("%d.%m.%Y") if start_date == end_date else f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}")
            },
            "filters": {
                 "city_id": city_id,
                 # Показываем ID партнера, если фильтр был применен (админом или это сам партнер)
                 "partner_id": partner_id if user.role == 'admin' and partner_id else (user.id if user.role == 'partner' else None)
             },
            "summary": {
                "stores_count": stores_count,
                "orders_count": orders_count,
                "total_sales_amount": float(total_sales),
                "total_payments_received": float(total_payments_received),
                "total_partner_expenses": float(total_partner_expenses),
                "total_defect_cost": float(total_defect_cost),
                "total_bonus_cost": float(total_bonus_cost), # Добавили стоимость бонусов
                "total_profit": float(total_profit_period),
                "total_ordered_quantity": total_ordered_quantity,
                "total_bonus_quantity": total_bonus_quantity,
                "total_defect_quantity": total_defect_quantity,
                "total_remaining_debt": float(total_remaining_debt_all_time)
            }
        }

    def _get_empty_stats(self, start_date, end_date, city_id, partner_id, user):
         """Возвращает структуру с нулями, если магазины не найдены"""
         return {
             "date_range": {"start_date": start_date.isoformat() if start_date else None,"end_date": end_date.isoformat(),"formatted": "..."},
             "filters": {
                 "city_id": city_id,
                 "partner_id": partner_id if user.role == 'admin' and partner_id else (user.id if user.role == 'partner' else None)
             },
             "summary": {"stores_count": 0,"orders_count": 0,"total_sales_amount": 0.0,"total_payments_received": 0.0,"total_partner_expenses": 0.0,"total_defect_cost": 0.0, "total_bonus_cost": 0.0, "total_profit": 0.0,"total_ordered_quantity": 0,"total_bonus_quantity": 0,"total_defect_quantity": 0,"total_remaining_debt": 0.0}
         }