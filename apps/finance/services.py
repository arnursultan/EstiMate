# apps/finance/services.py
from django.db.models import Sum, F, Q
from django.utils import timezone
from datetime import datetime, timedelta, date, time # Добавим date, time
from decimal import Decimal

from apps.users.models import User
from apps.products.models import Product, PartnerInventory
from apps.orders.models import Order, OrderItem, DefectItem
# УДАЛЕН StoreExpense из импорта
from apps.stores.models import Store, StoreDebt, StoreDebtPayment
# ДОБАВЛЕН импорт PartnerExpense
from .models import PartnerExpense
import logging

logger = logging.getLogger(__name__)


class PartnerStatisticsService:
    """Сервис для работы со статистикой партнера"""

    def get_partner_statistics(self, partner_id, date_range):
        """
        Получение статистики партнера за указанный диапазон дат.
        date_range: tuple (start_date, end_date), где start_date МОЖЕТ БЫТЬ None для 'all'
        """
        start_date, end_date = date_range
        # Определяем начальную дату для запросов, если она None (для 'all')
        query_start_date = start_date or date(2000, 1, 1) # Очень ранняя дата, если start_date is None

        print(f"\n--- [Service] Статистика для Партнера ID={partner_id} за Даты: {query_start_date} - {end_date} ---") # Отладка

        try:
            partner = User.objects.get(id=partner_id, role='partner')
            print(f"[Service] Партнер найден: {partner.first_name} {partner.last_name}") # Отладка
        except User.DoesNotExist:
            print(f"[Service] Ошибка: Партнер с ID={partner_id} не найден.") # Отладка
            return {"error": "Партнер не найден"}

        # --- Создаем timezone-aware datetime для диапазона КОНЕЧНОЙ ДАТЫ ---
        # Начальную дату используем как есть (или query_start_date)
        end_datetime = None
        try:
            tz = timezone.get_current_timezone()
            # Конец дня для конечной даты - ИСПРАВЛЕНИЕ: используем время 23:59:59.999999
            end_datetime = timezone.make_aware(datetime.combine(end_date, time(23, 59, 59, 999999)), tz)
            print(f"[Service] Конечная дата Datetime (с учетом пояса {tz}): {end_datetime}")
        except Exception as e:
            logger.exception("Ошибка при создании timezone-aware конечной даты")
            print("[Service] ВНИМАНИЕ: Не удалось создать timezone-aware конечную дату, используется сравнение по __date.")
            end_datetime = end_date # Fallback на сравнение с date


        # --- ПОЛУЧЕНИЕ ДАННЫХ (Используем query_start_date и end_datetime/end_date) ---
        print("[Service] Получение данных...") # Отладка

        # --- Заказы от администратора к партнеру (подтвержденные) ---
        requested_orders_qs = Order.objects.filter(partner_id=partner_id, order_type='admin_to_partner', status='confirmed')
        # Фильтрация по дате
        if isinstance(end_datetime, datetime):
             requested_orders_qs = requested_orders_qs.filter(created_at__gte=query_start_date, created_at__lte=end_datetime)
        else: # Fallback
             requested_orders_qs = requested_orders_qs.filter(created_at__date__gte=query_start_date, created_at__date__lte=end_date)
        requested_orders_count = requested_orders_qs.count()
        print(f"[Service] Найденные Requested Orders ({requested_orders_count}): {list(requested_orders_qs.values_list('id', flat=True))}")

        # --- Заказы от партнера к магазинам (подтвержденные) ---
        sold_orders_qs = Order.objects.filter(created_by_id=partner_id, order_type='partner_to_store', status='confirmed').select_related('store')
        if isinstance(end_datetime, datetime):
             sold_orders_qs = sold_orders_qs.filter(created_at__gte=query_start_date, created_at__lte=end_datetime)
        else:
             sold_orders_qs = sold_orders_qs.filter(created_at__date__gte=query_start_date, created_at__date__lte=end_date)
        sold_orders_count = sold_orders_qs.count()
        print(f"[Service] Найденные Sold Orders ({sold_orders_count}): {list(sold_orders_qs.values_list('id', flat=True))}")

        # --- Элементы заказов ---
        requested_items = OrderItem.objects.filter(order__in=requested_orders_qs).select_related('product')
        requested_items_count = requested_items.count()
        print(f"[Service] Найденные Requested Items ({requested_items_count})")

        sold_items = OrderItem.objects.filter(order__in=sold_orders_qs).select_related('product')
        sold_items_count = sold_items.count()
        sold_items_details = [(item.id, item.quantity, item.price, item.total_price) for item in sold_items]
        print(f"[Service] Найденные Sold Items ({sold_items_count}): {sold_items_details}")

        # --- Бракованные товары ---
        defect_items = DefectItem.objects.filter(order__in=sold_orders_qs).select_related('product')
        defect_items_count = defect_items.count()
        defects_details = [(d.id, d.quantity, d.product.price if d.product else 0) for d in defect_items]
        print(f"[Service] Найденные Defect Items ({defect_items_count}): {defects_details}")

        # --- Расходы ПАРТНЕРА ---
        partner_expenses = PartnerExpense.objects.filter(
            partner_id=partner_id,
            expense_date__gte=query_start_date, # Сравнение DateField с date
            expense_date__lte=end_date
        )
        partner_expenses_count = partner_expenses.count()
        expenses_agg = partner_expenses.aggregate(total=Sum('amount'))
        print(f"[Service] Найденные Partner Expenses ({partner_expenses_count}): Agg={expenses_agg}")

        # --- Платежи магазинов партнера ---
        partner_store_payments = StoreDebtPayment.objects.filter(store__partner_id=partner_id)
        if isinstance(end_datetime, datetime): # Фильтруем по datetime
             partner_store_payments = partner_store_payments.filter(payment_date__gte=query_start_date, payment_date__lte=end_datetime)
        else: # Fallback на __date
             partner_store_payments = partner_store_payments.filter(payment_date__date__gte=query_start_date, payment_date__date__lte=end_date)
        partner_store_payments_count = partner_store_payments.count()
        payments_agg = partner_store_payments.aggregate(total=Sum('amount'))
        print(f"[Service] Найденные Payments ({partner_store_payments_count}): Agg={payments_agg}")

        # --- РАСЧЕТЫ ---
        # (Без изменений)
        print("[Service] Расчет показателей...")
        total_requested_amount = sum(item.total_price for item in requested_items) or Decimal('0.00')
        total_sold_amount = sum(item.total_price for item in sold_items) or Decimal('0.00')
        total_partner_expenses = expenses_agg['total'] or Decimal('0.00')
        total_expenses = total_partner_expenses
        total_defect_amount = sum(d.quantity * (d.product.price if d.product else Decimal('0.00')) for d in defect_items) or Decimal('0.00')
        total_defects_count = sum(d.quantity for d in defect_items)
        total_payments_received = payments_agg['total'] or Decimal('0.00')
        profit = total_payments_received - total_expenses - total_defect_amount
        print(f"[Service] Расчет: Sold={total_sold_amount}, Payments={total_payments_received}, Expenses={total_expenses}, DefectCost={total_defect_amount}, Profit={profit}")

        # --- Инвентарь ---
        # (Без изменений)
        inventory_items = PartnerInventory.objects.filter(partner_id=partner_id)
        remaining_items_count = inventory_items.aggregate(total=Sum('quantity'))['total'] or 0
        print(f"[Service] Remaining Inventory Count: {remaining_items_count}")

        # --- ДЕТАЛИЗАЦИЯ ---
        # (Без изменений)
        print("[Service] Формирование детализации...")
        sold_products_detail = [ {"product_id": item.product_id, "product_name": item.product.name, "quantity": item.quantity, "price": float(item.price), "total_price": float(item.total_price), "order_id": item.order_id, "store_id": item.order.store_id, "store_name": item.order.store.name if item.order.store else None, "created_at": item.created_at.isoformat()} for item in sold_items ]
        stores_data = {}
        for order in sold_orders_qs:
            if not order.store_id: continue
            store_id = order.store_id
            summary = stores_data.setdefault(store_id, {"store_id": store_id, "store_name": order.store.name, "total_sold": Decimal('0.00'), "total_items": 0, "orders_count": 0})
            summary["orders_count"] += 1
            order_total = sum(item.total_price for item in order.order_items.all()) or Decimal('0.00')
            summary["total_sold"] += order_total
            summary["total_items"] += sum(item.quantity for item in order.order_items.all()) or 0
        expenses_detail = [ {"id": exp.id, "amount": float(exp.amount), "description": exp.description, "date": exp.expense_date.isoformat(), "created_at": exp.created_at.isoformat()} for exp in partner_expenses ]
        defects_detail = [ {"id": defect.id, "product_id": defect.product_id, "product_name": defect.product.name, "quantity": defect.quantity, "price": float(defect.product.price if defect.product else 0), "total_price": float(defect.quantity * (defect.product.price if defect.product else 0)), "order_id": defect.order_id, "description": defect.description, "created_at": defect.created_at.isoformat()} for defect in defect_items ]
        products_summary = self._get_products_summary(requested_items, sold_items)
        print("[Service] Детализация сформирована.")

        # --- ФОРМИРОВАНИЕ ОТВЕТА ---
        # (Без изменений, но используем оригинальные start_date / end_date для отображения)
        result = {
            "partner_id": partner.id,
            "partner_name": f"{partner.first_name} {partner.last_name}",
            "date_range": {
                "start_date": start_date.isoformat() if start_date else None, # Может быть None для 'all'
                "end_date": end_date.isoformat(),
                "formatted": "За все время" if start_date is None else (start_date.strftime("%d.%m.%Y") if start_date == end_date else f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}")
            },
            "requested_from_admin": { "total_amount": float(total_requested_amount),"items_count": requested_items_count,"orders_count": requested_orders_count, },
            "sold_to_stores": { "total_amount": float(total_sold_amount),"items_count": sold_items_count,"orders_count": sold_orders_count,"products_detail": sold_products_detail,"stores_summary": list(stores_data.values()) },
            "finances": { "payments_received": float(total_payments_received),"expenses": float(total_expenses),"defect_cost": float(total_defect_amount),"profit": float(profit),"expenses_detail": expenses_detail,"defects_detail": defects_detail },
            "inventory": { "remaining_items_count": remaining_items_count, },
            "products_summary": products_summary
        }
        print(f"[Service] Итоговый результат для партнера {partner_id}: Финансы = {result['finances']}")
        return result


    def _get_dates_from_period(self, period):
        """Получение начальной и конечной даты на основе периода"""
        # (Без изменений)
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
        # (Без изменений)
        products_summary = {}
        for item in requested_items:
            product_id = item.product_id
            summary = products_summary.setdefault(product_id, {"product_id": product_id, "product_name": item.product.name,"requested_quantity": 0, "sold_quantity": 0,"price": float(item.price),"total_requested_amount": 0.0, "total_sold_amount": 0.0})
            summary["requested_quantity"] += item.quantity
            summary["total_requested_amount"] += float(item.total_price)
        for item in sold_items:
            product_id = item.product_id
            summary = products_summary.setdefault(product_id, {"product_id": product_id, "product_name": item.product.name,"requested_quantity": 0, "sold_quantity": 0,"price": float(item.price),"total_requested_amount": 0.0, "total_sold_amount": 0.0})
            summary["sold_quantity"] += item.quantity
            summary["total_sold_amount"] += float(item.total_price)
        return list(products_summary.values())


# --- AdminStatisticsService ---
class AdminStatisticsService:
    """Сервис для работы со статистикой администратора"""

    _get_dates_from_period = PartnerStatisticsService._get_dates_from_period

    def get_admin_statistics(self, admin_id, date_range):
        """
        Получение общей статистики администратора за период.
        date_range: tuple (start_date, end_date), start_date МОЖЕТ БЫТЬ None
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

        # --- Создаем timezone-aware datetime для КОНЕЧНОЙ ДАТЫ ---
        end_datetime = None
        try:
            tz = timezone.get_current_timezone()
            # ИСПРАВЛЕНИЕ: используем время 23:59:59.999999 вместо time.max
            end_datetime = timezone.make_aware(datetime.combine(end_date, time(23, 59, 59, 999999)), tz)
            print(f"[Service] Админ конечная дата Datetime (с учетом пояса {tz}): {end_datetime}")
        except Exception as e:
            logger.exception("Ошибка при создании timezone-aware конечной даты для админа")
            print("[Service] ВНИМАНИЕ: Не удалось создать timezone-aware конечную дату для админа, используется сравнение по __date.")
            end_datetime = end_date

        # --- ПОЛУЧЕНИЕ ДАННЫХ ---
        print("[Service] Получение данных для админ статистики...")

        # --- Заказы от партнеров к магазинам ---
        store_orders_qs = Order.objects.filter(order_type='partner_to_store', status='confirmed')
        if isinstance(end_datetime, datetime):
             store_orders_qs = store_orders_qs.filter(created_at__gte=query_start_date, created_at__lte=end_datetime)
        else:
             store_orders_qs = store_orders_qs.filter(created_at__date__gte=query_start_date, created_at__date__lte=end_date)
        store_orders_count = store_orders_qs.count()
        print(f"[Service] Админ: Найденные Store Orders ({store_orders_count})")

        # --- Заказы от админа к партнерам ---
        partner_orders_qs = Order.objects.filter(order_type='admin_to_partner', status='confirmed')
        if isinstance(end_datetime, datetime):
            partner_orders_qs = partner_orders_qs.filter(created_at__gte=query_start_date, created_at__lte=end_datetime)
        else:
            partner_orders_qs = partner_orders_qs.filter(created_at__date__gte=query_start_date, created_at__date__lte=end_date)
        partner_orders_count = partner_orders_qs.count()
        print(f"[Service] Админ: Найденные Partner Orders ({partner_orders_count})")

        # --- Элементы заказов ---
        store_order_items = OrderItem.objects.filter(order__in=store_orders_qs).select_related('product')
        partner_order_items = OrderItem.objects.filter(order__in=partner_orders_qs).select_related('product')
        print(f"[Service] Админ: Найденные Store Order Items ({store_order_items.count()})")
        print(f"[Service] Админ: Найденные Partner Order Items ({partner_order_items.count()})")

        # --- Брак ---
        defect_items = DefectItem.objects.filter(order__in=store_orders_qs).select_related('product')
        print(f"[Service] Админ: Найденные Defect Items ({defect_items.count()})")

        # --- Долги за период---
        period_store_debts = StoreDebt.objects.filter(created_at__date__gte=query_start_date, created_at__date__lte=end_date)
        print(f"[Service] Админ: Найденные Period Store Debts ({period_store_debts.count()})")

        # --- Платежи за период ---
        period_store_payments = StoreDebtPayment.objects.all()
        if isinstance(end_datetime, datetime):
             period_store_payments = period_store_payments.filter(payment_date__gte=query_start_date, payment_date__lte=end_datetime)
        else:
             period_store_payments = period_store_payments.filter(payment_date__date__gte=query_start_date, payment_date__date__lte=end_date)
        print(f"[Service] Админ: Найденные Period Store Payments ({period_store_payments.count()})")

        # --- Расходы ВСЕХ ПАРТНЕРОВ за период ---
        all_partner_expenses = PartnerExpense.objects.filter(expense_date__gte=query_start_date, expense_date__lte=end_date)
        expenses_agg = all_partner_expenses.aggregate(total=Sum('amount'))
        print(f"[Service] Админ: Найденные Partner Expenses ({all_partner_expenses.count()}): Agg={expenses_agg}")

        # --- Инвентарь Админа ---
        admin_inventory = Product.objects.filter(is_deleted=False)
        remaining_inventory_count = admin_inventory.aggregate(total=Sum('quantity'))['total'] or 0
        remaining_inventory_value = sum(p.quantity * p.price for p in admin_inventory if p.quantity and p.price) or Decimal('0.00')
        print(f"[Service] Админ: Inventory: Count={remaining_inventory_count}, Value={remaining_inventory_value}")

        # --- РАСЧЕТЫ ---
        # (Без изменений)
        print("[Service] Расчет админ показателей...")
        total_sales_amount_period = sum(item.total_price for item in store_order_items) or Decimal('0.00')
        total_requested_by_partners_amount_period = sum(item.total_price for item in partner_order_items) or Decimal('0.00')
        total_debt_created_period = period_store_debts.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        total_paid_debt_period = period_store_payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        total_expenses_amount_period = expenses_agg['total'] or Decimal('0.00')
        total_defect_cost_period = sum(d.quantity * (d.product.price if d.product else Decimal('0.00')) for d in defect_items) or Decimal('0.00')
        total_defect_count_period = sum(d.quantity for d in defect_items)
        total_bonus_count_period = sum(item.bonus_quantity or 0 for item in store_order_items)
        print(f"[Service] Админ Расчет: Sales={total_sales_amount_period}, Paid={total_paid_debt_period}, Expenses={total_expenses_amount_period}, DefectCost={total_defect_cost_period}, GivenToPartners={total_requested_by_partners_amount_period}")

        # --- ФОРМИРОВАНИЕ ОТВЕТА ---
        # (Без изменений)
        result = {
            "admin_id": admin.id,
            "admin_name": f"{admin.first_name} {admin.last_name}",
             "date_range": {
                 "start_date": start_date.isoformat() if start_date else None,
                 "end_date": end_date.isoformat(),
                 "formatted": "За все время" if start_date is None else (start_date.strftime("%d.%m.%Y") if start_date == end_date else f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}")
             },
             "period_summary": {
                 "sales_amount": float(total_sales_amount_period),
                 "payments_received": float(total_paid_debt_period),
                 "partner_expenses_total": float(total_expenses_amount_period),
                 "defect_cost": float(total_defect_cost_period),
                 "products_given_to_partners": float(total_requested_by_partners_amount_period),
                 "orders_to_stores_count": store_orders_count,
                 "orders_to_partners_count": partner_orders_count,
                 "bonus_items_count": total_bonus_count_period,
                 "defect_items_count": total_defect_count_period,
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
        # (Без изменений по сравнению с предыдущей версией с отладкой)
        start_date, end_date = date_range
        print(f"\n--- [Service] Статистика по партнерам для Админа ID={admin_id} за Даты: {start_date} - {end_date} ---")

        try: admin = User.objects.get(id=admin_id, role='admin')
        except User.DoesNotExist: return {"error": "Администратор не найден"}

        partners = User.objects.filter(role='partner', is_active=True, is_deleted=False, status='approved')
        print(f"[Service] Найдено {partners.count()} партнеров для обсчета.")
        partners_data = []
        partner_service = PartnerStatisticsService()

        total_requested, total_sold, total_expenses, total_profit, total_payments_received = (Decimal(0) for _ in range(5))

        for partner in partners:
            print(f"[Service] Расчет статистики для партнера ID={partner.id}...")
            try:
                partner_stats = partner_service.get_partner_statistics(partner_id=partner.id, date_range=date_range)
                if "error" in partner_stats: print(f"[Service] Ошибка получения статистики для партнера {partner.id}: {partner_stats['error']}"); continue

                requested = Decimal(str(partner_stats.get("requested_from_admin", {}).get("total_amount", 0.0)))
                sold = Decimal(str(partner_stats.get("sold_to_stores", {}).get("total_amount", 0.0)))
                payments = Decimal(str(partner_stats.get("finances", {}).get("payments_received", 0.0)))
                expenses = Decimal(str(partner_stats.get("finances", {}).get("expenses", 0.0)))
                profit = Decimal(str(partner_stats.get("finances", {}).get("profit", 0.0)))
                remaining_items = partner_stats.get("inventory", {}).get("remaining_items_count", 0)

                total_requested += requested; total_sold += sold; total_payments_received += payments; total_expenses += expenses; total_profit += profit

                partners_data.append({"partner_id": partner.id,"partner_name": f"{partner.first_name} {partner.last_name}","requested_amount": float(requested),"sold_amount": float(sold),"payments_received": float(payments),"expenses": float(expenses),"profit": float(profit),"remaining_items": remaining_items})
                print(f"[Service] Статистика для партнера {partner.id} успешно рассчитана.")
            except Exception as e: logger.exception(f"Критическая ошибка получения статистики для партнера {partner.id}: {str(e)}"); print(f"[Service] КРИТИЧЕСКАЯ ОШИБКА получения статистики для партнера {partner.id}: {str(e)}")

        result = {
            "date_range": {"start_date": start_date.isoformat() if start_date else None,"end_date": end_date.isoformat(),"formatted": "За все время" if start_date is None else (start_date.strftime("%d.%m.%Y") if start_date == end_date else f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}")},
            "total": {"partners_count": len(partners_data),"requested_amount": float(total_requested),"sold_amount": float(total_sold),"payments_received": float(total_payments_received),"expenses": float(total_expenses),"profit": float(total_profit)},
            "partners": partners_data
        }
        print(f"[Service] Итоговая статистика по партнерам: {result}")
        return result