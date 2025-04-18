from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Product, PartnerInventory
from .serializers import (
    ProductSerializer,
    PartnerInventorySerializer,
    ProductListSerializer
)
from .permissions import IsAdminUser


class ProductViewSet(viewsets.ModelViewSet):
    """
    Представление для работы с товарами
    """
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_bonus', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['price', 'created_at', 'name']

    def get_serializer_class(self):
        if self.action == 'list':
            return ProductListSerializer
        return ProductSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'activate', 'deactivate', 'upload_image']:
            return [IsAdminUser()]
        return [permissions.IsAuthenticated()]

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def activate(self, request, pk=None):
        """Активация товара"""
        product = self.get_object()

        if product.is_active:
            return Response(
                {"detail": "Товар уже активен"},
                status=status.HTTP_400_BAD_REQUEST
            )

        product.is_active = True
        product.save()

        return Response(
            {"detail": "Товар успешно активирован"},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def deactivate(self, request, pk=None):
        """Деактивация товара"""
        product = self.get_object()

        if not product.is_active:
            return Response(
                {"detail": "Товар уже деактивирован"},
                status=status.HTTP_400_BAD_REQUEST
            )

        product.is_active = False
        product.save()

        return Response(
            {"detail": "Товар успешно деактивирован"},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def upload_image(self, request, pk=None):
        """Загрузка изображения товара"""
        product = self.get_object()
        file = request.data.get('image')

        if not file:
            return Response(
                {"detail": "Файл изображения не предоставлен"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Сохраняем изображение непосредственно в модели Product
        product.image = file
        product.save()

        return Response(
            ProductSerializer(product, context={'request': request}).data,
            status=status.HTTP_200_OK
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    # Добавляем в apps/products/views.py

    @action(detail=False, methods=['get'])
    def available_products_for_store(self, request):
        """
        Получить список товаров из инвентаря партнера, доступных для заказа в магазин.

        Этот эндпоинт показывает только товары из инвентаря текущего партнера с количеством > 0.
        Для удобства работы с фронтенд приложением, товары имеют информацию о доступном количестве.
        """
        user = request.user
        if user.role != 'partner':
            return Response(
                {"error": "Только партнеры могут получить список товаров из своего инвентаря"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Получаем только товары из инвентаря партнера с количеством > 0
        inventory_items = PartnerInventory.objects.filter(
            partner=user,
            quantity__gt=0
        ).select_related('product')

        # Формируем список доступных товаров
        available_products = []
        for item in inventory_items:
            available_products.append({
                'id': item.product.id,  # Используем глобальный ID продукта
                'name': item.product.name,
                'description': item.product.description,
                'price': float(item.product.price),
                'available_quantity': item.quantity,
                'image_url': request.build_absolute_uri(item.product.image.url) if item.product.image else None,
                'is_bonus': item.product.is_bonus
            })

        return Response(available_products)

    @action(detail=False, methods=['get'])
    def products_for_admin_orders(self, request):
        """
        Получить список товаров для заказа у администратора.
        Этот эндпоинт возвращает товары из общего каталога для заказа 'admin_to_partner'.
        """
        if request.user.role != 'partner':
            return Response(
                {"error": "Только партнеры могут просматривать эти товары"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Получаем только активные товары с количеством > 0 из общего каталога
        products = Product.objects.filter(is_active=True, quantity__gt=0)

        product_list = []
        for product in products:
            product_list.append({
                'id': product.id,
                'name': product.name,
                'description': product.description,
                'price': float(product.price),
                'available_quantity': product.quantity,
                'image_url': request.build_absolute_uri(product.image.url) if product.image else None,
                'is_bonus': product.is_bonus
            })

        return Response(product_list)

    @action(detail=False, methods=['get'])
    def products_for_store_orders(self, request):
        """
        Получить список товаров из инвентаря партнера для заказа в магазин.
        Важно: этот эндпоинт возвращает ID записей инвентаря (а не ID товаров).
        """
        user = request.user
        if user.role != 'partner':
            return Response(
                {"error": "Только партнеры могут получить список товаров из своего инвентаря"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Получаем только товары из инвентаря партнера с количеством > 0
        inventory_items = PartnerInventory.objects.filter(
            partner=user,
            quantity__gt=0
        ).select_related('product')

        # Формируем список доступных товаров
        available_products = []
        for item in inventory_items:
            product = item.product
            available_products.append({
                'inventory_id': item.id,  # ID записи в таблице инвентаря партнера
                'product_id': product.id,  # Для информации - ID в общем каталоге
                'name': product.name,
                'description': product.description,
                'price': float(product.price),
                'available_quantity': item.quantity,
                'image_url': request.build_absolute_uri(product.image.url) if product.image else None,
                'is_bonus': product.is_bonus
            })

        return Response(available_products)

class PartnerInventoryViewSet(viewsets.ModelViewSet):
    """
    Представление для работы с инвентарем партнера
    """
    serializer_class = PartnerInventorySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['product__is_bonus']
    search_fields = ['product__name']
    ordering_fields = ['quantity', 'created_at']

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return PartnerInventory.objects.all()
        return PartnerInventory.objects.filter(partner=user)

    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated()]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
