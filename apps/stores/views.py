from django.db import transaction
from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Sum, Q
from .models import City, Store, StoreDebt, StoreDebtPayment, StoreExpense
from .serializers import (
    CitySerializer,
    StoreSerializer,
    StoreDebtSerializer,
    StoreListSerializer
)
from datetime import  datetime, timedelta
from apps.products.permissions import IsAdminUser, IsPartnerUser, IsOwnerOrAdmin
from apps.orders.serializers import StoreDebtPaymentSerializer, StoreExpenseSerializer
from rest_framework.views import APIView
from django.core.cache import cache
from rest_framework.response import Response


class CityViewSet(viewsets.ModelViewSet):
    """
    Представление для работы с городами
    """
    queryset = City.objects.all()
    serializer_class = CitySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [permissions.IsAuthenticated()]


class StoreViewSet(viewsets.ModelViewSet):
    """
    Представление для работы с магазинами
    """
    serializer_class = StoreSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['city', 'status']
    search_fields = ['name', 'inn', 'address']
    ordering_fields = ['name', 'created_at']

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return Store.objects.all()
        return Store.objects.filter(partner=user)

    def get_serializer_class(self):
        if self.action == 'list':
            return StoreListSerializer
        return StoreSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.IsAuthenticated()]
        elif self.action in ['update', 'partial_update', 'destroy']:
            return [IsOwnerOrAdmin()]
        return [permissions.IsAuthenticated()]

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Одобрение заявки на создание магазина"""
        store = self.get_object()

        if not request.user.role == 'admin':
            return Response(
                {"detail": "Только администратор может одобрять заявки на создание магазина"},
                status=status.HTTP_403_FORBIDDEN
            )

        if store.status == 'approved':
            return Response(
                {"detail": "Магазин уже одобрен"},
                status=status.HTTP_400_BAD_REQUEST
            )

        store.status = 'approved'
        store.save()

        return Response(
            {"detail": "Магазин успешно одобрен"},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Отклонение заявки на создание магазина"""
        store = self.get_object()

        if not request.user.role == 'admin':
            return Response(
                {"detail": "Только администратор может отклонять заявки на создание магазина"},
                status=status.HTTP_403_FORBIDDEN
            )

        if store.status == 'rejected':
            return Response(
                {"detail": "Магазин уже отклонен"},
                status=status.HTTP_400_BAD_REQUEST
            )

        store.status = 'rejected'
        store.save()

        return Response(
            {"detail": "Магазин успешно отклонен"},
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Получение списка ожидающих одобрения магазинов"""
        if request.user.role != 'admin':
            return Response(
                {"detail": "У вас нет прав для выполнения этого действия"},
                status=status.HTTP_403_FORBIDDEN
            )

        pending_stores = Store.objects.filter(status='pending')
        serializer = StoreListSerializer(pending_stores, many=True, context={'request': request})

        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def with_debt(self, request):
        """Получение списка магазинов с долгами"""
        queryset = self.get_queryset()
        stores_with_debt = []

        for store in queryset:
            if store.remaining_debt > 0:
                stores_with_debt.append(store)

        serializer = StoreListSerializer(stores_with_debt, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def financial_summary(self, request, pk=None):
        """
        Получение финансовой сводки по магазину с возможностью фильтрации по датам

        Параметры запроса:
        - date: конкретная дата (формат YYYY-MM-DD)
        - start_date: начальная дата диапазона (формат YYYY-MM-DD)
        - end_date: конечная дата диапазона (формат YYYY-MM-DD)
        - period: период ('today', 'yesterday', 'this_week', 'last_week', 'this_month',
                  'last_month', 'this_quarter', 'last_quarter', 'this_year', 'last_year')
        """
        from datetime import datetime, timedelta
        from apps.orders.models import Order, OrderItem, DefectItem

        store = self.get_object()

        # Получаем город для отображения в информации
        city_name = store.city.name if store.city else ""

        # Получаем параметры даты из запроса
        date_str = request.query_params.get('date')
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        period = request.query_params.get('period')

        # Текущая дата для относительных расчетов
        today = timezone.now().date()

        # Обработка периодов (новый функционал)
        if period:
            if period == 'today':
                start_date = end_date = today
            elif period == 'yesterday':
                start_date = end_date = today - timedelta(days=1)
            elif period == 'this_week':
                # Начало текущей недели (понедельник)
                start_date = today - timedelta(days=today.weekday())
                end_date = today
            elif period == 'last_week':
                # Начало прошлой недели (понедельник)
                start_date = today - timedelta(days=today.weekday() + 7)
                # Конец прошлой недели (воскресенье)
                end_date = start_date + timedelta(days=6)
            elif period == 'this_month':
                # Начало текущего месяца
                start_date = today.replace(day=1)
                end_date = today
            elif period == 'last_month':
                # Начало прошлого месяца
                if today.month == 1:
                    start_date = today.replace(year=today.year - 1, month=12, day=1)
                else:
                    start_date = today.replace(month=today.month - 1, day=1)
                # Конец прошлого месяца
                end_date = today.replace(day=1) - timedelta(days=1)
            elif period == 'this_quarter':
                # Определение текущего квартала
                quarter = (today.month - 1) // 3 + 1
                # Начало текущего квартала
                start_date = today.replace(month=3 * quarter - 2, day=1)
                end_date = today
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
            elif period == 'this_year':
                # Начало текущего года
                start_date = today.replace(month=1, day=1)
                end_date = today
            elif period == 'last_year':
                # Прошлый год
                start_date = today.replace(year=today.year - 1, month=1, day=1)
                end_date = today.replace(year=today.year - 1, month=12, day=31)
            else:
                return Response(
                    {
                        "detail": "Неизвестный параметр period. Допустимые значения: today, yesterday, this_week, last_week, this_month, last_month, this_quarter, last_quarter, this_year, last_year"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        # Обработка конкретной даты
        elif date_str:
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
                start_date = end_date = date
            except ValueError:
                return Response(
                    {"detail": "Неверный формат даты. Используйте YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        # Обработка диапазона дат
        elif start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                if start_date > end_date:
                    return Response(
                        {"detail": "Начальная дата не может быть позже конечной даты"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except ValueError:
                return Response(
                    {"detail": "Неверный формат даты. Используйте YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        # По умолчанию - текущая дата
        else:
            start_date = end_date = today

        # Получаем все заказы магазина, не только за период
        all_orders = Order.objects.filter(store=store)
        period_orders = Order.objects.filter(
            store=store,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )

        # Получаем элементы заказов
        all_order_items = OrderItem.objects.filter(order__in=all_orders)
        period_order_items = OrderItem.objects.filter(order__in=period_orders)

        # Получаем все долги и платежи
        all_debts = StoreDebt.objects.filter(store=store)
        period_debts = StoreDebt.objects.filter(
            store=store,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )

        all_payments = StoreDebtPayment.objects.filter(store=store)
        period_payments = StoreDebtPayment.objects.filter(
            store=store,
            payment_date__date__gte=start_date,
            payment_date__date__lte=end_date
        )

        # Получаем расходы
        all_expenses = StoreExpense.objects.filter(store=store)
        period_expenses = StoreExpense.objects.filter(
            store=store,
            expense_date__gte=start_date,
            expense_date__lte=end_date
        )

        # Получаем бракованные товары
        all_defects = DefectItem.objects.filter(order__store=store)
        period_defects = DefectItem.objects.filter(order__in=period_orders)

        # Вычисляем суммы
        total_debt = sum(debt.amount for debt in all_debts)
        period_debt = sum(debt.amount for debt in period_debts)

        total_paid = sum(payment.amount for payment in all_payments)
        period_paid = sum(payment.amount for payment in period_payments)

        total_expenses = sum(expense.amount for expense in all_expenses)
        period_expenses_sum = sum(expense.amount for expense in period_expenses)

        # Количество товаров и бонусов
        total_ordered = sum(item.quantity for item in all_order_items)
        period_ordered = sum(item.quantity for item in period_order_items)

        total_bonus = sum(item.bonus_quantity or 0 for item in all_order_items)
        period_bonus = sum(item.bonus_quantity or 0 for item in period_order_items)

        total_defect_quantity = sum(defect.quantity for defect in all_defects)
        period_defect_quantity = sum(defect.quantity for defect in period_defects)

        # Рассчитываем прибыль и баланс
        remaining_debt = total_debt - total_paid
        profit = period_paid - period_expenses_sum
        total_balance = total_paid - total_expenses

        # Группировка товаров для отображения
        products_summary = []

        # Сначала получаем все уникальные продукты
        product_ids = set(item.product_id for item in period_order_items)

        for product_id in product_ids:
            items = period_order_items.filter(product_id=product_id)
            if items:
                product = items[0].product
                quantity = sum(item.quantity for item in items)

                products_summary.append({
                    "product_id": product_id,
                    "product_name": product.name,
                    "quantity": quantity,
                    "price": float(product.price),
                    "total_price": float(product.price * quantity)
                })

        # Определяем тип примененного фильтра для отображения
        filter_type = "default"
        if period:
            filter_type = f"period:{period}"
        elif date_str:
            filter_type = "specific_date"
        elif start_date_str and end_date_str:
            filter_type = "date_range"

        return Response({
            "id": store.id,
            "store_id": store.id,
            "store_name": store.name,
            "city": {
                "id": store.city.id if store.city else None,
                "name": city_name
            },
            "date": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "formatted": start_date.strftime("%d.%m.%Y") if start_date == end_date else
                f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}",
                "filter_type": filter_type
            },
            "orders_count": period_orders.count(),
            "total_ordered_quantity": period_ordered,

            # Финансовые показатели
            "debt": float(total_debt),
            "pay_debt": float(total_paid),
            "remaining_debt": float(remaining_debt),

            # Данные за период
            "period_debt": float(period_debt),
            "period_paid": float(period_paid),

            # Расходы и прибыль
            "expenses": float(total_expenses),
            "period_expenses": float(period_expenses_sum),

            # Бонусы и брак
            "bonus_quantity": total_bonus,
            "defect_quantity": total_defect_quantity,

            # Финансовые показатели
            "profit": float(profit),
            "total_balance": float(total_balance),

            # Товары в заказах
            "products": products_summary
        })

    @action(detail=False, methods=['get'])
    def stores_summary(self, request):
        """
        Получение статистики по всем магазинам (для администраторов и партнеров)
        с возможностью фильтрации по датам и городам

        Параметры запроса:
        - date: конкретная дата (формат YYYY-MM-DD)
        - start_date: начальная дата диапазона (формат YYYY-MM-DD)
        - end_date: конечная дата диапазона (формат YYYY-MM-DD)
        - period: период ('today', 'yesterday', 'this_week', 'last_week', 'this_month',
                  'last_month', 'this_quarter', 'last_quarter', 'this_year', 'last_year')
        - city_id: идентификатор города для фильтрации
        """
        from datetime import datetime, timedelta
        from apps.orders.models import Order, OrderItem, DefectItem
        from .models import City

        user = request.user

        # Получаем параметры из запроса
        date_str = request.query_params.get('date')
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        period = request.query_params.get('period')
        city_id = request.query_params.get('city_id')

        # Текущая дата для относительных расчетов
        today = timezone.now().date()

        # Обработка периодов
        if period:
            if period == 'today':
                start_date = end_date = today
            elif period == 'yesterday':
                start_date = end_date = today - timedelta(days=1)
            elif period == 'this_week':
                # Начало текущей недели (понедельник)
                start_date = today - timedelta(days=today.weekday())
                end_date = today
            elif period == 'last_week':
                # Начало прошлой недели (понедельник)
                start_date = today - timedelta(days=today.weekday() + 7)
                # Конец прошлой недели (воскресенье)
                end_date = start_date + timedelta(days=6)
            elif period == 'this_month':
                # Начало текущего месяца
                start_date = today.replace(day=1)
                end_date = today
            elif period == 'last_month':
                # Начало прошлого месяца
                if today.month == 1:
                    start_date = today.replace(year=today.year - 1, month=12, day=1)
                else:
                    start_date = today.replace(month=today.month - 1, day=1)
                # Конец прошлого месяца
                end_date = today.replace(day=1) - timedelta(days=1)
            elif period == 'this_quarter':
                # Определение текущего квартала
                quarter = (today.month - 1) // 3 + 1
                # Начало текущего квартала
                start_date = today.replace(month=3 * quarter - 2, day=1)
                end_date = today
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
            elif period == 'this_year':
                # Начало текущего года
                start_date = today.replace(month=1, day=1)
                end_date = today
            elif period == 'last_year':
                # Прошлый год
                start_date = today.replace(year=today.year - 1, month=1, day=1)
                end_date = today.replace(year=today.year - 1, month=12, day=31)
            else:
                return Response(
                    {
                        "detail": "Неизвестный параметр period. Допустимые значения: today, yesterday, this_week, last_week, this_month, last_month, this_quarter, last_quarter, this_year, last_year"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        # Обработка конкретной даты
        elif date_str:
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
                start_date = end_date = date
            except ValueError:
                return Response(
                    {"detail": "Неверный формат даты. Используйте YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        # Обработка диапазона дат
        elif start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                if start_date > end_date:
                    return Response(
                        {"detail": "Начальная дата не может быть позже конечной даты"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except ValueError:
                return Response(
                    {"detail": "Неверный формат даты. Используйте YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        # По умолчанию - текущая дата
        else:
            start_date = end_date = today

        # Получаем магазины с фильтрацией по правам доступа и городу
        if user.role == 'admin':
            stores_queryset = Store.objects.all()
        else:
            # Партнеры видят только свои магазины
            stores_queryset = Store.objects.filter(partner=user)

        # Фильтруем по городу, если указан
        if city_id:
            stores_queryset = stores_queryset.filter(city_id=city_id)

        # Фильтруем только одобренные магазины
        stores_queryset = stores_queryset.filter(status='approved')

        # Сначала получим все города для возможности выбора пользователем
        all_cities = City.objects.all()
        cities_data = [{"id": city.id, "name": city.name} for city in all_cities]

        # Получаем все нужные данные для выбранных магазинов
        # Получаем все нужные данные для выбранных магазинов
        stores_data = []
        total_stats = {
            "orders_count": 0,
            "total_ordered_quantity": 0,
            "total_debt": 0.0,  # Явно указываем float
            "total_paid": 0.0,  # Явно указываем float
            "expenses": 0.0,  # Явно указываем float
            "bonus_quantity": 0,
            "defect_quantity": 0,
            "profit": 0.0  # Явно указываем float
        }

        # Список уникальных городов в результатах
        result_cities = set()

        # Идем по каждому магазину и собираем статистику
        for store in stores_queryset:
            # Получаем заказы магазина за период
            orders = Order.objects.filter(
                store=store,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date
            )

            # Получаем элементы заказов
            order_items = OrderItem.objects.filter(order__in=orders)

            # Получаем долги и платежи за период
            debts = StoreDebt.objects.filter(
                store=store,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date
            )

            payments = StoreDebtPayment.objects.filter(
                store=store,
                payment_date__date__gte=start_date,
                payment_date__date__lte=end_date
            )

            # Получаем расходы за период
            expenses = StoreExpense.objects.filter(
                store=store,
                expense_date__gte=start_date,
                expense_date__lte=end_date
            )

            # Получаем бракованные товары за период
            defects = DefectItem.objects.filter(order__in=orders)

            # Рассчитываем показатели
            # Рассчитываем показатели
            store_orders_count = orders.count()
            store_ordered_quantity = sum(item.quantity for item in order_items)
            store_debt = float(sum(debt.amount for debt in debts))  # Преобразуем в float
            store_paid = float(sum(payment.amount for payment in payments))  # Преобразуем в float
            store_expenses = float(sum(expense.amount for expense in expenses))  # Преобразуем в float
            store_bonus = sum(item.bonus_quantity or 0 for item in order_items)
            store_defects = sum(defect.quantity for defect in defects)
            store_profit = store_paid - store_expenses

            # Добавляем в общую статистику
            total_stats["orders_count"] += store_orders_count
            total_stats["total_ordered_quantity"] += store_ordered_quantity
            total_stats["total_debt"] += store_debt  # Теперь складываем float с float
            total_stats["total_paid"] += store_paid  # Теперь складываем float с float
            total_stats["expenses"] += store_expenses  # Теперь складываем float с float
            total_stats["bonus_quantity"] += store_bonus
            total_stats["defect_quantity"] += store_defects
            total_stats["profit"] += store_profit

            # Добавляем город в список уникальных городов
            if store.city:
                result_cities.add(store.city.name)

            # Добавляем данные магазина
            store_data = {
                "id": store.id,
                "name": store.name,
                "city": store.city.name if store.city else "",
                "address": store.address,
                "orders_count": store_orders_count,
                "total_ordered_quantity": store_ordered_quantity,
                "debt": float(store_debt),
                "paid": float(store_paid),
                "expenses": float(store_expenses),
                "bonus_quantity": store_bonus,
                "defect_quantity": store_defects,
                "profit": float(store_profit)
            }
            stores_data.append(store_data)

        # Формируем итоговый ответ
        result = {
            "date_range": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "formatted": start_date.strftime("%d.%m.%Y") if start_date == end_date else
                f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"
            },
            "filters": {
                "city_id": city_id,
                "all_cities": cities_data,  # Все доступные города
                "result_cities": list(result_cities)  # Города в результатах
            },
            "total": {
                "stores_count": stores_queryset.count(),
                "orders_count": total_stats["orders_count"],
                "total_ordered_quantity": total_stats["total_ordered_quantity"],
                "total_debt": float(total_stats["total_debt"]),
                "total_paid": float(total_stats["total_paid"]),
                "expenses": float(total_stats["expenses"]),
                "bonus_quantity": total_stats["bonus_quantity"],
                "defect_quantity": total_stats["defect_quantity"],
                "profit": float(total_stats["profit"])
            },
            "stores": stores_data
        }

        return Response(result)

    @action(detail=False, methods=['get'])
    def city_summary(self, request):
        """
        Получение статистики по всем магазинам в конкретном городе

        Параметры запроса:
        - city_id: идентификатор города (обязательный)
        - date/start_date/end_date/period: параметры для фильтрации по датам (как в других методах)
        """
        city_id = request.query_params.get('city_id')
        if not city_id:
            return Response(
                {"detail": "Параметр city_id обязателен"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            city = City.objects.get(id=city_id)
        except City.DoesNotExist:
            return Response(
                {"detail": "Город не найден"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Устанавливаем параметр city_id в request.query_params для использования в stores_summary
        request.query_params._mutable = True
        request.query_params['city_id'] = city_id
        request.query_params._mutable = False

        # Используем тот же метод stores_summary с установленным параметром city_id
        response = self.stores_summary(request)

        # Добавляем информацию о городе в ответ
        response.data['city'] = {
            'id': city.id,
            'name': city.name
        }

        return response

    @action(detail=True, methods=['post'])
    def add_expense(self, request, pk=None):
        """Добавление расхода для магазина"""
        # Используем select_related для снижения количества запросов
        try:
            store = Store.objects.select_related('partner', 'city').get(pk=pk)

            # Проверяем, что пользователь имеет доступ к магазину
            user = request.user
            if user.role != 'admin' and store.partner != user:
                return Response(
                    {"detail": "У вас нет доступа к этому магазину"},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Оптимизированное создание
            with transaction.atomic():
                serializer = StoreExpenseSerializer(
                    data={
                        "store": store.id,
                        "amount": request.data.get("amount"),
                        "description": request.data.get("description", ""),
                        "expense_date": request.data.get("expense_date", timezone.now().date().isoformat())
                    },
                    context={"request": request}
                )

                serializer.is_valid(raise_exception=True)
                expense = serializer.save()

            return Response(
                StoreExpenseSerializer(expense).data,
                status=status.HTTP_201_CREATED
            )
        except Store.DoesNotExist:
            return Response(
                {"detail": "Магазин не найден"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"detail": f"Ошибка при создании расхода: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    @action(detail=True, methods=['post'])
    def pay_debt(self, request, pk=None):
        """Частичная оплата долга магазина"""
        store = self.get_object()

        # Проверяем, что пользователь имеет доступ к магазину
        user = request.user
        if user.role != 'admin' and store.partner != user:
            return Response(
                {"detail": "У вас нет доступа к этому магазину"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Проверяем, что у магазина есть долг
        if store.remaining_debt <= 0:
            return Response(
                {"detail": "У магазина нет неоплаченного долга"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Создаем платеж
        serializer = StoreDebtPaymentSerializer(
            data={
                "store": store.id,
                "amount": request.data.get("amount"),
                "description": request.data.get("description", "Частичная оплата долга")
            },
            context={"request": request}
        )

        serializer.is_valid(raise_exception=True)
        payment = serializer.save()

        # Если долг полностью погашен, отмечаем все долги как оплаченные
        if store.remaining_debt <= 0:
            store.debts.filter(is_paid=False).update(is_paid=True)

        return Response(
            StoreDebtPaymentSerializer(payment).data,
            status=status.HTTP_201_CREATED
        )


class StoreDebtViewSet(viewsets.ModelViewSet):
    """
    Представление для работы с долгами магазинов
    """
    serializer_class = StoreDebtSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['store', 'is_paid']
    ordering_fields = ['amount', 'created_at']

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return StoreDebt.objects.all()
        return StoreDebt.objects.filter(store__partner=user)

    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsOwnerOrAdmin()]
        return [permissions.IsAuthenticated()]

    @action(detail=True, methods=['post'])
    def mark_paid(self, request, pk=None):
        """Отметить долг как полностью оплаченный"""
        debt = self.get_object()

        # Проверка, что пользователь имеет доступ к долгу
        if request.user.role != 'admin' and debt.store.partner != request.user:
            return Response(
                {"detail": "У вас нет прав для выполнения этого действия"},
                status=status.HTTP_403_FORBIDDEN
            )

        if debt.is_paid:
            return Response(
                {"detail": "Долг уже оплачен"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Создаем платеж на полную сумму долга
        StoreDebtPayment.objects.create(
            store=debt.store,
            amount=debt.amount,
            description=f"Полная оплата долга (ID: {debt.id})"
        )

        # Отмечаем долг как оплаченный
        debt.is_paid = True
        debt.updated_at = timezone.now()
        debt.save()

        return Response(
            {"detail": "Долг успешно отмечен как оплаченный"},
            status=status.HTTP_200_OK
        )


    @action(detail=False, methods=['get'])
    def store_debts(self, request):
        """Получение всех долгов конкретного магазина"""
        store_id = request.query_params.get('store_id')
        if not store_id:
            return Response(
                {"detail": "Необходимо указать ID магазина"},
                status=status.HTTP_400_BAD_REQUEST
            )

        queryset = self.get_queryset().filter(store_id=store_id)

        # Фильтрация по статусу оплаты
        is_paid = request.query_params.get('is_paid')
        if is_paid is not None:
            is_paid_bool = is_paid.lower() == 'true'
            queryset = queryset.filter(is_paid=is_paid_bool)

        serializer = StoreDebtSerializer(queryset, many=True)

        # Рассчитываем общую сумму
        total_amount = sum(debt.amount for debt in queryset)

        return Response({
            "debts": serializer.data,
            "total_amount": total_amount,
            "count": queryset.count()
        })

    # В файле apps/stores/views.py добавим действия для активации/деактивации

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Активация магазина"""
        store = self.get_object()

        if not request.user.role == 'admin' and store.partner != request.user:
            return Response(
                {"detail": "У вас нет прав для активации этого магазина"},
                status=status.HTTP_403_FORBIDDEN
            )

        if store.is_active:
            return Response(
                {"detail": "Магазин уже активен"},
                status=status.HTTP_400_BAD_REQUEST
            )

        store.is_active = True
        store.save()

        return Response(
            {"detail": "Магазин успешно активирован"},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Деактивация магазина"""
        store = self.get_object()

        if not request.user.role == 'admin' and store.partner != request.user:
            return Response(
                {"detail": "У вас нет прав для деактивации этого магазина"},
                status=status.HTTP_403_FORBIDDEN
            )

        if not store.is_active:
            return Response(
                {"detail": "Магазин уже деактивирован"},
                status=status.HTTP_400_BAD_REQUEST
            )

        store.is_active = False
        store.save()

        return Response(
            {"detail": "Магазин успешно деактивирован"},
            status=status.HTTP_200_OK
        )





