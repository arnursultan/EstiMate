from drf_yasg.utils import swagger_auto_schema
from rest_framework import viewsets, permissions, status, filters, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.views import APIView

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
from apps.users.models import User


logger = logging.getLogger(__name__) # Добавим

class ProductViewSet(viewsets.ModelViewSet):
    """
    Представление для работы с товарами (Каталог)
    """
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated] # Базовое, уточняется ниже
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_bonus', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['price', 'created_at', 'name', 'quantity']
    ordering = ['name']

    def get_queryset(self):
        user = self.request.user
        queryset = Product.objects.filter(is_deleted=False)

        if user.role == 'admin':
            is_active_param = self.request.query_params.get('is_active')
            is_deleted_param = self.request.query_params.get('is_deleted')
            if is_active_param is None and is_deleted_param is None:
                 queryset = queryset.filter(is_active=True)
            else:
                 # Если есть фильтры, админ ищет по всем (включая удаленные, если запрошено)
                 base_qs = Product.objects.all() if is_deleted_param == 'true' else Product.objects.filter(is_deleted=False)
                 if is_active_param is not None:
                      show_active = is_active_param.lower() == 'true'
                      base_qs = base_qs.filter(is_active=show_active)
                 if is_deleted_param is not None: # Повторно, но нужно для логики выше
                      show_deleted = is_deleted_param.lower() == 'true'
                      # Фильтр is_deleted уже применен при выборе base_qs
                      if not show_deleted: # Если запросили is_deleted=false явно
                           base_qs = base_qs.filter(is_deleted=False)
                 queryset = base_qs
        else:
            queryset = queryset.filter(is_active=True)

        return queryset.order_by(*self.ordering) # Применяем сортировку

    def get_serializer_class(self):
        if self.action == 'list':
            return ProductListSerializer
        return ProductSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy',
                           'activate', 'deactivate', 'soft_delete', 'restore',
                           'upload_image']:
            return [IsAdminUser()]
        return [permissions.IsAuthenticated()]

    # --- Actions для товаров (activate, deactivate, soft_delete, restore, upload_image) ---
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def activate(self, request, pk=None):
        product = get_object_or_404(Product, pk=pk, is_deleted=False)
        if product.is_active: return Response({"detail": "Товар уже активен"}, status=status.HTTP_400_BAD_REQUEST)
        product.is_active = True; product.save(update_fields=['is_active']); logger.info(f"Админ {request.user.email} активировал товар ID {pk}")
        return Response(ProductSerializer(product, context={'request': request}).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def deactivate(self, request, pk=None):
        product = get_object_or_404(Product, pk=pk, is_deleted=False)
        if not product.is_active: return Response({"detail": "Товар уже деактивирован"}, status=status.HTTP_400_BAD_REQUEST)
        product.is_active = False; product.save(update_fields=['is_active']); logger.info(f"Админ {request.user.email} деактивировал товар ID {pk}")
        return Response(ProductSerializer(product, context={'request': request}).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def upload_image(self, request, pk=None):
        product = get_object_or_404(Product, pk=pk)
        file = request.data.get('image')
        if not file: return Response({"detail": "Файл изображения не предоставлен"}, status=status.HTTP_400_BAD_REQUEST)
        product.image = file; product.save(); logger.info(f"Админ {request.user.email} загрузил изображение для товара ID {pk}")
        return Response(ProductSerializer(product, context={'request': request}).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def soft_delete(self, request, pk=None):
        product = get_object_or_404(Product, pk=pk)
        if product.is_deleted: return Response({"detail": "Товар уже удален"}, status=status.HTTP_400_BAD_REQUEST)
        if product.soft_delete(): logger.info(f"Админ {request.user.email} удалил (мягко) товар {product.name}"); return Response({"detail": "Товар успешно помечен как удаленный"}, status=status.HTTP_200_OK)
        else: return Response({"detail": "Не удалось удалить товар"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def restore(self, request, pk=None):
        try: product = Product._base_manager.get(pk=pk)
        except Product.DoesNotExist: return Response({"detail": "Товар не найден"}, status=status.HTTP_404_NOT_FOUND)
        if not product.is_deleted: return Response({"detail": "Товар не был удален"}, status=status.HTTP_400_BAD_REQUEST)
        if product.restore(): logger.info(f"Админ {request.user.email} восстановил товар {product.name}"); return Response(ProductSerializer(product, context={'request': request}).data, status=status.HTTP_200_OK)
        else: return Response({"detail": "Не удалось восстановить товар"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # --- Actions для получения списков товаров для заказа ---
    @action(detail=False, methods=['get'], permission_classes=[IsPartnerUser])
    def products_for_admin_orders(self, request):
        """(Партнер) Получить список товаров для заказа у администратора (из Product)."""
        products = self.filter_queryset(self.get_queryset().filter(is_active=True, quantity__gt=0)) # Только активные и в наличии
        product_list = []
        for product in products:
            image_url = None
            if product.image:
                 try: image_url = request.build_absolute_uri(product.image.url)
                 except: image_url = product.image.url
            product_list.append({'id': product.id,'name': product.name,'description': product.description,'price': float(product.price),'available_quantity': product.quantity,'image_url': image_url,'is_bonus': product.is_bonus})
        return Response(product_list)

    @action(detail=False, methods=['get'], permission_classes=[IsPartnerUser])
    def products_for_store_orders(self, request):
        """(Партнер) Получить список товаров из своего инвентаря для заказа в магазин."""
        user = request.user
        inventory_items = PartnerInventory.objects.filter(
            partner=user, quantity__gt=0, product__is_active=True, product__is_deleted=False
        ).select_related('product')
        available_products = []
        for item in inventory_items:
            product = item.product
            image_url = None
            if product.image:
                 try: image_url = request.build_absolute_uri(product.image.url)
                 except: image_url = product.image.url
            available_products.append({'inventory_id': item.id,'product_id': product.id,'name': product.name,'description': product.description,'price': float(product.price),'available_quantity': item.quantity,'image_url': image_url,'is_bonus': product.is_bonus})
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


class PartnerInventoryListView(APIView):
    """
    Получение списка инвентаря для конкретного партнера (только для админа).
    Доступ по URL: /api/products/inventory/partner/{partner_pk}/
    """
    permission_classes = [IsAdminUser] # Только администраторы

    @swagger_auto_schema(
        operation_summary="Инвентарь конкретного партнера (Админ)",
        operation_description="Возвращает список записей инвентаря для указанного партнера.",
        responses={200: PartnerInventoryDetailSerializer(many=True)}
    )
    def get(self, request, partner_pk, format=None):
        # Находим партнера или возвращаем 404
        partner = get_object_or_404(User, pk=partner_pk, role='partner')
        logger.info(f"Админ {request.user.id} запрашивает инвентарь партнера {partner_pk}")

        # Получаем его инвентарь (только активные, не удаленные товары)
        inventory_items = PartnerInventory.objects.filter(
            partner=partner,
            product__is_active=True,
            product__is_deleted=False
        ).select_related('product').order_by('product__name') # Оптимизация + сортировка

        # Применяем фильтры из запроса (например, ?product__is_bonus=true)
        # Создаем временный FilterSet или фильтруем вручную
        filtered_inventory = self._filter_inventory(request, inventory_items)


        serializer = PartnerInventoryDetailSerializer(filtered_inventory, many=True, context={'request': request})
        return Response(serializer.data)

    def _filter_inventory(self, request, queryset):
         # Простая ручная фильтрация для примера
         # Можно интегрировать DjangoFilterBackend, если нужно больше фильтров
         product_id = request.query_params.get('product')
         is_bonus = request.query_params.get('product__is_bonus')

         if product_id:
              try:
                   queryset = queryset.filter(product_id=int(product_id))
              except (ValueError, TypeError):
                   pass # Игнорируем неверный ID
         if is_bonus is not None:
              is_bonus_bool = is_bonus.lower() == 'true'
              queryset = queryset.filter(product__is_bonus=is_bonus_bool)

         # Добавить поиск и сортировку, если необходимо

         return queryset

# --- View для "Моего инвентаря" (для партнера) ---
class MyInventoryListView(generics.ListAPIView):
    """
    Представление для получения списка ИНВЕНТАРЯ ТЕКУЩЕГО ПАРТНЕРА.
    Доступ по /api/products/my-inventory/
    """
    serializer_class = PartnerInventoryDetailSerializer
    permission_classes = [IsPartnerUser] # Только партнеры
    # Используем стандартные бэкенды DRF для фильтрации/поиска/сортировки
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['product__is_bonus'] # Фильтр по товару (is_bonus)
    search_fields = ['product__name'] # Поиск по названию товара
    ordering_fields = ['quantity', 'created_at', 'product__name']
    ordering = ['product__name']

    @swagger_auto_schema(
        operation_summary="Мой инвентарь (Партнер)",
        operation_description="Возвращает список товаров в инвентаре текущего партнера.",
    )
    def get_queryset(self):
        user = self.request.user
        queryset = PartnerInventory.objects.filter(
            partner=user,
            product__is_active=True,
            product__is_deleted=False
        ).select_related('partner', 'product')
        # ordering применяется автоматически бэкендом
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
