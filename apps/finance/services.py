# apps/finance/services.py
from django.db.models import Sum, F, Q
from django.utils import timezone
from datetime import datetime, timedelta

from apps.users.models import User
from apps.products.models import Product, PartnerInventory
from apps.orders.models import Order, OrderItem, DefectItem
from apps.stores.models import StoreDebt, StoreDebtPayment, StoreExpense


class PartnerStatisticsService:
    """Сервис для работы со статистикой партнера"""

    def get_partner_statistics(self, partner_id, date=None, date_range=None, period=None):
        """
        Получение статистики партнера
        """
        try:
            partner = User.objects.get(id=partner_id, role='partner')
        except User.DoesNotExist:
            return {"error": "Партнер не найден"}

        # Определяем даты для фильтрации
        today = timezone.now().date()

        if period:
            start_date, end_date = self._get_dates_from_period(period)
        elif date:
            start_date = end_date = date
        elif date_range:
            start_date, end_date = date_range
        else:
            # По умолчанию - текущая дата
            start_date = end_date = today

        # Получаем заказы от администратора к партнеру (запрошенные товары)
        requested_orders = Order.objects.filter(
            partner=partner,
            order_type='admin_to_partner',
            status='confirmed',
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )

        # Получаем заказы от партнера к магазинам (проданные товары)
        sold_orders = Order.objects.filter(
            created_by=partner,
            order_type='partner_to_store',
            status='confirmed',
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )

        # Получаем элементы заказов
        requested_items = OrderItem.objects.filter(order__in=requested_orders)
        sold_items = OrderItem.objects.filter(order__in=sold_orders)

        # Получаем бракованные товары
        defect_items = DefectItem.objects.filter(
            order__in=sold_orders
        )

        # Получаем расходы
        expenses = StoreExpense.objects.filter(
            store__partner=partner,
            expense_date__gte=start_date,
            expense_date__lte=end_date
        )

        # Рассчитываем финансовые показатели
        total_requested_amount = float(sum(
            item.quantity * item.price for item in requested_items
        ) or 0)

        total_sold_amount = float(sum(
            item.quantity * item.price for item in sold_items
        ) or 0)

        total_expenses = float(sum(expense.amount for expense in expenses) or 0)

        # Рассчитываем остатки инвентаря
        inventory_items = PartnerInventory.objects.filter(partner=partner)
        remaining_items_count = sum(item.quantity for item in inventory_items)

        # Общее количество бракованных товаров
        total_defects = sum(defect.quantity for defect in defect_items)

        # Собираем данные о товарах
        products_data = self._get_products_summary(requested_items, sold_items)

        # Детальная информация о проданных товарах
        sold_products_detail = []
        for item in sold_items:
            try:
                product = item.product
                sold_products_detail.append({
                    "product_id": product.id,
                    "product_name": product.name,
                    "quantity": item.quantity,
                    "price": float(item.price),
                    "total_price": float(item.price * item.quantity),
                    "order_id": item.order.id,
                    "store_id": item.order.store.id if item.order.store else None,
                    "store_name": item.order.store.name if item.order.store else None,
                    "created_at": item.created_at.isoformat()
                })
            except Exception as e:
                print(f"Ошибка при обработке проданного товара: {str(e)}")

        # Информация о магазинах
        stores_data = {}
        for order in sold_orders:
            if not order.store:
                continue

            store_id = order.store.id
            if store_id not in stores_data:
                stores_data[store_id] = {
                    "store_id": store_id,
                    "store_name": order.store.name,
                    "total_sold": 0.0,
                    "total_items": 0,
                    "orders_count": 0
                }

            stores_data[store_id]["orders_count"] += 1
            stores_data[store_id]["total_sold"] += float(order.total_price or 0)
            stores_data[store_id]["total_items"] += sum(item.quantity for item in order.order_items.all())

        # Вычисляем прибыль
        profit = total_sold_amount - total_expenses

        # Формируем итоговый ответ
        result = {
            "partner_id": partner.id,
            "partner_name": f"{partner.first_name} {partner.last_name}",
            "date_range": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "formatted": start_date.strftime("%d.%m.%Y") if start_date == end_date else
                f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"
            },
            "requested": {
                "total_amount": total_requested_amount,
                "items_count": requested_items.count(),
                "orders_count": requested_orders.count(),
                "products": self._format_products_list(requested_items)
            },
            "sold": {
                "total_amount": total_sold_amount,
                "items_count": sold_items.count(),
                "orders_count": sold_orders.count(),
                "products": self._format_products_list(sold_items),
                "products_detail": sold_products_detail,  # Добавлено: детальная информация о проданных товарах
                "stores": list(stores_data.values())  # Добавлено: информация по магазинам
            },
            "debt": total_sold_amount,  # Долг магазинов перед партнером
            "expenses": total_expenses,
            "defects": total_defects,
            "remaining_items": remaining_items_count,
            "total_amount": total_sold_amount,  # Общая сумма
            "profit": profit,  # Прибыль
            "products_summary": products_data
        }

        return result

    def _get_dates_from_period(self, period):
        """Получение начальной и конечной даты на основе периода"""
        today = timezone.now().date()

        if period == 'today':
            return today, today
        elif period == 'yesterday':
            yesterday = today - timedelta(days=1)
            return yesterday, yesterday
        elif period == 'this_week':
            # Начало текущей недели (понедельник)
            start_date = today - timedelta(days=today.weekday())
            return start_date, today
        elif period == 'last_week':
            # Начало прошлой недели (понедельник)
            start_date = today - timedelta(days=today.weekday() + 7)
            # Конец прошлой недели (воскресенье)
            end_date = start_date + timedelta(days=6)
            return start_date, end_date
        elif period == 'this_month':
            # Начало текущего месяца
            start_date = today.replace(day=1)
            return start_date, today
        elif period == 'last_month':
            # Начало прошлого месяца
            if today.month == 1:
                start_date = today.replace(year=today.year - 1, month=12, day=1)
            else:
                start_date = today.replace(month=today.month - 1, day=1)
            # Конец прошлого месяца
            end_date = today.replace(day=1) - timedelta(days=1)
            return start_date, end_date
        elif period == 'this_quarter':
            # Определение текущего квартала
            quarter = (today.month - 1) // 3 + 1
            # Начало текущего квартала
            start_date = today.replace(month=3 * quarter - 2, day=1)
            return start_date, today
        elif period == 'last_quarter':
            # Определение прошлого квартала
            quarter = (today.month - 1) // 3
            if quarter == 0:  # Если текущий месяц в 1-м квартале, берем 4-й квартал прошлого года
                start_date = today.replace(year=today.year - 1, month=10, day=1)
                end_date = today.replace(year=today.year - 1, month=12, day=31)
            else:
                start_date = today.replace(month=3 * quarter - 2, day=1)
                # Конец прошлого квартала
                end_date = today.replace(month=3 * quarter, day=1) - timedelta(days=1)
            return start_date, end_date
        elif period == 'this_year':
            # Начало текущего года
            start_date = today.replace(month=1, day=1)
            return start_date, today
        elif period == 'last_year':
            # Прошлый год
            start_date = today.replace(year=today.year - 1, month=1, day=1)
            end_date = today.replace(year=today.year - 1, month=12, day=31)
            return start_date, end_date
        else:
            # По умолчанию - текущая дата
            return today, today

    def _get_products_summary(self, requested_items, sold_items):
        """Получение сводки по товарам"""
        products_summary = {}

        # Собираем данные о запрошенных товарах
        for item in requested_items:
            product_id = item.product_id
            if product_id not in products_summary:
                products_summary[product_id] = {
                    "product_id": product_id,
                    "product_name": item.product.name,
                    "requested_quantity": 0,
                    "sold_quantity": 0,
                    "price": float(item.price),  # Преобразуем в float
                    "total_requested": 0.0,
                    "total_sold": 0.0
                }

            products_summary[product_id]["requested_quantity"] += item.quantity
            products_summary[product_id]["total_requested"] += float(item.quantity * item.price)  # Преобразуем в float

        # Собираем данные о проданных товарах
        for item in sold_items:
            product_id = item.product_id
            if product_id not in products_summary:
                products_summary[product_id] = {
                    "product_id": product_id,
                    "product_name": item.product.name,
                    "requested_quantity": 0,
                    "sold_quantity": 0,
                    "price": float(item.price),  # Преобразуем в float
                    "total_requested": 0.0,
                    "total_sold": 0.0
                }

            products_summary[product_id]["sold_quantity"] += item.quantity
            products_summary[product_id]["total_sold"] += float(item.quantity * item.price)  # Преобразуем в float

        return list(products_summary.values())

    def _format_products_list(self, order_items):
        """Форматирование списка товаров для отображения"""
        product_quantities = {}

        for item in order_items:
            product_name = item.product.name
            if product_name not in product_quantities:
                product_quantities[product_name] = 0

            product_quantities[product_name] += item.quantity

        # Форматируем в виде строк
        result = []
        for product_name, quantity in product_quantities.items():
            result.append(f"{quantity} штук {product_name}")

        return result


# apps/finance/services.py - дополним существующий файл

class AdminStatisticsService:
    """Сервис для работы со статистикой администратора"""

    def get_admin_statistics(self, admin_id, date=None, date_range=None, period=None):
        """
        Получение общей статистики администратора

        Параметры:
        - admin_id: ID администратора
        - date: конкретная дата (опционально)
        - date_range: (start_date, end_date) - диапазон дат (опционально)
        - period: период ('today', 'yesterday', 'this_week', 'last_week', 'this_month', 'last_month', etc.)
        """
        try:
            admin = User.objects.get(id=admin_id, role='admin')
        except User.DoesNotExist:
            return {"error": "Администратор не найден"}

        # Определяем даты для фильтрации
        today = timezone.now().date()

        if period:
            start_date, end_date = self._get_dates_from_period(period)
        elif date:
            start_date = end_date = date
        elif date_range:
            start_date, end_date = date_range
        else:
            # По умолчанию - текущая дата
            start_date = end_date = today

        # Получаем все заказы за период
        from apps.orders.models import Order, OrderItem, DefectItem

        # Заказы от администратора к партнерам (доход)
        admin_orders = Order.objects.filter(
            order_type='admin_to_partner',
            status='confirmed',
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )

        # Заказы от партнеров к магазинам (долги магазинов)
        store_orders = Order.objects.filter(
            order_type='partner_to_store',
            status='confirmed',
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )

        # Получаем элементы заказов
        admin_order_items = OrderItem.objects.filter(order__in=admin_orders)
        store_order_items = OrderItem.objects.filter(order__in=store_orders)

        # Получаем бракованные товары
        defect_items = DefectItem.objects.filter(
            order__in=store_orders
        )

        # Получаем долги и платежи
        from apps.stores.models import StoreDebt, StoreDebtPayment

        store_debts = StoreDebt.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )

        store_payments = StoreDebtPayment.objects.filter(
            payment_date__date__gte=start_date,
            payment_date__date__lte=end_date
        )

        # Получаем расходы
        from apps.stores.models import StoreExpense

        expenses = StoreExpense.objects.filter(
            expense_date__gte=start_date,
            expense_date__lte=end_date
        )

        # Рассчитываем финансовые показатели
        admin_income = float(sum(
            item.quantity * item.price for item in admin_order_items
        ))

        store_debt = float(sum(
            debt.amount for debt in store_debts
        ))

        paid_debt = float(sum(
            payment.amount for payment in store_payments
        ))

        expenses_amount = float(sum(
            expense.amount for expense in expenses
        ))

        # Рассчитываем бонусы
        total_bonus_count = sum(
            item.bonus_quantity or 0 for item in store_order_items
        )

        # Примерно оцениваем стоимость бонусов (средняя цена товара * количество бонусов)
        avg_price = 0
        if store_order_items.count() > 0:
            avg_price = float(sum(item.price for item in store_order_items)) / store_order_items.count()

        bonuses_amount = total_bonus_count * avg_price

        # Общее количество товаров
        total_products = sum(item.quantity for item in admin_order_items)

        # Общее количество бракованных товаров
        total_defects = sum(defect.quantity for defect in defect_items)

        # Остаток товаров (на складе администратора)
        remaining_products = Product.objects.aggregate(total=Sum('quantity'))['total'] or 0

        # Общий баланс
        total_balance = admin_income - expenses_amount + paid_debt - bonuses_amount

        # Собираем данные о товарах по категориям
        products_data = self._get_admin_products_summary(admin_order_items)

        # Формируем итоговый ответ
        result = {
            "admin_id": admin.id,
            "admin_name": f"{admin.first_name} {admin.last_name}",
            "date_range": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "formatted": start_date.strftime("%d.%m.%Y") if start_date == end_date else
                f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"
            },
            "income": {
                "total_amount": admin_income,
                "orders_count": admin_orders.count(),
                "products_count": total_products
            },
            "expenses": expenses_amount,
            "store_debt": store_debt,
            "paid_debt": paid_debt,
            "bonuses": {
                "count": total_bonus_count,
                "amount": bonuses_amount
            },
            "defects": total_defects,
            "remaining_products": remaining_products,
            "total_balance": total_balance,
            "products": products_data,
            "chart_data": {
                "income": admin_income,
                "expenses": expenses_amount,
                "debt": store_debt,
                "bonuses": bonuses_amount
            }
        }

        return result

    def _get_dates_from_period(self, period):
        """Получение начальной и конечной даты на основе периода"""
        # Реализация аналогична методу в PartnerStatisticsService
        # ...

    def _get_admin_products_summary(self, order_items):
        """Получение сводки по товарам администратора"""
        products_summary = {}

        for item in order_items:
            product_id = item.product_id
            if product_id not in products_summary:
                products_summary[product_id] = {
                    "product_id": product_id,
                    "product_name": item.product.name,
                    "quantity": 0,
                    "price": float(item.price),
                    "total_amount": 0.0
                }

            products_summary[product_id]["quantity"] += item.quantity
            products_summary[product_id]["total_amount"] += float(item.quantity * item.price)

        # Сортируем по количеству (от большего к меньшему)
        sorted_products = sorted(
            products_summary.values(),
            key=lambda x: x["quantity"],
            reverse=True
        )

        return sorted_products

    def get_partners_statistics(self, admin_id, date=None, date_range=None, period=None):
        """Получение статистики по всем партнерам для администратора"""
        try:
            admin = User.objects.get(id=admin_id, role='admin')
        except User.DoesNotExist:
            return {"error": "Администратор не найден"}

        # Определяем даты для фильтрации
        today = timezone.now().date()

        if period:
            start_date, end_date = self._get_dates_from_period(period)
        elif date:
            start_date = end_date = date
        elif date_range:
            start_date, end_date = date_range
        else:
            # По умолчанию - текущая дата
            start_date = end_date = today

        # Получаем всех активных партнеров
        partners = User.objects.filter(role='partner', is_active=True, status='approved')

        # Собираем статистику по каждому партнеру
        partners_data = []

        partner_service = PartnerStatisticsService()

        for partner in partners:
            try:
                partner_stats = partner_service.get_partner_statistics(
                    partner_id=partner.id,
                    date=date,
                    date_range=date_range,
                    period=period
                )

                # Добавляем краткую информацию о партнере
                partner_summary = {
                    "partner_id": partner.id,
                    "partner_name": f"{partner.first_name} {partner.last_name}",
                    "requested_amount": partner_stats["requested"]["total_amount"],
                    "sold_amount": partner_stats["sold"]["total_amount"],
                    "expenses": partner_stats["expenses"],
                    "profit": partner_stats["profit"],
                    "remaining_items": partner_stats["remaining_items"]
                }

                partners_data.append(partner_summary)
            except Exception as e:
                print(f"Error getting statistics for partner {partner.id}: {str(e)}")

        # Рассчитываем общие показатели
        total_requested = sum(partner["requested_amount"] for partner in partners_data)
        total_sold = sum(partner["sold_amount"] for partner in partners_data)
        total_expenses = sum(partner["expenses"] for partner in partners_data)
        total_profit = sum(partner["profit"] for partner in partners_data)

        # Формируем итоговый ответ
        result = {
            "date_range": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "formatted": start_date.strftime("%d.%m.%Y") if start_date == end_date else
                f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"
            },
            "total": {
                "partners_count": len(partners_data),
                "requested_amount": total_requested,
                "sold_amount": total_sold,
                "expenses": total_expenses,
                "profit": total_profit
            },
            "partners": partners_data
        }

        return result