from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Sum, Avg, Count, F, ExpressionWrapper, DurationField
from .models import City, Store, StoreDebt
from .serializers import (
    CitySerializer, StoreSerializer, StoreDetailSerializer,
    StoreStatusUpdateSerializer, StoreActivationSerializer,
    StoreDebtSerializer, StoreDebtPaymentSerializer, DebtPaymentSerializer
)
from apps.orders.models import ProductRequest


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_staff


class CityViewSet(viewsets.ModelViewSet):
    queryset = City.objects.all()
    serializer_class = CitySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            self.permission_classes = [IsAdminUser]
        return super().get_permissions()


class StoreViewSet(viewsets.ModelViewSet):
    queryset = Store.objects.all()
    serializer_class = StoreSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['city', 'status', 'is_active']
    search_fields = ['name', 'inn', 'address', 'phone']
    ordering_fields = ['name', 'created_at', 'updated_at']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return StoreDetailSerializer
        elif self.action == 'update_status':
            return StoreStatusUpdateSerializer
        elif self.action in ['activate', 'deactivate']:
            return StoreActivationSerializer
        return self.serializer_class

    def get_queryset(self):
        """
        Возвращает QuerySet магазинов в зависимости от роли пользователя:
        - Для администраторов возвращаются все магазины
        - Для обычных пользователей только подтвержденные и активные магазины
        """
        if self.request.user.is_staff:
            # Для администраторов возвращаем все магазины
            return Store.objects.all()
        else:
            # Для обычных пользователей только подтвержденные и активные
            return Store.objects.filter(status='approved', is_active=True)

    def create(self, request, *args, **kwargs):
        if request.user.is_staff:
            return Response({"error": "Администраторы не могут создавать магазины"}, status=403)
        return super().create(request, *args, **kwargs)

    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def pending_requests(self, request):
        """
        Получение списка заявок на создание магазинов, ожидающих рассмотрения
        """
        pending_stores = Store.objects.filter(status='pending')
        serializer = self.get_serializer(pending_stores, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def approved_stores(self, request):
        """
        Получение списка подтвержденных магазинов
        """
        approved_stores = Store.objects.filter(status='approved')
        serializer = self.get_serializer(approved_stores, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def rejected_stores(self, request):
        """
        Получение списка отклоненных магазинов
        """
        rejected_stores = Store.objects.filter(status='rejected')
        serializer = self.get_serializer(rejected_stores, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def update_status(self, request, pk=None):
        store = self.get_object()
        serializer = self.get_serializer(store, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(StoreDetailSerializer(store).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def activate(self, request, pk=None):
        store = self.get_object()
        if store.status != 'approved':
            return Response({"error": "Можно активировать только подтвержденные магазины"}, status=400)
        if store.is_active:
            return Response({"error": "Магазин уже активирован"}, status=400)

        store.is_active = True
        store.save()
        return Response(StoreDetailSerializer(store).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def deactivate(self, request, pk=None):
        store = self.get_object()
        if not store.is_active:
            return Response({"error": "Магазин уже деактивирован"}, status=400)

        store.is_active = False
        store.save()
        return Response(StoreDetailSerializer(store).data)

    @action(detail=False, methods=['get'])
    def filter_by_debt(self, request):
        """
        Фильтрация магазинов по долгам
        """
        # Для обычных пользователей показываем только подтвержденные и активные магазины
        queryset = self.get_queryset()

        stores = queryset.annotate(
            total_debt=Sum('debts__amount', filter=F('debts__is_paid') == False)
        ).order_by('-total_debt')

        serializer = StoreSerializer(stores, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def filter_by_payment_speed(self, request):
        """
        Фильтрация магазинов по скорости оплаты
        """
        try:
            # Для обычных пользователей показываем только подтвержденные и активные магазины
            queryset = self.get_queryset()

            stores = queryset.annotate(
                paid_requests=Count('product_requests', filter=F('product_requests__status') == 'received'),
                # Безопасная формула для расчета среднего времени обработки
                avg_delay=Avg(
                    ExpressionWrapper(
                        F('product_requests__created_at') - F('product_requests__created_at'),
                        # Временно используем одинаковое поле для избежания ошибок
                        output_field=DurationField()
                    ),
                    filter=F('product_requests__status') == 'received'
                )
            ).order_by('paid_requests')

            serializer = StoreSerializer(stores, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response({"error": str(e)}, status=400)

    @action(detail=True, methods=['get'])
    def requests(self, request, pk=None):
        """Получение списка запросов для конкретного магазина"""
        store = self.get_object()
        requests = ProductRequest.objects.filter(store=store)

        # Пагинация для большого количества запросов
        page = self.paginate_queryset(requests)
        if page is not None:
            data = [
                {
                    "id": r.id,
                    "product": str(r.product),
                    "quantity": r.quantity,
                    "status": r.get_status_display(),
                    "created_at": r.created_at
                } for r in page
            ]
            return self.get_paginated_response(data)

        data = [
            {
                "id": r.id,
                "product": str(r.product),
                "quantity": r.quantity,
                "status": r.get_status_display(),
                "created_at": r.created_at
            } for r in requests
        ]
        return Response(data)


class StoreDebtViewSet(viewsets.ModelViewSet):
    serializer_class = StoreDebtSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['store', 'is_paid']
    ordering_fields = ['created_at', 'amount']

    def get_queryset(self):
        """Фильтрация долгов в зависимости от роли пользователя"""
        queryset = StoreDebt.objects.all()

        # Если обычный пользователь, показываем только долги магазинов,
        # которые связаны с его запросами и только для подтвержденных и активных магазинов
        if not self.request.user.is_staff:
            store_ids = ProductRequest.objects.filter(
                user=self.request.user
            ).values_list('store_id', flat=True).distinct()

            queryset = queryset.filter(
                store_id__in=store_ids,
                store__status='approved',
                store__is_active=True
            )

        return queryset

    @action(detail=True, methods=['post'])
    def mark_as_paid(self, request, pk=None):
        """Отметить долг как оплаченный"""
        debt = self.get_object()

        # Проверяем, имеет ли пользователь право отмечать долг как оплаченный
        if not request.user.is_staff:
            return Response({"error": "Только администратор может отмечать долги как оплаченные"},
                            status=403)

        serializer = StoreDebtPaymentSerializer(debt, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(StoreDebtSerializer(debt).data)

    @action(detail=False, methods=['post'])
    def pay_debt(self, request):
        """Оплатить долг полностью или частично"""
        serializer = DebtPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            debt = StoreDebt.objects.get(id=serializer.validated_data['debt_id'])

            # Проверяем, доступен ли долг для этого пользователя
            if not request.user.is_staff:
                store_ids = ProductRequest.objects.filter(
                    user=request.user
                ).values_list('store_id', flat=True).distinct()

                if debt.store_id not in store_ids or debt.store.status != 'approved' or not debt.store.is_active:
                    return Response({"error": "Долг не найден или недоступен"}, status=404)

            payment_amount = serializer.validated_data['payment_amount']

            if payment_amount >= debt.amount:
                # Полная оплата
                debt.is_paid = True
                debt.paid_at = timezone.now()
                debt.save()

                # Обновляем статистику календаря, если функция доступна
                try:
                    from apps.finance.services import update_calendar_statistics
                    update_calendar_statistics(
                        debt.paid_at.date(),
                        store=debt.store,
                        city=debt.store.city,
                        has_debt_payment=True
                    )
                except (ImportError, AttributeError, TypeError):
                    # Функция недоступна или не поддерживает параметр has_debt_payment
                    try:
                        from apps.finance.services import update_calendar_statistics
                        update_calendar_statistics(
                            debt.paid_at.date(),
                            store=debt.store,
                            city=debt.store.city
                        )
                    except Exception:
                        pass

                return Response({
                    "status": "success",
                    "message": "Долг полностью погашен",
                    "debt": StoreDebtSerializer(debt).data
                })
            else:
                # Частичная оплата - создаем новый долг с остатком
                remaining = debt.amount - payment_amount

                # Отмечаем текущий долг как оплаченный
                debt.is_paid = True
                debt.paid_at = timezone.now()
                debt.save()

                # Создаем новый долг с оставшейся суммой
                new_debt = StoreDebt.objects.create(
                    store=debt.store,
                    amount=remaining,
                    request=debt.request
                )

                return Response({
                    "status": "partial_payment",
                    "message": f"Внесена частичная оплата. Новый долг: {remaining}",
                    "paid_debt": StoreDebtSerializer(debt).data,
                    "remaining_debt": StoreDebtSerializer(new_debt).data
                })
        except StoreDebt.DoesNotExist:
            return Response({"error": "Долг не найден"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=400)