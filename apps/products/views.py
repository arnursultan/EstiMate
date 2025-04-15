from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Product, PartnerInventory, ProductImage
from .serializers import (
    ProductSerializer,
    PartnerInventorySerializer,
    ProductImageSerializer,
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
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'activate', 'deactivate']:
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
        product = self.get_object()
        file = request.data.get('image')
        is_primary = request.data.get('is_primary', False)

        if not file:
            return Response(
                {"detail": "Файл изображения не предоставлен"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Если это основное изображение, снимаем отметку с других изображений
        if is_primary:
            product.images.filter(is_primary=True).update(is_primary=False)

        image = ProductImage.objects.create(
            product=product,
            image=file,
            is_primary=is_primary
        )

        return Response(
            ProductImageSerializer(image).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['delete'], permission_classes=[IsAdminUser])
    def delete_image(self, request, pk=None):
        product = self.get_object()
        image_id = request.data.get('image_id')

        if not image_id:
            return Response(
                {"detail": "ID изображения не предоставлен"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            image = product.images.get(id=image_id)
            image.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ProductImage.DoesNotExist:
            return Response(
                {"detail": "Изображение не найдено"},
                status=status.HTTP_404_NOT_FOUND
            )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


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