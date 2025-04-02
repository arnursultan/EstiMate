from rest_framework import viewsets, permissions, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from apps.orders.models import ProductRequest
from .serializers import CartSerializer, CartReceivedSerializer, CartDamagedSerializer
import logging

logger = logging.getLogger(__name__)


class CartViewSet(viewsets.ModelViewSet):
    """Управление корзиной товаров"""
    serializer_class = CartSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status']
    ordering_fields = ['created_at', 'total_price']

    def get_queryset(self):
        """Возвращает элементы корзины текущего пользователя"""
        # Проверяем, не является ли это запросом для генерации схемы Swagger
        if getattr(self, 'swagger_fake_view', False):
            # Возвращаем пустой QuerySet для Swagger
            return ProductRequest.objects.none()

        # Обычная логика для реальных запросов
        return ProductRequest.objects.filter(
            user=self.request.user,
            for_store=False,
            status__in=['pending', 'approved']
        ).order_by('-created_at')


    def get_serializer_class(self):
        """Выбирает сериализатор в зависимости от действия"""
        if self.action == 'mark_received':
            return CartReceivedSerializer
        elif self.action == 'report_damaged':
            return CartDamagedSerializer
        return self.serializer_class

    def perform_create(self, serializer):
        """Создает запрос товара для себя (не для магазина)"""
        serializer.save(user=self.request.user, for_store=False)

    def destroy(self, request, *args, **kwargs):
        """Удаляет элемент из корзины"""
        instance = self.get_object()
        if instance.status != 'pending':
            return Response(
                {"error": "Удалять можно только запросы в статусе 'В ожидании'"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            self.perform_destroy(instance)
            return Response({"detail": "Элемент успешно удален из корзины"}, status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(f"Ошибка при удалении из корзины: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['patch'])
    def mark_received(self, request, pk=None):
        """Отметить товар как полученный"""
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)

        if serializer.is_valid():
            try:
                serializer.save()
                return Response(CartSerializer(instance).data)
            except Exception as e:
                logger.error(f"Ошибка при отметке товара как полученного: {str(e)}")
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'])
    def report_damaged(self, request, pk=None):
        """Отметить поврежденные товары"""
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)

        if serializer.is_valid():
            try:
                serializer.save()
                return Response(CartSerializer(instance).data)
            except Exception as e:
                logger.error(f"Ошибка при отметке поврежденных товаров: {str(e)}")
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Сводка по корзине"""
        queryset = self.get_queryset()

        # Подсчет общих показателей
        total_items = queryset.count()
        total_quantity = sum(item.quantity for item in queryset)
        total_bonus = sum(item.bonus_quantity for item in queryset)
        total_price = sum(float(item.total_price) for item in queryset)

        # Группировка по статусу
        pending_count = queryset.filter(status='pending').count()
        approved_count = queryset.filter(status='approved').count()

        return Response({
            "total_items": total_items,
            "total_quantity": total_quantity,
            "total_bonus": total_bonus,
            "total_price": total_price,
            "pending_count": pending_count,
            "approved_count": approved_count
        })