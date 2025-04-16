from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Sum, Count
from datetime import datetime
from .models import Order, OrderItem, DefectItem
from .serializers import (
    OrderSerializer,
    OrderWithItemsSerializer,
    OrderStatusUpdateSerializer,
    OrderItemSerializer,
    DefectItemSerializer,
    DefectGroupSerializer,
    StoreDebtPaymentSerializer,
    StoreExpenseSerializer
)
from apps.stores.models import Store, StoreDebt, StoreDebtPayment, StoreExpense
from apps.products.permissions import IsAdminUser, IsPartnerUser, IsOwnerOrAdmin
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


class OrderViewSet(viewsets.ModelViewSet):
    """
    Представление для работы с заказами
    """
    serializer_class = OrderSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['order_type', 'status', 'is_group_order', 'store', 'partner']
    search_fields = ['store__name', 'partner__email', 'partner__first_name']
    ordering_fields = ['created_at', 'updated_at']

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return Order.objects.all()

        # Партнеры видят только свои заказы (созданные ими или для них)
        return Order.objects.filter(
            Q(created_by=user) | Q(partner=user)
        )

    def get_serializer_class(self):
        # Для отладки
        logger.debug(f"Action: {self.action}, данные запроса: {self.request.data}")

        if self.action == 'create':
            # Проверяем наличие items или order_items в данных запроса
            if 'items' in self.request.data or 'order_items' in self.request.data:
                logger.debug("Используется OrderWithItemsSerializer")
                return OrderWithItemsSerializer
            logger.debug("Используется OrderSerializer")
            return OrderSerializer
        elif self.action in ['update', 'partial_update'] and 'status' in self.request.data:
            logger.debug("Используется OrderStatusUpdateSerializer")
            return OrderStatusUpdateSerializer

        logger.debug("Используется OrderSerializer (default)")
        return OrderSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()

        # Добавляем данные о товарах для создания заказа
        if self.action == 'create':
            if 'items' in self.request.data:
                context['items'] = self.request.data.get('items', [])
            if 'order_items' in self.request.data:
                context['order_items'] = self.request.data.get('order_items', [])

        # Всегда добавляем запрос
        context['request'] = self.request

        return context

    def get_permissions(self):
        if self.action == 'destroy':
            return [IsAdminUser()]
        elif self.action in ['update', 'partial_update']:
            return [IsOwnerOrAdmin()]
        return [permissions.IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        logger.info(f"Создание заказа. Данные: {request.data}")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        logger.info(f"Заказ создан. ID: {instance.id}")

        headers = self.get_success_headers(serializer.data)
        return Response(
            OrderSerializer(instance, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
            headers=headers
        )

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Обновление статуса заказа"""
        order = self.get_object()
        serializer = OrderStatusUpdateSerializer(
            instance=order,
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(OrderSerializer(order).data)

    @action(detail=False, methods=['get'])
    def admin_orders(self, request):
        """Получение заказов от партнера к администратору"""
        queryset = self.get_queryset().filter(order_type='admin_to_partner')

        # Фильтрация по статусу
        status = request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)

        serializer = OrderSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def store_orders(self, request):
        """Получение заказов от партнера к магазину"""
        queryset = self.get_queryset().filter(order_type='partner_to_store')

        # Фильтрация по статусу
        status = request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)

        # Фильтрация по магазину
        store_id = request.query_params.get('store_id')
        if store_id:
            queryset = queryset.filter(store_id=store_id)

        serializer = OrderSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def in_process(self, request):
        """Получение заказов в обработке (аналог корзины)"""
        queryset = self.get_queryset().filter(status='in_process')
        serializer = OrderSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Получение статистики по заказам"""
        user = request.user

        # Определяем набор заказов в зависимости от роли пользователя
        if user.role == 'admin':
            orders = Order.objects.all()
        else:
            orders = Order.objects.filter(
                Q(created_by=user) | Q(partner=user)
            )

        # Общее количество заказов
        total_orders = orders.count()

        # Разбивка по статусам
        status_counts = {
            'in_process': orders.filter(status='in_process').count(),
            'confirmed': orders.filter(status='confirmed').count(),
            'rejected': orders.filter(status='rejected').count(),
        }

        # Разбивка по типам
        type_counts = {
            'admin_to_partner': orders.filter(order_type='admin_to_partner').count(),
            'partner_to_store': orders.filter(order_type='partner_to_store').count(),
        }

        # Разбивка по типу заказа (групповой/одиночный)
        order_type_counts = {
            'group': orders.filter(is_group_order=True).count(),
            'single': orders.filter(is_group_order=False).count(),
        }

        # Общая стоимость подтвержденных заказов
        confirmed_orders_price = sum(
            order.total_price for order in orders.filter(status='confirmed')
        )

        return Response({
            'total_orders': total_orders,
            'status_counts': status_counts,
            'type_counts': type_counts,
            'order_type_counts': order_type_counts,
            'confirmed_orders_price': confirmed_orders_price,
        })

    @action(detail=False, methods=['get'])
    def get_store_orders(self, request):
        """Получение заказов магазина по дате"""
        store_id = request.query_params.get('store_id')
        date_str = request.query_params.get('date')

        if not store_id:
            return Response(
                {"detail": "Необходимо указать ID магазина"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not date_str:
            return Response(
                {"detail": "Необходимо указать дату в формате YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {"detail": "Неверный формат даты. Используйте YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Находим заказы для магазина на указанную дату
        orders = Order.objects.filter(
            store_id=store_id,
            created_at__date=date,
            order_type='partner_to_store'
        ).order_by('-created_at')

        # Возвращаем список заказов с минимальной информацией
        order_data = [{
            'order_id': order.id,
            'created_at': order.created_at.isoformat(),
            'total_price': float(order.total_price),
            'items_count': order.order_items.count()
        } for order in orders]

        return Response({
            'store_id': store_id,
            'date': date.isoformat(),
            'orders_count': len(order_data),
            'orders': order_data
        })


class OrderItemViewSet(viewsets.ModelViewSet):
    """
    Представление для работы с элементами заказа
    """
    serializer_class = OrderItemSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['order', 'product']
    search_fields = ['product__name']
    ordering_fields = ['created_at', 'quantity', 'price']

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return OrderItem.objects.all()

        # Партнеры видят только элементы своих заказов
        return OrderItem.objects.filter(
            Q(order__created_by=user) | Q(order__partner=user)
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()

        # Добавляем заказ в контекст
        order_id = self.kwargs.get('order_pk')
        if order_id:
            context['order'] = Order.objects.get(id=order_id)

        return context

    def get_permissions(self):
        if self.action == 'destroy':
            return [permissions.IsAuthenticated(), IsOwnerOrAdmin()]
        elif self.action in ['update', 'partial_update']:
            return [permissions.IsAuthenticated(), IsOwnerOrAdmin()]
        return [permissions.IsAuthenticated()]


class DefectItemViewSet(viewsets.ModelViewSet):
    """
    Представление для работы с бракованными товарами
    """
    serializer_class = DefectItemSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['order', 'product']
    search_fields = ['product__name', 'description']
    ordering_fields = ['created_at', 'quantity']

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return DefectItem.objects.all()

        # Партнеры видят только бракованные товары в своих заказах
        return DefectItem.objects.filter(order__created_by=user)

    def get_serializer_context(self):
        context = super().get_serializer_context()

        # Добавляем заказ в контекст
        order_id = self.kwargs.get('order_pk')
        if order_id:
            try:
                context['order'] = Order.objects.get(id=order_id)
            except Order.DoesNotExist:
                pass

        # Всегда добавляем запрос в контекст
        context['request'] = self.request
        return context

    @action(detail=False, methods=['post'])
    def add_group(self, request):
        """Добавление группы бракованных товаров для заказа"""
        serializer = DefectGroupSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        defects = serializer.save()

        return Response(
            DefectItemSerializer(defects, many=True).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=['get'])
    def order_defects(self, request):
        """Получение бракованных товаров по конкретному заказу"""
        order_id = request.query_params.get('order_id')
        if not order_id:
            return Response(
                {"detail": "Необходимо указать ID заказа"},
                status=status.HTTP_400_BAD_REQUEST
            )

        queryset = self.get_queryset().filter(order_id=order_id)
        serializer = DefectItemSerializer(queryset, many=True)

        # Рассчитываем общую стоимость бракованных товаров
        total_defect_price = sum(defect.total_price for defect in queryset)

        return Response({
            "defects": serializer.data,
            "total_quantity": queryset.aggregate(total=Sum('quantity'))['total'] or 0,
            "total_price": total_defect_price
        })

    @action(detail=False, methods=['get'])
    def store_defects(self, request):
        store_id = request.query_params.get('store_id')
        date_str = request.query_params.get('date')

        if not store_id:
            return Response(
                {"detail": "Необходимо указать ID магазина"},
                status=status.HTTP_400_BAD_REQUEST
            )

        queryset = self.get_queryset().filter(order__store_id=store_id)

        # Фильтрация по дате, если указана
        if date_str:
            try:
                from datetime import datetime
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
                queryset = queryset.filter(order__created_at__date=date)
            except ValueError:
                return Response(
                    {"detail": "Неверный формат даты. Используйте YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        serializer = DefectItemSerializer(queryset, many=True)

        # Рассчитываем общую стоимость бракованных товаров
        total_defect_price = sum(defect.total_price for defect in queryset)

        # Группируем по товарам
        product_summary = {}
        for defect in queryset:
            product_id = defect.product_id
            if product_id not in product_summary:
                product_summary[product_id] = {
                    "product_id": product_id,
                    "product_name": defect.product.name,
                    "total_quantity": 0,
                    "total_price": 0
                }

            product_summary[product_id]["total_quantity"] += defect.quantity
            product_summary[product_id]["total_price"] += float(defect.total_price)

        return Response({
            "defects": serializer.data,
            "total_quantity": queryset.aggregate(total=Sum('quantity'))['total'] or 0,
            "total_price": float(total_defect_price),
            "products_summary": list(product_summary.values())
        })


class StoreDebtPaymentViewSet(viewsets.ModelViewSet):
    """
    Представление для работы с платежами по долгам магазинов
    """
    serializer_class = StoreDebtPaymentSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['store']
    ordering_fields = ['payment_date', 'amount']

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return StoreDebtPayment.objects.all()

        # Партнеры видят только платежи своих магазинов
        return StoreDebtPayment.objects.filter(store__partner=user)

    def get_permissions(self):
        if self.action in ['destroy', 'update', 'partial_update']:
            return [IsOwnerOrAdmin()]
        return [permissions.IsAuthenticated()]

    @action(detail=False, methods=['get'])
    def store_payments(self, request):
        """Получение всех платежей по долгам конкретного магазина"""
        store_id = request.query_params.get('store_id')
        if not store_id:
            return Response(
                {"detail": "Необходимо указать ID магазина"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Проверка доступа к магазину
        try:
            store = Store.objects.get(id=store_id)
            if request.user.role != 'admin' and store.partner != request.user:
                return Response(
                    {"detail": "У вас нет доступа к этому магазину"},
                    status=status.HTTP_403_FORBIDDEN
                )
        except Store.DoesNotExist:
            return Response(
                {"detail": "Магазин не найден"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Получаем платежи и долги
        payments = StoreDebtPayment.objects.filter(store_id=store_id).order_by('-payment_date')
        debts = StoreDebt.objects.filter(store_id=store_id)

        # Рассчитываем общие суммы
        total_debt = sum(float(debt.amount) for debt in debts)
        total_paid = sum(float(payment.amount) for payment in payments)
        remaining_debt = total_debt - total_paid

        return Response({
            "store_id": store_id,
            "store_name": store.name,
            "total_debt": total_debt,
            "total_paid": total_paid,
            "remaining_debt": remaining_debt,
            "payments": StoreDebtPaymentSerializer(payments, many=True).data
        })


class StoreExpenseViewSet(viewsets.ModelViewSet):
    """
    Представление для работы с расходами магазинов
    """
    serializer_class = StoreExpenseSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['store', 'expense_date']
    search_fields = ['description']
    ordering_fields = ['expense_date', 'amount', 'created_at']

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return StoreExpense.objects.all()

        # Партнеры видят только расходы своих магазинов
        return StoreExpense.objects.filter(store__partner=user)

    def get_permissions(self):
        if self.action in ['destroy', 'update', 'partial_update']:
            return [IsOwnerOrAdmin()]
        return [permissions.IsAuthenticated()]

    @action(detail=False, methods=['get'])
    def store_expenses(self, request):
        """Получение всех расходов конкретного магазина"""
        store_id = request.query_params.get('store_id')
        if not store_id:
            return Response(
                {"detail": "Необходимо указать ID магазина"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Проверка доступа к магазину
        try:
            store = Store.objects.get(id=store_id)
            if request.user.role != 'admin' and store.partner != request.user:
                return Response(
                    {"detail": "У вас нет доступа к этому магазину"},
                    status=status.HTTP_403_FORBIDDEN
                )
        except Store.DoesNotExist:
            return Response(
                {"detail": "Магазин не найден"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Получаем расходы
        expenses = StoreExpense.objects.filter(store_id=store_id).order_by('-expense_date')
        total_expenses = sum(float(expense.amount) for expense in expenses)

        return Response({
            "store_id": store_id,
            "store_name": store.name,
            "total_expenses": total_expenses,
            "expenses": StoreExpenseSerializer(expenses, many=True).data
        })