from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Sum, F, Count, Prefetch
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

from .models import (
    PartnerFinanceEntry,
    StoreFinanceEntry,
    DailyStatistics,
    ProductDailyStatistics
)
from .serializers import (
    PartnerFinanceEntrySerializer,
    StoreFinanceEntrySerializer,
    DailyStatisticsSerializer,
    FinanceSummarySerializer,
    StoreFilterSerializer
)

from apps.users.models import User
from apps.stores.models import Store
from apps.products.models import Product, PartnerInventory
from apps.orders.models import Order, OrderItem, DefectItem
from apps.products.permissions import IsAdminUser, IsPartnerUser, IsOwnerOrAdmin


class FinanceEntryViewSet(viewsets.ModelViewSet):
    """Базовый класс для финансовых записей"""
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['entry_type', 'date']
    search_fields = ['description']
    ordering_fields = ['date', 'amount', 'created_at']
    ordering = ['-date', '-created_at']

    def get_permissions(self):
        if self.action in ['destroy', 'update', 'partial_update']:
            return [IsOwnerOrAdmin()]
        return [permissions.IsAuthenticated()]


class PartnerFinanceEntryViewSet(FinanceEntryViewSet):
    """Представление для финансовых записей партнера"""
    serializer_class = PartnerFinanceEntrySerializer

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return PartnerFinanceEntry.objects.all()
        # Партнеры видят только свои финансовые записи
        return PartnerFinanceEntry.objects.filter(partner=user)

    def perform_create(self, serializer):
        # Если партнер создает запись для себя
        if self.request.user.role == 'partner':
            serializer.save(partner=self.request.user)
        else:
            serializer.save()


class StoreFinanceEntryViewSet(FinanceEntryViewSet):
    """Представление для финансовых записей магазина"""
    serializer_class = StoreFinanceEntrySerializer

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return StoreFinanceEntry.objects.all()
        # Партнеры видят только финансовые записи своих магазинов
        return StoreFinanceEntry.objects.filter(store__partner=user)


class StatisticsViewSet(viewsets.ReadOnlyModelViewSet):
    """Представление для просмотра статистики"""
    serializer_class = DailyStatisticsSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['date', 'partner', 'store']
    ordering_fields = ['date']
    ordering = ['-date']

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return DailyStatistics.objects.all().prefetch_related('product_stats')
        # Партнеры видят только свою статистику и статистику своих магазинов
        return DailyStatistics.objects.filter(
            Q(partner=user) | Q(store__partner=user)
        ).prefetch_related('product_stats')

    @action(detail=False, methods=['get'])
    def partner_statistics(self, request):
        """Получение статистики партнера"""
        user = request.user

        # Получаем параметры фильтрации
        date_from_str = request.query_params.get('date_from')
        date_to_str = request.query_params.get('date_to')

        # Устанавливаем значения по умолчанию
        today = timezone.now().date()
        date_from = today
        date_to = today

        # Преобразуем строковые даты в объекты date
        if date_from_str:
            try:
                date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {"error": "Неверный формат даты. Используйте YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        if date_to_str:
            try:
                date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {"error": "Неверный формат даты. Используйте YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Проверяем, что пользователь - партнер или админ запрашивает данные партнера
        partner_id = request.query_params.get('partner_id')

        if partner_id and user.role == 'admin':
            try:
                partner = User.objects.get(id=partner_id, role='partner')
            except User.DoesNotExist:
                return Response(
                    {"error": "Партнер не найден"},
                    status=status.HTTP_404_NOT_FOUND
                )
        elif user.role == 'partner':
            partner = user
        else:
            return Response(
                {"error": "Недостаточно прав для просмотра статистики партнера"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Получаем статистику из базы данных
        statistics = DailyStatistics.objects.filter(
            partner=partner,
            date__range=(date_from, date_to)
        ).prefetch_related('product_stats')

        # Если статистики нет, то рассчитываем её на лету
        if not statistics.exists():
            # Запрашиваем недостающие данные
            # 1. Запрошенные товары
            requested_items = OrderItem.objects.filter(
                order__partner=partner,
                order__order_type='admin_to_partner',
                order__created_at__date__range=(date_from, date_to)
            ).values('product_id', 'product__name').annotate(
                total_quantity=Sum('quantity'),
                total_amount=Sum(F('quantity') * F('price'))
            )

            # 2. Проданные товары
            sold_items = OrderItem.objects.filter(
                order__created_by=partner,
                order__order_type='partner_to_store',
                order__created_at__date__range=(date_from, date_to)
            ).values('product_id', 'product__name').annotate(
                total_quantity=Sum('quantity'),
                total_amount=Sum(F('quantity') * F('price'))
            )

            # 3. Расходы
            expenses = StoreFinanceEntry.objects.filter(
                store__partner=partner,
                entry_type='expense',
                date__range=(date_from, date_to)
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

            # 4. Бракованные товары
            defect_items = DefectItem.objects.filter(
                order__created_by=partner,
                order__created_at__date__range=(date_from, date_to)
            ).values('product_id', 'product__name').annotate(
                total_quantity=Sum('quantity')
            )

            # 5. Остаток товаров
            inventory_items = PartnerInventory.objects.filter(
                partner=partner
            ).values('product_id', 'product__name', 'quantity')

            # 6. Бонусные товары
            bonus_items = OrderItem.objects.filter(
                order__created_by=partner,
                order__created_at__date__range=(date_from, date_to)
            ).aggregate(total_bonus=Sum('bonus_quantity'))['total_bonus'] or 0

            # Считаем итоговые показатели
            total_requested = sum(item['total_amount'] for item in requested_items)
            total_sold = sum(item['total_amount'] for item in sold_items)
            total_profit = total_sold - expenses

            # Формируем список товаров для статистики
            product_stats = []

            # Добавляем запрошенные товары
            for item in requested_items:
                product_stats.append({
                    'product_id': item['product_id'],
                    'product_name': item['product__name'],
                    'requested_quantity': item['total_quantity'],
                    'income_amount': item['total_amount']
                })

            # Возвращаем результат
            return Response({
                'date_from': date_from,
                'date_to': date_to,
                'partner_id': partner.id,
                'partner_name': f"{partner.first_name} {partner.last_name}",
                'total_requested': total_requested,
                'total_sold': total_sold,
                'total_expenses': expenses,
                'total_defect_items': sum(item['total_quantity'] for item in defect_items),
                'total_remaining_items': sum(item['quantity'] for item in inventory_items),
                'total_bonus_items': bonus_items,
                'total_profit': total_profit,
                'product_summaries': product_stats
            })

        # Если статистика уже есть, то возвращаем её
        serializer = FinanceSummarySerializer({
            'date_from': date_from,
            'date_to': date_to,
            'total_income': statistics.aggregate(sum=Sum('total_income'))['sum'] or Decimal('0.00'),
            'total_expense': statistics.aggregate(sum=Sum('total_expense'))['sum'] or Decimal('0.00'),
            'total_debt': statistics.aggregate(sum=Sum('total_debt'))['sum'] or Decimal('0.00'),
            'total_debt_paid': statistics.aggregate(sum=Sum('total_debt_paid'))['sum'] or Decimal('0.00'),
            'total_bonus_items': statistics.aggregate(sum=Sum('total_bonus_items'))['sum'] or 0,
            'total_defect_items': statistics.aggregate(sum=Sum('total_defect_items'))['sum'] or 0,
            'total_balance': statistics.aggregate(sum=Sum('total_balance'))['sum'] or Decimal('0.00'),
            'product_summaries': [
                {
                    'product_id': ps.product_id,
                    'product_name': ps.product_name,
                    'requested_quantity': ps.requested_quantity,
                    'sold_quantity': ps.sold_quantity,
                    'bonus_quantity': ps.bonus_quantity,
                    'defect_quantity': ps.defect_quantity,
                    'remaining_quantity': ps.remaining_quantity,
                    'income_amount': ps.income_amount
                }
                for stat in statistics
                for ps in stat.product_stats.all()
            ]
        })

        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def store_statistics(self, request):
        """Получение статистики магазина"""
        user = request.user

        # Валидация параметров запроса
        filter_serializer = StoreFilterSerializer(data=request.query_params, context={'request': request})
        filter_serializer.is_valid(raise_exception=True)

        # Получаем параметры фильтрации
        store_id = filter_serializer.validated_data.get('store_id')
        city = filter_serializer.validated_data.get('city')
        date_from = filter_serializer.validated_data.get('date_from')
        date_to = filter_serializer.validated_data.get('date_to')

        # Формируем базовый запрос в зависимости от роли пользователя
        if user.role == 'admin':
            queryset = DailyStatistics.objects.filter(store__isnull=False)
        else:
            queryset = DailyStatistics.objects.filter(store__partner=user)

        # Применяем фильтры
        queryset = queryset.filter(date__range=(date_from, date_to))

        if store_id:
            queryset = queryset.filter(store_id=store_id)

        if city:
            queryset = queryset.filter(store__city=city)

        # Группируем статистику если выбрано несколько магазинов
        if not store_id and (user.role == 'admin' or city):
            # Агрегируем данные по всем магазинам
            summary = queryset.aggregate(
                total_income=Sum('total_income'),
                total_expense=Sum('total_expense'),
                total_debt=Sum('total_debt'),
                total_debt_paid=Sum('total_debt_paid'),
                total_bonus_items=Sum('total_bonus_items'),
                total_defect_items=Sum('total_defect_items'),
                total_balance=Sum('total_balance')
            )

            # Получаем список всех товаров
            products_stats = []
            for stat in queryset.prefetch_related('product_stats'):
                for ps in stat.product_stats.all():
                    products_stats.append({
                        'product_id': ps.product_id,
                        'product_name': ps.product_name,
                        'requested_quantity': ps.requested_quantity,
                        'sold_quantity': ps.sold_quantity,
                        'bonus_quantity': ps.bonus_quantity,
                        'defect_quantity': ps.defect_quantity,
                        'income_amount': ps.income_amount
                    })

            # Агрегируем статистику по товарам
            product_summary = {}
            for ps in products_stats:
                product_id = ps['product_id']
                if product_id not in product_summary:
                    product_summary[product_id] = {
                        'product_id': product_id,
                        'product_name': ps['product_name'],
                        'requested_quantity': 0,
                        'sold_quantity': 0,
                        'bonus_quantity': 0,
                        'defect_quantity': 0,
                        'income_amount': Decimal('0.00')
                    }

                product_summary[product_id]['requested_quantity'] += ps['requested_quantity']
                product_summary[product_id]['sold_quantity'] += ps['sold_quantity']
                product_summary[product_id]['bonus_quantity'] += ps['bonus_quantity']
                product_summary[product_id]['defect_quantity'] += ps['defect_quantity']
                product_summary[product_id]['income_amount'] += ps['income_amount']

            # Формируем итоговый результат
            response_data = {
                'date_from': date_from,
                'date_to': date_to,
                'total_income': summary['total_income'] or Decimal('0.00'),
                'total_expense': summary['total_expense'] or Decimal('0.00'),
                'total_debt': summary['total_debt'] or Decimal('0.00'),
                'total_debt_paid': summary['total_debt_paid'] or Decimal('0.00'),
                'total_bonus_items': summary['total_bonus_items'] or 0,
                'total_defect_items': summary['total_defect_items'] or 0,
                'total_balance': summary['total_balance'] or Decimal('0.00'),
                'product_summaries': list(product_summary.values())
            }

            if city:
                response_data['city'] = city
                response_data['store_count'] = queryset.values('store').distinct().count()

            return Response(response_data)

        # Для одного магазина возвращаем детальную статистику
        if store_id:
            try:
                store = Store.objects.get(id=store_id)

                # Проверяем права доступа
                if user.role == 'partner' and store.partner != user:
                    return Response(
                        {"error": "У вас нет доступа к этому магазину"},
                        status=status.HTTP_403_FORBIDDEN
                    )

                # Получаем статистику
                stats = queryset.filter(store=store).prefetch_related('product_stats')

                if not stats.exists():
                    # Если статистики нет, рассчитываем на лету

                    # Получаем заказы магазина
                    orders = Order.objects.filter(
                        store=store,
                        created_at__date__range=(date_from, date_to)
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
                    total_debt = store.debts.filter(
                        created_at__date__range=(date_from, date_to),
                        is_paid=False
                    ).aggregate(sum=Sum('amount'))['sum'] or Decimal('0.00')

                    # Получаем сумму погашенного долга
                    total_paid = store.debt_payments.filter(
                        payment_date__range=(date_from, date_to)
                    ).aggregate(sum=Sum('amount'))['sum'] or Decimal('0.00')

                    # Получаем расходы
                    total_expenses = store.expenses.filter(
                        expense_date__range=(date_from, date_to)
                    ).aggregate(sum=Sum('amount'))['sum'] or Decimal('0.00')

                    # Рассчитываем общую стоимость заказов
                    total_orders_amount = sum((item['total_amount'] for item in order_items), Decimal('0.00'))

                    # Формируем ответ
                    return Response({
                        'date_from': date_from,
                        'date_to': date_to,
                        'store_id': store.id,
                        'store_name': store.name,
                        'city': store.city,
                        'total_income': total_orders_amount,
                        'total_expense': total_expenses,
                        'total_debt': total_debt,
                        'total_debt_paid': total_paid,
                        'total_bonus_items': sum((item['total_bonus'] for item in order_items), 0),
                        'total_defect_items': sum((item['total_quantity'] for item in defect_items), 0),
                        'total_balance': total_orders_amount - total_expenses,
                        'product_summaries': [
                            {
                                'product_id': item['product_id'],
                                'product_name': item['product__name'],
                                'sold_quantity': item['total_quantity'],
                                'bonus_quantity': item['total_bonus'],
                                'income_amount': item['total_amount']
                            }
                            for item in order_items
                        ]
                    })

                # Если статистика уже есть
                summary = stats.aggregate(
                    total_income=Sum('total_income'),
                    total_expense=Sum('total_expense'),
                    total_debt=Sum('total_debt'),
                    total_debt_paid=Sum('total_debt_paid'),
                    total_bonus_items=Sum('total_bonus_items'),
                    total_defect_items=Sum('total_defect_items'),
                    total_balance=Sum('total_balance')
                )

                # Получаем статистику по товарам
                product_stats = []
                for stat in stats:
                    for ps in stat.product_stats.all():
                        product_stats.append({
                            'product_id': ps.product_id,
                            'product_name': ps.product_name,
                            'requested_quantity': ps.requested_quantity,
                            'sold_quantity': ps.sold_quantity,
                            'bonus_quantity': ps.bonus_quantity,
                            'defect_quantity': ps.defect_quantity,
                            'income_amount': ps.income_amount
                        })

                return Response({
                    'date_from': date_from,
                    'date_to': date_to,
                    'store_id': store.id,
                    'store_name': store.name,
                    'city': store.city,
                    'total_income': summary['total_income'] or Decimal('0.00'),
                    'total_expense': summary['total_expense'] or Decimal('0.00'),
                    'total_debt': summary['total_debt'] or Decimal('0.00'),
                    'total_debt_paid': summary['total_debt_paid'] or Decimal('0.00'),
                    'total_bonus_items': summary['total_bonus_items'] or 0,
                    'total_defect_items': summary['total_defect_items'] or 0,
                    'total_balance': summary['total_balance'] or Decimal('0.00'),
                    'product_summaries': product_stats
                })

            except Store.DoesNotExist:
                return Response(
                    {"error": "Магазин не найден"},
                    status=status.HTTP_404_NOT_FOUND
                )

        return Response(
            {"error": "Требуется указать ID магазина или город"},
            status=status.HTTP_400_BAD_REQUEST
        )

    @action(detail=False, methods=['get'])
    def dashboard_summary(self, request):
        """Общая сводка для панели управления"""
        user = self.request.user

        # Сегодняшняя дата
        today = timezone.now().date()

        # Данные для всех пользователей
        if user.role == 'admin':
            # Для администратора - общая статистика
            # Доход за сегодня
            income_today = DailyStatistics.objects.filter(
                date=today
            ).aggregate(sum=Sum('total_income'))['sum'] or Decimal('0.00')

            # Расходы за сегодня
            expense_today = DailyStatistics.objects.filter(
                date=today
            ).aggregate(sum=Sum('total_expense'))['sum'] or Decimal('0.00')

            # Общий долг
            total_debt = DailyStatistics.objects.filter(
                store__isnull=False
            ).aggregate(sum=Sum('total_debt'))['sum'] or Decimal('0.00')

            # Погашенный долг сегодня
            debt_paid_today = DailyStatistics.objects.filter(
                date=today,
                store__isnull=False
            ).aggregate(sum=Sum('total_debt_paid'))['sum'] or Decimal('0.00')

            # Прибыль сегодня
            profit_today = income_today - expense_today

            # Количество активных партнеров
            active_partners = User.objects.filter(role='partner', is_active=True).count()

            # Количество магазинов
            stores_count = Store.objects.filter(status='approved').count()

            # Количество заказов сегодня
            from apps.orders.models import Order
            orders_today = Order.objects.filter(created_at__date=today).count()

            # Формируем ответ
            return Response({
                'income_today': income_today,
                'expense_today': expense_today,
                'profit_today': profit_today,
                'total_debt': total_debt,
                'debt_paid_today': debt_paid_today,
                'active_partners': active_partners,
                'stores_count': stores_count,
                'orders_today': orders_today,
                'date': today
            })
        else:
            # Для партнера - личная статистика
            # Доход за сегодня
            income_today = DailyStatistics.objects.filter(
                date=today,
                partner=user
            ).aggregate(sum=Sum('total_income'))['sum'] or Decimal('0.00')

            # Расходы за сегодня
            expense_today = DailyStatistics.objects.filter(
                date=today,
                partner=user
            ).aggregate(sum=Sum('total_expense'))['sum'] or Decimal('0.00')

            # Количество магазинов
            stores_count = Store.objects.filter(partner=user, status='approved').count()

            # Количество заказов сегодня
            from apps.orders.models import Order
            orders_today = Order.objects.filter(
                created_at__date=today,
                query=Q(created_by=user) | Q(partner=user)
            )

            # Остаток товаров
            remaining_items = PartnerInventory.objects.filter(
                partner=user
            ).aggregate(sum=Sum('quantity'))['sum'] or 0

            # Прибыль сегодня
            profit_today = income_today - expense_today

            # Формируем ответ
            return Response({
                'income_today': income_today,
                'expense_today': expense_today,
                'profit_today': profit_today,
                'stores_count': stores_count,
                'orders_today': orders_today,
                'remaining_items': remaining_items,
                'date': today
            })
            queryset = queryset.filter(store__city=city)

        # Группируем статистику если выбрано несколько магазинов
        if not store_id and (user.role == 'admin' or city):
            # Агрегируем данные по всем магазинам
            summary = queryset.aggregate(
                total_income=Sum('total_income'),
                total_expense=Sum('total_expense'),
                total_debt=Sum('total_debt'),
                total_debt_paid=Sum('total_debt_paid'),
                total_bonus_items=Sum('total_bonus_items'),
                total_defect_items=Sum('total_defect_items'),
                total_balance=Sum('total_balance')
            )

            # Получаем список всех товаров
            products_stats = []
            for stat in queryset.prefetch_related('product_stats'):
                for ps in stat.product_stats.all():
                    products_stats.append({
                        'product_id': ps.product_id,
                        'product_name': ps.product_name,
                        'requested_quantity': ps.requested_quantity,
                        'sold_quantity': ps.sold_quantity,
                        'bonus_quantity': ps.bonus_quantity,
                        'defect_quantity': ps.defect_quantity,
                        'income_amount': ps.income_amount
                    })

            # Агрегируем статистику по товарам
            product_summary = {}
            for ps in products_stats:
                product_id = ps['product_id']
                if product_id not in product_summary:
                    product_summary[product_id] = {
                        'product_id': product_id,
                        'product_name': ps['product_name'],
                        'requested_quantity': 0,
                        'sold_quantity': 0,
                        'bonus_quantity': 0,
                        'defect_quantity': 0,
                        'income_amount': Decimal('0.00')
                    }

                product_summary[product_id]['requested_quantity'] += ps['requested_quantity']
                product_summary[product_id]['sold_quantity'] += ps['sold_quantity']
                product_summary[product_id]['bonus_quantity'] += ps['bonus_quantity']
                product_summary[product_id]['defect_quantity'] += ps['defect_quantity']
                product_summary[product_id]['income_amount'] += ps['income_amount']

            # Формируем итоговый результат
            response_data = {
                'date_from': date_from,
                'date_to': date_to,
                'total_income': summary['total_income'] or Decimal('0.00'),
                'total_expense': summary['total_expense'] or Decimal('0.00'),
                'total_debt': summary['total_debt'] or Decimal('0.00'),
                'total_debt_paid': summary['total_debt_paid'] or Decimal('0.00'),
                'total_bonus_items': summary['total_bonus_items'] or 0,
                'total_defect_items': summary['total_defect_items'] or 0,
                'total_balance': summary['total_balance'] or Decimal('0.00'),
                'product_summaries': list(product_summary.values())
            }

            if city:
                response_data['city'] = city
                response_data['store_count'] = queryset.values('store').distinct().count()

            return Response(response_data)

        # Для одного магазина возвращаем детальную статистику
        if store_id:
            try:
                store = Store.objects.get(id=store_id)

                # Проверяем права доступа
                if user.role == 'partner' and store.partner != user:
                    return Response(
                        {"error": "У вас нет доступа к этому магазину"},
                        status=status.HTTP_403_FORBIDDEN
                    )

                # Получаем статистику
                stats = queryset.filter(store=store).prefetch_related('product_stats')

                if not stats.exists():
                    # Если статистики нет, рассчитываем на лету

                    # Получаем заказы магазина
                    orders = Order.objects.filter(
                        store=store,
                        created_at__date__range=(date_from, date_to)
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
                    total_debt = store.debts.filter(
                        created_at__date__range=(date_from, date_to),
                        is_paid=False
                    ).aggregate(sum=Sum('amount'))['sum'] or Decimal('0.00')

                    # Получаем сумму погашенного долга
                    total_paid = store.debt_payments.filter(
                        payment_date__range=(date_from, date_to)
                    ).aggregate(sum=Sum('amount'))['sum'] or Decimal('0.00')

                    # Получаем расходы
                    total_expenses = store.expenses.filter(
                        expense_date__range=(date_from, date_to)
                    ).aggregate(sum=Sum('amount'))['sum'] or Decimal('0.00')

                    # Рассчитываем общую стоимость заказов
                    total_orders_amount = sum(item['total_amount'] for item in order_items)

                    # Формируем ответ
                    return Response({
                        'date_from': date_from,
                        'date_to': date_to,
                        'store_id': store.id,
                        'store_name': store.name,
                        'city': store.city,
                        'total_income': total_orders_amount,
                        'total_expense': total_expenses,
                        'total_debt': total_debt,
                        'total_debt_paid': total_paid,
                        'total_bonus_items': sum(item['total_bonus'] for item in order_items),
                        'total_defect_items': sum(item['total_quantity'] for item in defect_items),
                        'total_balance': total_orders_amount - total_expenses,
                        'product_summaries': [
                            {
                                'product_id': item['product_id'],
                                'product_name': item['product__name'],
                                'sold_quantity': item['total_quantity'],
                                'bonus_quantity': item['total_bonus'],
                                'income_amount': item['total_amount']
                            }
                            for item in order_items
                        ]
                    })

                # Если статистика уже есть
                summary = stats.aggregate(
                    total_income=Sum('total_income'),
                    total_expense=Sum('total_expense'),
                    total_debt=Sum('total_debt'),
                    total_debt_paid=Sum('total_debt_paid'),
                    total_bonus_items=Sum('total_bonus_items'),
                    total_defect_items=Sum('total_defect_items'),
                    total_balance=Sum('total_balance')
                )

                # Получаем статистику по товарам
                product_stats = []
                for stat in stats:
                    for ps in stat.product_stats.all():
                        product_stats.append({
                            'product_id': ps.product_id,
                            'product_name': ps.product_name,
                            'requested_quantity': ps.requested_quantity,
                            'sold_quantity': ps.sold_quantity,
                            'bonus_quantity': ps.bonus_quantity,
                            'defect_quantity': ps.defect_quantity,
                            'income_amount': ps.income_amount
                        })

                return Response({
                    'date_from': date_from,
                    'date_to': date_to,
                    'store_id': store.id,
                    'store_name': store.name,
                    'city': store.city,
                    'total_income': summary['total_income'] or Decimal('0.00'),
                    'total_expense': summary['total_expense'] or Decimal('0.00'),
                    'total_debt': summary['total_debt'] or Decimal('0.00'),
                    'total_debt_paid': summary['total_debt_paid'] or Decimal('0.00'),
                    'total_bonus_items': summary['total_bonus_items'] or 0,
                    'total_defect_items': summary['total_defect_items'] or 0,
                    'total_balance': summary['total_balance'] or Decimal('0.00'),
                    'product_summaries': product_stats
                })

            except Store.DoesNotExist:
                return Response(
                    {"error": "Магазин не найден"},
                    status=status.HTTP_404_NOT_FOUND
                )

        return Response(
            {"error": "Требуется указать ID магазина или город"},
            status=status.HTTP_400_BAD_REQUEST
        )

    @action(detail=False, methods=['get'])
    def admin_statistics(self, request):
        """Получение общей статистики для администратора"""
        user = request.user

        # Проверяем права доступа
        if user.role != 'admin':
            return Response(
                {"error": "Только администратор может просматривать эту статистику"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Получаем параметры фильтрации
        date_from_str = request.query_params.get('date_from')
        date_to_str = request.query_params.get('date_to')
        city = request.query_params.get('city')
        partner_id = request.query_params.get('partner_id')

        # Устанавливаем значения по умолчанию
        today = timezone.now().date()
        date_from = today
        date_to = today

        # Преобразуем строковые даты в объекты date
        if date_from_str:
            try:
                date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {"error": "Неверный формат даты. Используйте YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        if date_to_str:
            try:
                date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {"error": "Неверный формат даты. Используйте YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Формируем базовый набор данных в зависимости от фильтров
        # Статистика партнеров
        partner_stats = DailyStatistics.objects.filter(
            partner__isnull=False,
            date__range=(date_from, date_to)
        )

        # Статистика магазинов
        store_stats = DailyStatistics.objects.filter(
            store__isnull=False,
            date__range=(date_from, date_to)
        )

        # Применяем дополнительные фильтры
        if partner_id:
            partner_stats = partner_stats.filter(partner_id=partner_id)
            store_stats = store_stats.filter(store__partner_id=partner_id)

        if city:
            store_stats = store_stats.filter(store__city=city)

        # Получаем сводную статистику по всем партнерам
        partner_summary = partner_stats.aggregate(
            total_income=Sum('total_income'),
            total_expense=Sum('total_expense'),
            total_bonus_items=Sum('total_bonus_items'),
            total_defect_items=Sum('total_defect_items'),
            total_balance=Sum('total_balance')
        )

        # Получаем сводную статистику по всем магазинам
        store_summary = store_stats.aggregate(
            total_debt=Sum('total_debt'),
            total_debt_paid=Sum('total_debt_paid')
        )

        # Получаем статистику по товарам
        # Для партнеров (доход)
        partner_products = []
        for stat in partner_stats.prefetch_related('product_stats'):
            for ps in stat.product_stats.all():
                partner_products.append({
                    'product_id': ps.product_id,
                    'product_name': ps.product_name,
                    'requested_quantity': ps.requested_quantity,
                    'income_amount': ps.income_amount
                })

        # Для магазинов (долги и бонусы)
        store_products = []
        for stat in store_stats.prefetch_related('product_stats'):
            for ps in stat.product_stats.all():
                store_products.append({
                    'product_id': ps.product_id,
                    'product_name': ps.product_name,
                    'sold_quantity': ps.sold_quantity,
                    'bonus_quantity': ps.bonus_quantity,
                    'defect_quantity': ps.defect_quantity
                })

        # Агрегируем статистику по товарам
        product_summary = {}

        # Добавляем данные от партнеров
        for pp in partner_products:
            product_id = pp['product_id']
            if product_id not in product_summary:
                product_summary[product_id] = {
                    'product_id': product_id,
                    'product_name': pp['product_name'],
                    'requested_quantity': 0,
                    'sold_quantity': 0,
                    'bonus_quantity': 0,
                    'defect_quantity': 0,
                    'income_amount': Decimal('0.00')
                }

            product_summary[product_id]['requested_quantity'] += pp['requested_quantity']
            product_summary[product_id]['income_amount'] += pp['income_amount']

        # Добавляем данные от магазинов
        for sp in store_products:
            product_id = sp['product_id']
            if product_id not in product_summary:
                product_summary[product_id] = {
                    'product_id': product_id,
                    'product_name': sp['product_name'],
                    'requested_quantity': 0,
                    'sold_quantity': 0,
                    'bonus_quantity': 0,
                    'defect_quantity': 0,
                    'income_amount': Decimal('0.00')
                }

            product_summary[product_id]['sold_quantity'] += sp['sold_quantity']
            product_summary[product_id]['bonus_quantity'] += sp['bonus_quantity']
            product_summary[product_id]['defect_quantity'] += sp['defect_quantity']

        # Получаем остаток товаров (инвентарь партнеров)
        remaining_items = PartnerInventory.objects.all()
        if partner_id:
            remaining_items = remaining_items.filter(partner_id=partner_id)

        remaining_count = remaining_items.aggregate(sum=Sum('quantity'))['sum'] or 0

        # Рассчитываем общий баланс
        total_income = partner_summary['total_income'] or Decimal('0.00')
        total_expense = partner_summary['total_expense'] or Decimal('0.00')
        total_bonus_value = Decimal('0.00')  # Это нужно рассчитать на основе стоимости бонусных товаров

        # Для расчета стоимости бонусных товаров нужно знать цену каждого
        # Поэтому просто используем сумму из статистики
        total_balance = total_income - total_expense - total_bonus_value

        # Формируем итоговый ответ
        response_data = {
            'date_from': date_from,
            'date_to': date_to,
            'total_income': total_income,
            'total_expense': total_expense,
            'total_debt': store_summary['total_debt'] or Decimal('0.00'),
            'total_debt_paid': store_summary['total_debt_paid'] or Decimal('0.00'),
            'total_bonus_items': partner_summary['total_bonus_items'] or 0,
            'total_defect_items': partner_summary['total_defect_items'] or 0,
            'total_remaining_items': remaining_count,
            'total_balance': total_balance,
            'product_summaries': list(product_summary.values())
        }

        # Добавляем дополнительную информацию в зависимости от фильтров
        if partner_id:
            try:
                partner = User.objects.get(id=partner_id, role='partner')
                response_data['partner_id'] = partner.id
                response_data['partner_name'] = f"{partner.first_name} {partner.last_name}"
            except User.DoesNotExist:
                pass

        if city:
            response_data['city'] = city
            response_data['store_count'] = Store.objects.filter(city=city).count()

        return Response(response_data)