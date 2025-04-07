from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import ProductRequest
from .serializers import (
    ProductRequestSerializer,
    AdminProductRequestStatusSerializer,
    PartnerMarkReceivedSerializer,
    ReportDamagedSerializer,
    SelfRequestSerializer,
    StoreRequestSerializer
)
from apps.products.models import Product, PartnerProduct
from apps.stores.models import Store
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_staff


class ProductRequestViewSet(viewsets.ModelViewSet):
    serializer_class = ProductRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'payment_method', 'request_type', 'store', 'product']
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
        elif self.action == 'create_self_request':
            return SelfRequestSerializer
        elif self.action == 'create_store_request':
            return StoreRequestSerializer
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

    @swagger_auto_schema(
        method='post',
        request_body=SelfRequestSerializer,
        responses={201: ProductRequestSerializer()}
    )
    @action(detail=False, methods=['post'])
    def create_self_request(self, request):
        """Создать запрос 'для себя' (SELF)"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product_id = serializer.validated_data['product_id']
        quantity = serializer.validated_data['quantity']

        try:
            product = Product.objects.get(id=product_id, is_active=True)

            # Создаем запрос SELF
            product_request = ProductRequest.objects.create(
                product=product,
                user=request.user,
                quantity=quantity,
                request_type='SELF',
                status='pending'
            )

            return Response(
                ProductRequestSerializer(product_request).data,
                status=status.HTTP_201_CREATED
            )
        except Product.DoesNotExist:
            return Response(
                {"error": "Указанный товар не найден или неактивен"},
                status=status.HTTP_404_NOT_FOUND
            )

    @swagger_auto_schema(
        method='post',
        request_body=StoreRequestSerializer,
        responses={201: ProductRequestSerializer()}
    )
    @action(detail=False, methods=['post'])
    def create_store_request(self, request):
        """Создать запрос 'для магазина' (STORE)"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        partner_product_id = serializer.validated_data['partner_product_id']
        store_id = serializer.validated_data['store_id']
        quantity = serializer.validated_data['quantity']

        try:
            # Проверяем, что указан товар из личного каталога
            partner_product = PartnerProduct.objects.get(id=partner_product_id, partner=request.user)

            # Проверяем, что товара достаточно
            if partner_product.remaining_quantity < quantity:
                return Response(
                    {"error": f"Недостаточно товара в вашем каталоге. Доступно: {partner_product.remaining_quantity}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Проверяем магазин
            store = Store.objects.get(id=store_id, status='approved', is_active=True)

            # Создаем запрос STORE
            product_request = ProductRequest.objects.create(
                product=partner_product.product,  # Используем глобальный товар
                user=request.user,
                quantity=quantity,
                request_type='STORE',
                store=store,
                partner_product=partner_product,
                payment_method='debt',  # В новой версии только "в долг"
                status='pending'
            )

            return Response(
                ProductRequestSerializer(product_request).data,
                status=status.HTTP_201_CREATED
            )
        except PartnerProduct.DoesNotExist:
            return Response(
                {"error": "Указанный товар не найден в вашем каталоге"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Store.DoesNotExist:
            return Response(
                {"error": "Указанный магазин не найден или не активен"},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def pending_self_requests(self, request):
        """Получение всех ожидающих запросов 'для себя' (для администратора)"""
        queryset = ProductRequest.objects.filter(status='pending', request_type='SELF')
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def pending_store_requests(self, request):
        """Получение всех ожидающих запросов 'для магазина' (для администратора)"""
        queryset = ProductRequest.objects.filter(status='pending', request_type='STORE')
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def self_requests(self, request):
        """Получение всех запросов 'для себя' текущего пользователя"""
        queryset = ProductRequest.objects.filter(user=request.user, request_type='SELF')
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def store_requests(self, request):
        """Получение всех запросов 'для магазина' текущего пользователя"""
        queryset = ProductRequest.objects.filter(user=request.user, request_type='STORE')
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    # Добавить в apps/orders/views.py

    @swagger_auto_schema(
        method='post',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'items': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'product_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'quantity': openapi.Schema(type=openapi.TYPE_INTEGER, minimum=1)
                        }
                    )
                )
            },
            required=['items']
        ),
        responses={201: "Запросы созданы успешно"}
    )
    @action(detail=False, methods=["post"], url_path="bulk_self_request")
    def bulk_self_request(self, request):
        """
        Групповой запрос товаров 'для себя' (SELF).
        """
        items = request.data.get('items', [])

        if not items:
            return Response(
                {"error": "Необходимо указать хотя бы один товар"},
                status=status.HTTP_400_BAD_REQUEST
            )

        created_requests = []
        errors = []

        for item in items:
            product_id = item.get('product_id')
            quantity = item.get('quantity', 1)

            # Валидация данных
            if not product_id:
                errors.append({"error": "Не указан ID товара", "item": item})
                continue

            if quantity <= 0:
                errors.append({"error": "Количество должно быть положительным числом", "item": item})
                continue

            try:
                product = Product.objects.get(id=product_id, is_active=True)

                # Создаем запрос SELF
                product_request = ProductRequest.objects.create(
                    product=product,
                    user=request.user,
                    quantity=quantity,
                    request_type='SELF',
                    status='pending'
                )

                created_requests.append({
                    "id": product_request.id,
                    "product_name": product.name,
                    "quantity": quantity
                })

            except Product.DoesNotExist:
                errors.append({"error": f"Товар с ID {product_id} не найден или неактивен", "item": item})

        return Response({
            "created_requests": created_requests,
            "errors": errors,
            "success": len(created_requests) > 0
        }, status=status.HTTP_201_CREATED if created_requests else status.HTTP_400_BAD_REQUEST)

    # Добавить в apps/orders/views.py

    @swagger_auto_schema(
        method='post',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'store_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'items': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'partner_product_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'quantity': openapi.Schema(type=openapi.TYPE_INTEGER, minimum=1)
                        }
                    )
                )
            },
            required=['store_id', 'items']
        ),
        responses={201: "Запросы созданы успешно"}
    )
    @action(detail=False, methods=["post"], url_path="bulk_store_request")
    def bulk_store_request(self, request):
        """
        Групповой запрос товаров 'для магазина' (STORE).
        """
        store_id = request.data.get('store_id')
        items = request.data.get('items', [])

        if not store_id:
            return Response(
                {"error": "Необходимо указать ID магазина"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not items:
            return Response(
                {"error": "Необходимо указать хотя бы один товар"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Проверяем существование и статус магазина
        try:
            store = Store.objects.get(id=store_id, status='approved', is_active=True)
        except Store.DoesNotExist:
            return Response(
                {"error": "Указанный магазин не найден или не активен"},
                status=status.HTTP_404_NOT_FOUND
            )

        created_requests = []
        errors = []

        for item in items:
            partner_product_id = item.get('partner_product_id')
            quantity = item.get('quantity', 1)

            # Валидация данных
            if not partner_product_id:
                errors.append({"error": "Не указан ID товара из каталога", "item": item})
                continue

            if quantity <= 0:
                errors.append({"error": "Количество должно быть положительным числом", "item": item})
                continue

            try:
                partner_product = PartnerProduct.objects.get(id=partner_product_id, partner=request.user)

                # Проверка достаточного количества товара
                if partner_product.remaining_quantity < quantity:
                    errors.append({
                        "error": f"Недостаточно товара '{partner_product.product.name}' в каталоге. Доступно: {partner_product.remaining_quantity}",
                        "item": item
                    })
                    continue

                # Создаем запрос STORE
                product_request = ProductRequest.objects.create(
                    product=partner_product.product,
                    user=request.user,
                    quantity=quantity,
                    request_type='STORE',
                    store=store,
                    partner_product=partner_product,
                    payment_method='debt',
                    status='pending'
                )

                created_requests.append({
                    "id": product_request.id,
                    "product_name": partner_product.product.name,
                    "quantity": quantity
                })

            except PartnerProduct.DoesNotExist:
                errors.append({"error": f"Товар с ID {partner_product_id} не найден в вашем каталоге", "item": item})

        return Response({
            "store": {"id": store.id, "name": store.name},
            "created_requests": created_requests,
            "errors": errors,
            "success": len(created_requests) > 0
        }, status=status.HTTP_201_CREATED if created_requests else status.HTTP_400_BAD_REQUEST)

    # Добавляем в apps/orders/views.py

    @action(detail=True, methods=['post'])
    def confirm_receipt(self, request, pk=None):
        """Подтверждение получения товара партнером"""
        instance = self.get_object()

        # Проверяем, что товар принадлежит этому пользователю
        if instance.user != request.user:
            return Response(
                {"error": "Вы можете подтверждать получение только своих запросов"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Проверяем статус запроса
        if instance.status != 'approved':
            return Response(
                {"error": f"Товар в статусе '{instance.get_status_display()}' не может быть отмечен как полученный"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Отмечаем товар как полученный
            instance.status = 'received'
            instance.save()

            # Для запросов типа SELF создаем или обновляем товар в каталоге партнера
            if instance.request_type == 'SELF':
                from apps.products.models import PartnerProduct
                partner_product, created = PartnerProduct.objects.get_or_create(
                    partner=instance.user,
                    product=instance.product,
                    defaults={
                        'price': instance.product.price,
                        'quantity': 0
                    }
                )

                # Увеличиваем количество товара
                partner_product.quantity += instance.quantity
                if instance.bonus_quantity > 0:
                    partner_product.bonus_quantity += instance.bonus_quantity
                partner_product.save()

            return Response({
                "message": f"Товар '{instance.product.name}' успешно отмечен как полученный",
                "request": ProductRequestSerializer(instance).data
            })
        except Exception as e:
            return Response(
                {"error": f"Ошибка при подтверждении получения: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )