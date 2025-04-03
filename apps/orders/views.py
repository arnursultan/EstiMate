from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from .models import ProductRequest
from .serializers import (
    ProductRequestSerializer,
    AdminProductRequestStatusSerializer,
    PartnerMarkReceivedSerializer,
    ReportDamagedSerializer,
    ProductRequestCalculationSerializer,
    BulkProductRequestSerializer
)
from apps.products.models import Product
from apps.stores.models import Store
from drf_yasg.utils import swagger_auto_schema



class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_staff


class ProductRequestViewSet(viewsets.ModelViewSet):
    serializer_class = ProductRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'payment_method', 'for_store', 'store', 'product']
    search_fields = ['product__name', 'store__name']
    ordering_fields = ['created_at', 'quantity', 'total_price']

    def get_queryset(self):
        """
        Возвращает запросы в зависимости от роли пользователя:
        - Для администраторов - все запросы
        - Для обычных пользователей - только свои запросы
        """
        # Проверяем, не является ли это запросом для генерации схемы Swagger
        if getattr(self, 'swagger_fake_view', False):
            # Возвращаем пустой QuerySet для Swagger
            return ProductRequest.objects.none()

        user = self.request.user
        if user.is_staff:
            return ProductRequest.objects.all()
        return ProductRequest.objects.filter(user=user)

    def get_serializer_class(self):
        """Выбор сериализатора в зависимости от действия"""
        if self.action == 'update_status':
            return AdminProductRequestStatusSerializer
        elif self.action == 'mark_received':
            return PartnerMarkReceivedSerializer
        elif self.action == 'report_damaged':
            return ReportDamagedSerializer
        elif self.action == 'calculate':
            return ProductRequestCalculationSerializer
        return self.serializer_class

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['patch'], permission_classes=[IsAdminUser])
    def update_status(self, request, pk=None):
        """Обновление статуса запроса (только для администратора)"""
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            serializer.save()
            return Response(ProductRequestSerializer(instance).data)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'], permission_classes=[permissions.IsAuthenticated])
    def mark_received(self, request, pk=None):
        """Отметить запрос как полученный (для создателя запроса)"""
        instance = self.get_object()

        # Проверка прав доступа
        if instance.user != request.user:
            return Response({"error": "Вы можете подтверждать получение только своих запросов"},
                            status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            instance.mark_as_received()
            return Response(ProductRequestSerializer(instance).data)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'], permission_classes=[permissions.IsAuthenticated])
    def report_damaged(self, request, pk=None):
        """Отметить поврежденные товары (для создателя запроса)"""
        instance = self.get_object()

        # Проверка прав доступа
        if instance.user != request.user:
            return Response({"error": "Вы можете отмечать брак только в своих запросах"},
                            status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            damaged_quantity = serializer.validated_data['damaged_quantity']
            instance.report_damaged(damaged_quantity)
            return Response(ProductRequestSerializer(instance).data)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def cart(self, request):
        """Получение запросов в корзине (pending и approved для не-магазинов)"""
        queryset = ProductRequest.objects.filter(
            user=request.user,
            for_store=False,
            status__in=['pending', 'approved']
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def calculate(self, request):
        """Расчет стоимости и бонусов для товара"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product = serializer.validated_data['product']
        quantity = serializer.validated_data['quantity']

        # Рассчитываем бонусы
        bonus_quantity = 0
        if product.is_bonus_eligible:
            bonus_quantity = quantity // 21

        # Рассчитываем стоимость
        total_price = product.calculate_total_price(quantity, bonus_quantity)

        result = {
            'product_id': product.id,
            'product_name': product.name,
            'quantity': quantity,
            'bonus_quantity': bonus_quantity,
            'price_per_unit': float(product.price),
            'total_price': float(total_price),
            'is_bonus_eligible': product.is_bonus_eligible
        }

        # Добавляем информацию о магазине, если указан
        store = serializer.validated_data.get('store')
        if store:
            result.update({
                'store_id': store.id,
                'store_name': store.name
            })

        return Response(result)

    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def pending_requests(self, request):
        """Получение всех ожидающих запросов (для администратора)"""
        queryset = ProductRequest.objects.filter(status='pending')
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def history(self, request):
        """История запросов пользователя"""
        queryset = ProductRequest.objects.filter(user=request.user)

        # Фильтрация по статусу
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Фильтрация по типу (для магазина или нет)
        for_store = request.query_params.get('for_store')
        if for_store is not None:
            queryset = queryset.filter(for_store=for_store.lower() == 'true')

        # Фильтрация по магазину
        store_id = request.query_params.get('store_id')
        if store_id:
            queryset = queryset.filter(store_id=store_id)

        # Пагинация
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


    @swagger_auto_schema(
        method='post',
        request_body=BulkProductRequestSerializer,
        operation_summary="Групповой запрос на товары",
        operation_description="Создаёт несколько заявок на товары за один раз. Поддерживает запросы для магазина или себя.",
        responses={201: ProductRequestSerializer(many=True)}
    )
    @action(detail=False, methods=["post"], url_path="bulk_create", permission_classes=[permissions.IsAuthenticated])
    def bulk_create(self, request):
        """
        Групповой запрос: создание сразу нескольких ProductRequest.
        """
        serializer = BulkProductRequestSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        instances = serializer.save(user=request.user)

        return Response(ProductRequestSerializer(instances, many=True).data, status=status.HTTP_201_CREATED)