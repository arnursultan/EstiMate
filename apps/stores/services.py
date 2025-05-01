# apps/stores/services.py
from django.db.models import Sum, Count, Q, F, ExpressionWrapper, DecimalField
from django.utils import timezone
from datetime import datetime, timedelta

from .models import Store, StoreDebt, StoreDebtPayment
from apps.orders.models import Order, OrderItem, DefectItem


class StoreStatisticsService:
    def get_store_statistics(self, store_id=None, date=None, date_range=None, city=None):
        """
        Получение статистики по магазину или группе магазинов

        Параметры:
        - store_id: ID конкретного магазина (опционально)
        - date: Конкретная дата (опционально)
        - date_range: Диапазон дат (опционально) - tuple (start_date, end_date)
        - city: ID города для фильтрации (опционально)
        """
        # Определяем фильтры запроса
        filters = {}

        if store_id:
            filters['id'] = store_id

        if city:
            filters['city_id'] = city

        # Получаем все магазины согласно фильтрам
        stores = Store.objects.filter(**filters)

        # Определяем временные рамки
        if date:
            start_date = date
            end_date = date
        elif date_range:
            start_date, end_date = date_range
        else:
            # По умолчанию - сегодня
            start_date = end_date = timezone.now().date()

        # Если запрос для конкретного магазина
        if store_id:
            store = stores.first()
            if not store:
                return {}  # Если магазин не найден, возвращаем пустой словарь
            return self._get_single_store_statistics(store, start_date, end_date)

        # Если запрос для группы магазинов
        return self._get_multiple_stores_statistics(stores, start_date, end_date)

    def _get_single_store_statistics(self, store, start_date, end_date):
        """Статистика для одного магазина"""
        # Корректируем фильтры для заданного периода
        date_filter = {
            'created_at__date__gte': start_date,
            'created_at__date__lte': end_date
        }

        # Получаем ВСЕ заказы магазина за период, независимо от статуса
        orders = Order.objects.filter(
            store=store,
            order_type='partner_to_store',
            **date_filter
        )

        # Получаем элементы заказов
        order_items = OrderItem.objects.filter(order__in=orders)

        # Создаем аннотацию для общей стоимости позиции
        order_items = order_items.annotate(
            item_total_price=ExpressionWrapper(
                F('quantity') * F('price'),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )

        # Получаем бракованные товары
        defects = DefectItem.objects.filter(order__in=orders)

        # Получаем долги магазина
        all_debts = StoreDebt.objects.filter(store=store)
        period_debts = all_debts.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )

        # Получаем платежи по долгам магазина
        all_payments = StoreDebtPayment.objects.filter(store=store)
        period_payments = all_payments.filter(
            payment_date__date__gte=start_date,
            payment_date__date__lte=end_date
        )

        # Получаем расходы магазина
        all_expenses = StoreExpense.objects.filter(store=store)
        period_expenses = all_expenses.filter(
            expense_date__gte=start_date,
            expense_date__lte=end_date
        )

        # Рассчитываем статистику заказов
        total_ordered_items = order_items.aggregate(
            total_quantity=Sum('quantity'),
            total_price=Sum('item_total_price'),
            total_bonus=Sum('bonus_quantity')
        )

        # Рассчитываем общую стоимость брака
        defects = defects.annotate(
            defect_total_price=ExpressionWrapper(
                F('quantity') * F('product__price'),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )

        total_defects = defects.aggregate(
            total_quantity=Sum('quantity'),
            total_price=Sum('defect_total_price')
        )

        # Финансовые показатели
        total_debt = all_debts.aggregate(total=Sum('amount'))['total'] or 0
        total_paid = all_payments.aggregate(total=Sum('amount'))['total'] or 0
        remaining_debt = total_debt - total_paid

        period_debt = period_debts.aggregate(total=Sum('amount'))['total'] or 0
        period_paid = period_payments.aggregate(total=Sum('amount'))['total'] or 0
        period_expense = period_expenses.aggregate(total=Sum('amount'))['total'] or 0

        # Прибыль = оплаченный долг - расходы
        profit = period_paid - period_expense

        # Собираем информацию о товарах в заказах
        products_data = []
        product_summary = {}

        for item in order_items:
            product_id = item.product_id
            product_name = item.product.name

            if product_id not in product_summary:
                product_summary[product_id] = {
                    'product_id': product_id,
                    'product_name': product_name,
                    'quantity': 0,
                    'bonus_quantity': 0,
                    'total_price': 0.0
                }

            product_summary[product_id]['quantity'] += item.quantity
            product_summary[product_id]['bonus_quantity'] += (item.bonus_quantity or 0)
            product_summary[product_id]['total_price'] += float(item.price * item.quantity)

        # Преобразуем словарь в список для вывода
        products_data = list(product_summary.values())

        # Формируем итоговую статистику
        return {
            'store_id': store.id,
            'store_name': store.name,
            'date_range': {
                'start_date': start_date.isoformat() if hasattr(start_date, 'isoformat') else start_date,
                'end_date': end_date.isoformat() if hasattr(end_date, 'isoformat') else end_date,
            },
            'orders_count': orders.count(),  # Общее количество заказов
            'total_ordered_quantity': total_ordered_items.get('total_quantity') or 0,
            'total_ordered_price': float(total_ordered_items.get('total_price') or 0),  # Должно быть равно total_debt

            # Бонусы и бракованные товары
            'total_bonus_quantity': total_ordered_items.get('total_bonus') or 0,
            'total_defect_quantity': total_defects.get('total_quantity') or 0,
            'total_defect_price': float(total_defects.get('total_price') or 0),

            # Долги
            'total_debt': float(total_debt),
            'total_paid_debt': float(total_paid),
            'remaining_debt': float(remaining_debt),

            # За период
            'period_debt': float(period_debt),
            'period_paid': float(period_paid),
            'period_expenses': float(period_expense),  # Расходы за период

            # Прибыль и товары
            'profit': float(profit),  # Прибыль = оплаченный долг - расходы
            'products': products_data
        }

    def _get_multiple_stores_statistics(self, stores, start_date, end_date):
        """Агрегированная статистика для нескольких магазинов"""
        # Получаем ID всех магазинов
        store_ids = stores.values_list('id', flat=True)

        # Фильтр для заданного периода
        date_filter = {
            'created_at__date__gte': start_date,
            'created_at__date__lte': end_date
        }

        # Получаем заказы магазинов за период
        orders = Order.objects.filter(
            store_id__in=store_ids,
            order_type='partner_to_store',
            status='confirmed',
            **date_filter
        )

        # Получаем элементы заказов
        order_items = OrderItem.objects.filter(order__in=orders)

        # Создаем аннотацию для общей стоимости позиции
        order_items = order_items.annotate(
            item_total_price=ExpressionWrapper(
                F('quantity') * F('price'),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )

        # Получаем бракованные товары и аннотируем их стоимостью
        defects = DefectItem.objects.filter(order__in=orders)
        defects = defects.annotate(
            defect_total_price=ExpressionWrapper(
                F('quantity') * F('product__price'),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )

        # Получаем долги и платежи
        debts = StoreDebt.objects.filter(
            store_id__in=store_ids,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )

        payments = StoreDebtPayment.objects.filter(
            store_id__in=store_ids,
            payment_date__date__gte=start_date,
            payment_date__date__lte=end_date
        )

        # Получаем расходы
        expenses = StoreExpense.objects.filter(
            store_id__in=store_ids,
            expense_date__gte=start_date,
            expense_date__lte=end_date
        )

        # Рассчитываем статистику
        total_ordered_items = order_items.aggregate(
            total_quantity=Sum('quantity'),
            total_price=Sum('item_total_price'),
            total_bonus=Sum('bonus_quantity')
        )

        total_defects = defects.aggregate(
            total_quantity=Sum('quantity'),
            total_price=Sum('defect_total_price')
        )

        # Общий долг всех магазинов
        total_debt = StoreDebt.objects.filter(store_id__in=store_ids).aggregate(
            total=Sum('amount')
        )['total'] or 0

        # Общая сумма оплат
        total_paid = StoreDebtPayment.objects.filter(store_id__in=store_ids).aggregate(
            total=Sum('amount')
        )['total'] or 0

        # Долг за указанный период
        period_debt = debts.aggregate(total=Sum('amount'))['total'] or 0

        # Оплаты за указанный период
        period_paid = payments.aggregate(total=Sum('amount'))['total'] or 0

        # Расходы за указанный период
        period_expenses = expenses.aggregate(total=Sum('amount'))['total'] or 0

        # Группировка заказов по магазинам
        stores_summary = []
        for store in stores:
            store_orders = orders.filter(store=store)
            store_items = order_items.filter(order__in=store_orders)

            store_ordered = store_items.aggregate(
                total_quantity=Sum('quantity'),
                total_price=Sum('item_total_price')
            )

            stores_summary.append({
                'store_id': store.id,
                'store_name': store.name,
                'orders_count': store_orders.count(),
                'total_quantity': store_ordered.get('total_quantity') or 0,
                'total_price': float(store_ordered.get('total_price') or 0),
                'remaining_debt': float(store.remaining_debt)
            })

        # Формируем итоговую статистику
        return {
            'date_range': {
                'start_date': start_date.isoformat() if hasattr(start_date, 'isoformat') else start_date,
                'end_date': end_date.isoformat() if hasattr(end_date, 'isoformat') else end_date,
            },
            'stores_count': stores.count(),
            'orders_count': orders.count(),
            'total_ordered_quantity': total_ordered_items.get('total_quantity') or 0,
            'total_ordered_price': float(total_ordered_items.get('total_price') or 0),
            'total_bonus_quantity': total_ordered_items.get('total_bonus') or 0,
            'total_defect_quantity': total_defects.get('total_quantity') or 0,
            'total_defect_price': float(total_defects.get('total_price') or 0),
            'total_debt': float(total_debt),
            'total_paid_debt': float(total_paid),
            'remaining_debt': float(total_debt - total_paid),
            'period_debt': float(period_debt),
            'period_paid': float(period_paid),
            'period_expenses': float(period_expenses),
            'profit': float(period_paid - period_expenses),
            'stores': stores_summary
        }