from django_filters import rest_framework as filters
from datetime import datetime
from django.utils import timezone
from django.db.models import Q

from apps.users.models import User
from apps.stores.models import Store, StoreDebt, StoreDebtPayment, StoreExpense
from apps.orders.models import Order, OrderItem, DefectItem
from .models import FinanceEntry, ManualFinanceEntry


class DateRangeFilterMixin:
    """Миксин для фильтрации по диапазону дат"""

    def parse_date_params(self, date_str=None, start_date_str=None, end_date_str=None):
        """Разбор параметров даты"""
        date_obj = None
        start_date_obj = None
        end_date_obj = None
        error = None

        # Обработка одиночной даты
        if date_str:
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                error = "Некорректный формат даты. Используйте YYYY-MM-DD"
                return None, None, None, error

        # Обработка диапазона дат
        if start_date_str:
            try:
                start_date_obj = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except ValueError:
                error = "Некорректный формат начальной даты. Используйте YYYY-MM-DD"
                return None, None, None, error

        if end_date_str:
            try:
                end_date_obj = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                error = "Некорректный формат конечной даты. Используйте YYYY-MM-DD"
                return None, None, None, error

            # Проверка правильности диапазона
            if start_date_obj and end_date_obj and start_date_obj > end_date_obj:
                error = "Начальная дата не может быть позже конечной"
                return None, None, None, error

        # Если дата не указана, используем текущую
        if not date_obj and not start_date_obj and not end_date_obj:
            date_obj = timezone.now().date()

        return date_obj, start_date_obj, end_date_obj, error

    def get_date_filters(self, date_obj=None, start_date_obj=None, end_date_obj=None, field_prefix='created_at'):
        """Получение фильтров по дате"""
        date_filters = {}

        if date_obj:
            date_filters[f'{field_prefix}__date'] = date_obj
        elif start_date_obj and end_date_obj:
            date_filters[f'{field_prefix}__date__range'] = (start_date_obj, end_date_obj)

        return date_filters


class FinanceEntryFilter(filters.FilterSet):
    """Фильтр для финансовых записей"""
    date_from = filters.DateFilter(field_name='date', lookup_expr='gte')
    date_to = filters.DateFilter(field_name='date', lookup_expr='lte')
    entry_type = filters.CharFilter(field_name='entry_type')
    user = filters.NumberFilter(field_name='user__id')
    store = filters.NumberFilter(field_name='store__id')

    class Meta:
        model = FinanceEntry
        fields = ['date_from', 'date_to', 'entry_type', 'user', 'store']


class ManualFinanceEntryFilter(filters.FilterSet):
    """Фильтр для ручных финансовых записей"""
    date_from = filters.DateFilter(field_name='date', lookup_expr='gte')
    date_to = filters.DateFilter(field_name='date', lookup_expr='lte')
    entry_type = filters.CharFilter(field_name='entry_type')
    user = filters.NumberFilter(field_name='user__id')
    store = filters.NumberFilter(field_name='store__id')

    class Meta:
        model = ManualFinanceEntry
        fields = ['date_from', 'date_to', 'entry_type', 'user', 'store']


class OrderFilter(DateRangeFilterMixin):
    """Класс для фильтрации заказов"""

    def get_admin_to_partner_orders(self, user=None, partner_id=None, date_obj=None, start_date_obj=None, end_date_obj=None):
        """Получение заказов от админа к партнеру"""
        filters = {
            'order_type': 'admin_to_partner',
            'status': 'confirmed'
        }

        # Добавляем фильтр по партнеру
        if partner_id:
            filters['partner_id'] = partner_id

        # Добавляем фильтры по дате
        date_filters = self.get_date_filters(date_obj, start_date_obj, end_date_obj)
        filters.update(date_filters)

        # Если указан пользователь (партнер), фильтруем по нему
        if user and user.role == 'partner':
            filters['partner'] = user

        return Order.objects.filter(**filters)

    def get_partner_to_store_orders(self, user=None, store_id=None, city_id=None, date_obj=None, start_date_obj=None, end_date_obj=None):
        """Получение заказов от партнера к магазину"""
        filters = {
            'order_type': 'partner_to_store',
            'status': 'confirmed'
        }

        # Добавляем фильтр по магазину
        if store_id:
            filters['store_id'] = store_id

        # Добавляем фильтр по городу
        if city_id:
            filters['store__city_id'] = city_id

        # Добавляем фильтры по дате
        date_filters = self.get_date_filters(date_obj, start_date_obj, end_date_obj)
        filters.update(date_filters)

        # Если указан пользователь (партнер), фильтруем по нему
        if user and user.role == 'partner':
            filters['created_by'] = user

        return Order.objects.filter(**filters)

class StoreFilter:
    """Класс для фильтрации магазинов"""

    def get_filtered_stores(self, user=None, store_id=None, city_id=None, partner_id=None):
        """Получение фильтрованного списка магазинов"""
        filters = {}

        # Фильтр по ID магазина
        if store_id:
            filters['id'] = store_id

        # Фильтр по городу
        if city_id:
            filters['city_id'] = city_id

        # Фильтр по партнеру
        if partner_id:
            filters['partner_id'] = partner_id

        # Если пользователь - партнер, показываем только его магазины
        if user and user.role == 'partner':
            filters['partner'] = user

        return Store.objects.filter(**filters)


class DefectItemFilter(DateRangeFilterMixin):
    """Класс для фильтрации бракованных товаров"""

    def get_filtered_defects(self, user=None, store_id=None, date_obj=None, start_date_obj=None, end_date_obj=None):
        """Получение фильтрованного списка бракованных товаров"""
        filters = {}

        # Фильтр по магазину
        if store_id:
            filters['order__store_id'] = store_id

        # Добавляем фильтры по дате
        date_filters = self.get_date_filters(date_obj, start_date_obj, end_date_obj)
        filters.update(date_filters)

        # Если пользователь - партнер, показываем только его бракованные товары
        if user and user.role == 'partner':
            filters['order__created_by'] = user

        return DefectItem.objects.filter(**filters)


class ExpenseFilter(DateRangeFilterMixin):
    """Класс для фильтрации расходов"""

    def get_filtered_expenses(self, user=None, store_id=None, date_obj=None, start_date_obj=None, end_date_obj=None):
        """Получение фильтрованного списка расходов"""
        # Ручные финансовые записи (расходы пользователя)
        user_expense_filters = {
            'entry_type': 'expense'
        }

        # Добавляем фильтр по пользователю
        if user:
            user_expense_filters['user'] = user

        # Добавляем фильтры по дате для записей пользователя
        if date_obj:
            user_expense_filters['date'] = date_obj
        elif start_date_obj and end_date_obj:
            user_expense_filters['date__range'] = (start_date_obj, end_date_obj)

        user_expenses = ManualFinanceEntry.objects.filter(**user_expense_filters)

        # Расходы магазина
        store_expense_filters = {}

        # Фильтр по магазину
        if store_id:
            store_expense_filters['store_id'] = store_id
        elif user and user.role == 'partner':
            # Если пользователь - партнер, показываем расходы его магазинов
            store_expense_filters['store__partner'] = user

        # Добавляем фильтры по дате для расходов магазина
        if date_obj:
            store_expense_filters['expense_date'] = date_obj
        elif start_date_obj and end_date_obj:
            store_expense_filters['expense_date__range'] = (start_date_obj, end_date_obj)

        store_expenses = StoreExpense.objects.filter(**store_expense_filters)

        return user_expenses, store_expenses