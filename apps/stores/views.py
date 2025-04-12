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
from apps.products.permissions import IsAdminUser, IsPartnerUser, IsOwnerOrAdmin
from apps.orders.serializers import StoreDebtPaymentSerializer, StoreExpenseSerializer


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
        """Получение финансовой сводки по магазину"""
        store = self.get_object()

        # Получаем долги
        debts = StoreDebt.objects.filter(store=store)
        total_debt = sum(debt.amount for debt in debts)

        # Получаем платежи
        payments = StoreDebtPayment.objects.filter(store=store)
        total_paid = sum(payment.amount for payment in payments)

        # Получаем расходы
        expenses = StoreExpense.objects.filter(store=store)
        total_expenses = sum(expense.amount for expense in expenses)

        # Получаем данные о бракованных товарах
        from apps.orders.models import DefectItem
        defect_items = DefectItem.objects.filter(order__store=store)
        total_defects = sum(defect.quantity for defect in defect_items)

        # Расчет оставшегося долга и прибыли
        remaining_debt = total_debt - total_paid
        profit = total_paid - total_expenses

        return Response({
            "store_id": store.id,
            "store_name": store.name,
            "total_debt": total_debt,
            "paid_debt": total_paid,
            "remaining_debt": remaining_debt,
            "expenses": total_expenses,
            "profit": profit,
            "total_defects": total_defects
        })

    @action(detail=True, methods=['post'])
    def add_expense(self, request, pk=None):
        """Добавление расхода для магазина"""
        store = self.get_object()

        # Проверяем, что пользователь имеет доступ к магазину
        user = request.user
        if user.role != 'admin' and store.partner != user:
            return Response(
                {"detail": "У вас нет доступа к этому магазину"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Создаем расход
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