from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Category, Product
from .serializers import CategorySerializer, ProductSerializer


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_staff


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            self.permission_classes = [IsAdminUser]
        return super().get_permissions()

    @swagger_auto_schema(
        operation_description="Получить список всех категорий",
        responses={200: CategorySerializer(many=True)}
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Создать новую категорию (только администратор)",
        request_body=CategorySerializer,
        responses={201: CategorySerializer}
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'price', 'quantity', 'created_at']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            self.permission_classes = [IsAdminUser]
        return super().get_permissions()

    @swagger_auto_schema(
        operation_description="Получить список всех продуктов",
        responses={200: ProductSerializer(many=True)}
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Создать новый продукт (только администратор)",
        request_body=ProductSerializer,
        responses={201: ProductSerializer}
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Получить детали продукта по ID",
        responses={200: ProductSerializer}
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Обновить продукт (только администратор)",
        request_body=ProductSerializer,
        responses={200: ProductSerializer}
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Частично обновить продукт (только администратор)",
        request_body=ProductSerializer,
        responses={200: ProductSerializer}
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Удалить продукт (только администратор)",
        responses={204: "Продукт успешно удален"}
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @swagger_auto_schema(
        method='post',
        operation_description="Добавить количество товара на склад (только администратор)",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['quantity_to_add'],
            properties={
                'quantity_to_add': openapi.Schema(type=openapi.TYPE_INTEGER, description='Количество товара для добавления')
            }
        ),
        responses={200: ProductSerializer}
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def add_quantity(self, request, pk=None):
        product = self.get_object()
        quantity_to_add = request.data.get('quantity_to_add', 0)

        try:
            quantity_to_add = int(quantity_to_add)
            if quantity_to_add <= 0:
                return Response({"error": "Количество добавляемого товара должно быть положительным числом"}, status=status.HTTP_400_BAD_REQUEST)

            product.quantity += quantity_to_add
            product.save()

            return Response(ProductSerializer(product).data)

        except ValueError:
            return Response({"error": "Некорректное значение для количества товара"}, status=status.HTTP_400_BAD_REQUEST)
