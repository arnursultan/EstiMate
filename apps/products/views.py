from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Product, PartnerInventory
from .serializers import (
    ProductSerializer,
    ProductListSerializer,
    PartnerInventorySerializer, # Добавили
    PartnerInventoryDetailSerializer # Добавили
)
# Импортируем разрешения из users
from apps.users.permissions import IsAdminUser, IsPartnerUser, IsInventoryOwnerOrAdmin
from django.shortcuts import get_object_or_404 # Добавим
import logging # Добавим
from django.core.exceptions import PermissionDenied


logger = logging.getLogger(__name__) # Добавим

class ProductViewSet(viewsets.ModelViewSet):
    """
    Представление для работы с товарами
    """
    # queryset определяется в get_queryset
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_bonus', 'is_active'] # is_deleted фильтруется в get_queryset
    search_fields = ['name', 'description']
    ordering_fields = ['price', 'created_at', 'name', 'quantity'] # Добавили quantity
    ordering = ['name'] # Сортировка по умолчанию

    def get_queryset(self):
        user = self.request.user
        # По умолчанию показываем только активные и не удаленные
        queryset = Product.objects.filter(is_active=True, is_deleted=False)

        # Позволяем админу видеть неактивные/удаленные через параметры
        is_active_param = self.request.query_params.get('is_active')
        is_deleted_param = self.request.query_params.get('is_deleted')

        if user.role == 'admin':
            # Админ может запросить все товары
            if is_active_param is None and is_deleted_param is None:
                 # Если фильтры не указаны, админ видит активные и неудаленные (как все)
                 pass
            else:
                 # Если указан хотя бы один фильтр, админ видит все и фильтрует по запросу
                 queryset = Product.objects.all() # Начинаем со всех
                 if is_active_param is not None:
                      show_active = is_active_param.lower() == 'true'
                      queryset = queryset.filter(is_active=show_active)
                 if is_deleted_param is not None:
                      show_deleted = is_deleted_param.lower() == 'true'
                      queryset = queryset.filter(is_deleted=show_deleted)

        # Другие пользователи видят только активные и неудаленные
        return queryset


    def get_serializer_class(self):
        if self.action == 'list':
            return ProductListSerializer
        return ProductSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy',
                           'activate', 'deactivate', 'soft_delete', 'restore',
                           'upload_image']:
            return [IsAdminUser()] # Только админ может менять каталог
        return [permissions.IsAuthenticated()] # Все остальные могут смотреть

    # Действия activate, deactivate, upload_image остаются как были

    # --- НОВЫЕ ДЕЙСТВИЯ SOFT DELETE / RESTORE ---
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def soft_delete(self, request, pk=None):
        """Мягкое удаление товара"""
        product = get_object_or_404(Product, pk=pk) # Ищем среди неудаленных
        if product.is_deleted: # На всякий случай
             return Response({"detail": "Товар уже удален"}, status=status.HTTP_400_BAD_REQUEST)

        if product.soft_delete():
            logger.info(f"Администратор {request.user.email} удалил (мягко) товар {product.name}")
            return Response({"detail": "Товар успешно помечен как удаленный"}, status=status.HTTP_200_OK)
        else:
             return Response({"detail": "Не удалось удалить товар"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def restore(self, request, pk=None):
        """Восстановление мягко удаленного товара"""
        try:
             # Ищем среди всех с помощью _base_manager
            product = Product._base_manager.get(pk=pk)
        except Product.DoesNotExist:
            return Response({"detail": "Товар не найден"}, status=status.HTTP_404_NOT_FOUND)

        if not product.is_deleted:
            return Response({"detail": "Товар не был удален"}, status=status.HTTP_400_BAD_REQUEST)

        if product.restore():
            logger.info(f"Администратор {request.user.email} восстановил товар {product.name}")
            return Response(ProductSerializer(product, context={'request': request}).data, status=status.HTTP_200_OK) # Возвращаем данные
        else:
             return Response({"detail": "Не удалось восстановить товар"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # --- Actions для заказов ---
    # available_products_for_store - удаляем, т.к. есть products_for_store_orders
    # @action(detail=False, methods=['get'])
    # def available_products_for_store(self, request): ...

    @action(detail=False, methods=['get'], permission_classes=[IsPartnerUser])
    def products_for_admin_orders(self, request):
        """
        Получить список товаров для заказа у администратора (из Product).
        """
        # Используем get_queryset текущего ViewSet, который уже фильтрует
        # активные и неудаленные товары
        products = self.filter_queryset(self.get_queryset().filter(quantity__gt=0)) # Только те, что в наличии

        product_list = []
        for product in products:
            image_url = None
            if product.image:
                 try: # Добавим try-except для build_absolute_uri
                      image_url = request.build_absolute_uri(product.image.url)
                 except:
                      image_url = product.image.url # Fallback

            product_list.append({
                'id': product.id, # ID Товара
                'name': product.name,
                'description': product.description,
                'price': float(product.price),
                'available_quantity': product.quantity, # Количество на складе админа
                'image_url': image_url,
                'is_bonus': product.is_bonus
            })

        return Response(product_list)

    @action(detail=False, methods=['get'], permission_classes=[IsPartnerUser])
    def products_for_store_orders(self, request):
        """
        Получить список товаров из инвентаря партнера для заказа в магазин.
        Возвращает ID записи инвентаря.
        """
        user = request.user
        # Получаем только активные и неудаленные товары из инвентаря партнера с количеством > 0
        inventory_items = PartnerInventory.objects.filter(
            partner=user,
            quantity__gt=0,
            product__is_active=True, # Доп. проверка на активность товара
            product__is_deleted=False # Доп. проверка на удаление товара
        ).select_related('product') # Оптимизация

        # Применяем фильтры поиска/сортировки если они есть в запросе
        # inventory_items = self.filter_queryset(inventory_items) # Нельзя, т.к. фильтры для Product

        available_products = []
        for item in inventory_items:
            product = item.product
            image_url = None
            if product.image:
                 try:
                      image_url = request.build_absolute_uri(product.image.url)
                 except:
                      image_url = product.image.url # Fallback

            available_products.append({
                'inventory_id': item.id,  # ID записи в таблице инвентаря партнера <--- ВАЖНО
                'product_id': product.id,  # ID в общем каталоге (для информации)
                'name': product.name,
                'description': product.description,
                'price': float(product.price),
                'available_quantity': item.quantity, # Количество у партнера
                'image_url': image_url,
                'is_bonus': product.is_bonus
            })

        return Response(available_products)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


# --- НОВЫЙ ViewSet ---
class PartnerInventoryViewSet(viewsets.ModelViewSet):
    """
    Представление для работы с инвентарем партнера
    """
    serializer_class = PartnerInventorySerializer # Используем базовый для CRUD
    permission_classes = [permissions.IsAuthenticated] # Общее разрешение
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    # Фильтруем по ID товара или по флагу бонуса связанного товара
    filterset_fields = ['product', 'product__is_bonus']
    search_fields = ['product__name'] # Поиск по имени связанного товара
    ordering_fields = ['quantity', 'created_at', 'product__name'] # Добавим сортировку по имени товара
    ordering = ['product__name'] # По умолчанию сортируем по товару

    def get_queryset(self):
        user = self.request.user
        queryset = PartnerInventory.objects.select_related('partner', 'product') # Оптимизация

        if user.role == 'admin':
            # Админ видит инвентарь всех партнеров
            pass
        elif user.role == 'partner':
            # Партнер видит только свой инвентарь
            queryset = queryset.filter(partner=user)
        else:
            return PartnerInventory.objects.none()

        # Фильтруем по связанному продукту (активен и не удален)
        queryset = queryset.filter(product__is_active=True, product__is_deleted=False)

        return queryset

    def get_serializer_class(self):
        # Для чтения используем детальный сериализатор
        if self.action in ['list', 'retrieve']:
            return PartnerInventoryDetailSerializer
        # Для создания/обновления используем базовый
        return PartnerInventorySerializer

    def get_permissions(self):
        # Админ может всё. Партнер может читать свой инвентарь, создавать записи (?).
        # Партнер НЕ должен иметь возможность напрямую менять количество через этот API.
        # Количество должно меняться через заказы.
        if self.action == 'create':
             # Запрещаем создание через API напрямую? Или разрешаем админу?
             return [IsAdminUser()] # Только админ может создать запись (например, начальный остаток)
        elif self.action in ['update', 'partial_update', 'destroy']:
             # Используем кастомное разрешение
             return [IsInventoryOwnerOrAdmin()]
        # list, retrieve доступны всем аутентифицированным (фильтрация в get_queryset)
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
         # Админ должен указать партнера при создании
         if self.request.user.role == 'admin':
              # Партнер должен быть в данных запроса, валидация в сериализаторе
              serializer.save()
         else:
             # Эта ветка не должна вызываться из-за get_permissions, но на всякий случай
             raise PermissionDenied("Только администратор может создавать записи инвентаря.")


    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context