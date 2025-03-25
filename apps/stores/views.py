from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import City, Store, StoreDebt
from .serializers import (
    CitySerializer, StoreSerializer, StoreDetailSerializer,
    StoreStatusUpdateSerializer, StoreActivationSerializer,
    StoreDebtSerializer, StoreDebtPaymentSerializer
)
from django.db.models import Sum, Avg, Count, F, ExpressionWrapper, DurationField


class IsAdminUser(permissions.BasePermission):
    """
    Разрешает доступ только администраторам.
    """

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

    @swagger_auto_schema(
        operation_description="Получить список всех городов",
        responses={200: CitySerializer(many=True)}
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Создать новый город (только администратор)",
        request_body=CitySerializer,
        responses={201: CitySerializer}
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)


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
        elif self.action == 'activate' or self.action == 'deactivate':
            return StoreActivationSerializer
        return self.serializer_class

    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy']:
            self.permission_classes = [IsAdminUser]
        return super().get_permissions()

    def get_queryset(self):
        # Для генерации схемы Swagger
        if getattr(self, 'swagger_fake_view', False):
            return Store.objects.none()

        queryset = Store.objects.all()

        # Фильтрация по статусу для не-администраторов
        if not self.request.user.is_staff:
            queryset = queryset.filter(status='approved', is_active=True)

        return queryset

    @swagger_auto_schema(
        operation_description="Получить список всех магазинов (для администраторов - все, для партнеров - только подтвержденные и активные)",
        responses={200: StoreSerializer(many=True)}
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Создать заявку на новый магазин (только партнеры)",
        request_body=StoreSerializer,
        responses={201: StoreSerializer}
    )
    def create(self, request, *args, **kwargs):
        # Администраторы не могут создавать магазины
        if request.user.is_staff:
            return Response(
                {"error": "Администраторы не могут создавать заявки на магазины"},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Получить детальную информацию о магазине",
        responses={200: StoreDetailSerializer}
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Обновить магазин (только администратор)",
        request_body=StoreSerializer,
        responses={200: StoreSerializer}
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Частично обновить магазин (только администратор)",
        request_body=StoreSerializer,
        responses={200: StoreSerializer}
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Удаление магазинов не поддерживается",
        responses={405: "Удаление магазинов не поддерживается"}
    )
    def destroy(self, request, *args, **kwargs):
        return Response(
            {"error": "Удаление магазинов не поддерживается. Используйте деактивацию."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    @swagger_auto_schema(
        method='post',
        operation_description="Администратор: подтвердить или отклонить заявку на магазин",
        request_body=StoreStatusUpdateSerializer,
        responses={200: StoreDetailSerializer}
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def update_status(self, request, pk=None):
        store = self.get_object()
        serializer = self.get_serializer(store, data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(StoreDetailSerializer(store).data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        method='post',
        operation_description="Администратор: активировать магазин",
        responses={200: StoreDetailSerializer}
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def activate(self, request, pk=None):
        store = self.get_object()

        if store.status != 'approved':
            return Response(
                {"error": "Можно активировать только подтвержденные магазины"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if store.is_active:
            return Response(
                {"error": "Магазин уже активирован"},
                status=status.HTTP_400_BAD_REQUEST
            )

        store.is_active = True
        store.save()

        return Response(StoreDetailSerializer(store).data)

    @swagger_auto_schema(
        method='post',
        operation_description="Администратор: деактивировать магазин",
        responses={200: StoreDetailSerializer}
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def deactivate(self, request, pk=None):
        store = self.get_object()

        if not store.is_active:
            return Response(
                {"error": "Магазин уже деактивирован"},
                status=status.HTTP_400_BAD_REQUEST
            )

        store.is_active = False
        store.save()

        return Response(StoreDetailSerializer(store).data)

    @action(detail=False, methods=['get'])
    def filter_by_debt(self, request):
        stores = Store.objects.annotate(
            total_debt=Sum('storedebts__amount', filter=F('storedebts__is_paid') == False)
        ).order_by('-total_debt')
        serializer = StoreSerializer(stores, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def filter_by_payment_speed(self, request):
        stores = Store.objects.annotate(
            paid_requests=Count('product_requests', filter=F('product_requests__status') == 'received'),
            avg_delay=Avg(
                ExpressionWrapper(
                    F('product_requests__created_at') - F('product_requests__updated_at'),
                    output_field=DurationField()
                ),
                filter=F('product_requests__status') == 'received'
            )
        ).order_by('avg_delay')
        serializer = StoreSerializer(stores, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def all_stores(self, request):
        stores = Store.objects.all()
        serializer = StoreSerializer(stores, many=True)
        return Response(serializer.data)


class StoreDebtViewSet(viewsets.ModelViewSet):
    queryset = StoreDebt.objects.all()
    serializer_class = StoreDebtSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['store', 'is_paid']
    ordering_fields = ['created_at', 'amount']

    def get_queryset(self):
        # Для генерации схемы Swagger
        if getattr(self, 'swagger_fake_view', False):
            return StoreDebt.objects.none()

        # Администраторы видят все долги, партнеры - только созданные ими
        if self.request.user.is_staff:
            return StoreDebt.objects.all()
        return StoreDebt.objects.filter(created_by=self.request.user)

    @swagger_auto_schema(
        method='post',
        operation_description="Отметить долг как оплаченный",
        request_body=StoreDebtPaymentSerializer,
        responses={200: StoreDebtSerializer}
    )
    @action(detail=True, methods=['post'])
    def mark_as_paid(self, request, pk=None):
        debt = self.get_object()
        serializer = StoreDebtPaymentSerializer(debt, data={'is_paid': True})

        if serializer.is_valid():
            serializer.save()
            return Response(StoreDebtSerializer(debt).data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)