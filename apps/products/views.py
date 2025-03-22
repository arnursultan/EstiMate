from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import F
from .models import Product
from .serializers import ProductSerializer, ProductAdminSerializer, ProductPartnerSerializer


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Разрешение, позволяющее только администраторам изменять объекты.
    Остальные пользователи имеют доступ только для чтения.
    """

    def has_permission(self, request, view):
        # Разрешить GET, HEAD, OPTIONS всем пользователям
        if request.method in permissions.SAFE_METHODS:
            return True
        # Разрешить изменения только администраторам
        return request.user and request.user.is_authenticated and request.user.role == 'admin'


class ProductViewSet(viewsets.ModelViewSet):
    """
    API для управления товарами в каталоге.
    Админы могут создавать, обновлять и удалять товары.
    Партнеры имеют доступ только для чтения.
    """
    queryset = Product.objects.filter(is_active=True)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_bonus']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'price', 'created_at']
    permission_classes = [permissions.IsAuthenticated, IsAdminOrReadOnly]

    def get_serializer_class(self):
        if self.request.user.role == 'admin':
            return ProductAdminSerializer
        return ProductPartnerSerializer

    def perform_create(self, serializer):
        serializer.save()

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def update_quantity(self, request, pk=None):
        """
        Обновление количества товара на складе (только для админов).
        """
        if request.user.role != 'admin':
            return Response(
                {"error": "Только администратор может обновлять количество товаров"},
                status=status.HTTP_403_FORBIDDEN
            )

        product = self.get_object()
        quantity = request.data.get('quantity')

        try:
            quantity = int(quantity)
            if quantity < 0:
                return Response(
                    {"error": "Количество не может быть отрицательным"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            product.quantity = quantity
            product.save()

            return Response(
                {"message": f"Количество товара '{product.name}' обновлено до {quantity}"},
                status=status.HTTP_200_OK
            )
        except (ValueError, TypeError):
            return Response(
                {"error": "Количество должно быть целым числом"},
                status=status.HTTP_400_BAD_REQUEST
            )