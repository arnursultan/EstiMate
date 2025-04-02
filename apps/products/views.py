from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.parsers import MultiPartParser, FormParser
from django.db.models import Q
from .models import Product
from .serializers import (
    ProductSerializer,
    ProductDetailSerializer,
    ProductQuantityUpdateSerializer,
    ProductBonusSerializer
)


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_staff


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_bonus_eligible']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'price', 'quantity', 'created_at']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProductDetailSerializer
        elif self.action == 'add_quantity':
            return ProductQuantityUpdateSerializer
        elif self.action == 'bonus_info':
            return ProductBonusSerializer
        return self.serializer_class

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'add_quantity']:
            self.permission_classes = [IsAdminUser]
        return super().get_permissions()

    def get_queryset(self):
        queryset = Product.objects.all()

        # Фильтрация по наличию товара
        in_stock = self.request.query_params.get('in_stock')
        if in_stock == 'true':
            queryset = queryset.filter(quantity__gt=0)
        elif in_stock == 'false':
            queryset = queryset.filter(quantity=0)

        # Фильтрация по цене
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')

        if min_price:
            try:
                min_price = float(min_price)
                queryset = queryset.filter(price__gte=min_price)
            except (ValueError, TypeError):
                pass

        if max_price:
            try:
                max_price = float(max_price)
                queryset = queryset.filter(price__lte=max_price)
            except (ValueError, TypeError):
                pass

        return queryset



    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def add_quantity(self, request, pk=None):
        """Добавление количества товара на склад"""
        product = self.get_object()
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            try:
                quantity_to_add = serializer.validated_data['quantity_to_add']
                product.add_quantity(quantity_to_add)
                return Response(ProductDetailSerializer(product).data)
            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def bonus_info(self, request, pk=None):
        """Расчет бонусов для товара"""
        product = self.get_object()
        serializer = ProductBonusSerializer(data=request.query_params)

        if serializer.is_valid():
            quantity = serializer.validated_data['quantity']

            # Рассчитываем бонусы только если товар участвует в бонусной программе
            bonus_count = product.calculate_bonus(quantity)
            bonus_value = bonus_count * product.price
            total_price = product.calculate_total_price(quantity, bonus_count)

            return Response({
                "product_id": product.id,
                "product_name": product.name,
                "is_bonus_eligible": product.is_bonus_eligible,
                "requested_quantity": quantity,
                "bonus_count": bonus_count,
                "bonus_value": float(bonus_value),
                "total_price_with_bonus": float(total_price)
            })
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """Получение товаров с низким остатком (менее 10 единиц)"""
        if not request.user.is_staff:
            return Response({"error": "Недостаточно прав для выполнения операции"},
                            status=status.HTTP_403_FORBIDDEN)

        low_stock_products = Product.objects.filter(quantity__gt=0, quantity__lt=10)
        serializer = self.get_serializer(low_stock_products, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def out_of_stock(self, request):
        """Получение отсутствующих товаров"""
        if not request.user.is_staff:
            return Response({"error": "Недостаточно прав для выполнения операции"},
                            status=status.HTTP_403_FORBIDDEN)

        out_of_stock_products = Product.objects.filter(quantity=0)
        serializer = self.get_serializer(out_of_stock_products, many=True)
        return Response(serializer.data)