import uuid
from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.views import APIView
from django.utils import timezone
from django.core.exceptions import ValidationError

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
from apps.stores.models import Store, StoreDebt
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_staff


class ProductRequestViewSet(viewsets.ModelViewSet):
    serializer_class = ProductRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'payment_method', 'request_type', 'store', 'product', 'batch_id']
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

        # Проверяем, что это SELF запрос
        if instance.request_type != 'SELF':
            return Response(
                {"error": "Можно обновлять статус только для запросов типа SELF"},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            # Сохраняем предыдущий статус
            old_status = instance.status
            new_status = serializer.validated_data['status']

            # Если статус меняется с pending на approved
            if old_status == 'pending' and new_status == 'approved':
                # Товар уже был уменьшен из каталога админа при создании запроса
                # Теперь просто меняем статус на approved
                serializer.save()

                # После сохранения статуса, добавляем товар в каталог партнера
                from apps.products.models import PartnerProduct
                partner_product, created = PartnerProduct.objects.get_or_create(
                    partner=instance.user,
                    product=instance.product,
                    defaults={
                        'price': instance.product.price,
                        'quantity': 0
                    }
                )

                # Увеличиваем количество товара у партнера
                partner_product.quantity += instance.quantity
                if instance.bonus_quantity > 0:
                    partner_product.bonus_quantity += instance.bonus_quantity
                partner_product.save()

                # Обновляем статистику
                from apps.finance.services import update_partner_daily_stats
                update_partner_daily_stats(instance.user, instance.created_at.date())

            # Если статус меняется с pending на rejected
            elif old_status == 'pending' and new_status == 'rejected':
                # Возвращаем товар в каталог администратора
                instance.product.add_quantity(instance.quantity)
                serializer.save()
            else:
                # Любой другой переход статусов
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

            # Обновляем статистику
            from apps.finance.services import update_partner_daily_stats
            if instance.store:
                from apps.finance.services import update_store_daily_stats
                update_store_daily_stats(instance.store, instance.created_at.date())
            update_partner_daily_stats(instance.user, instance.created_at.date())

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

            # Проверяем наличие достаточного количества товара у админа
            if product.quantity < quantity:
                return Response(
                    {"error": f"Недостаточно товара в каталоге. Доступно: {product.quantity}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Уменьшаем количество товара у админа
            product.reduce_quantity(quantity)

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

            # Уменьшаем количество товара в каталоге партнера
            partner_product.update_quantity(quantity, operation='subtract')

            # Создаем запрос STORE (со статусом approved по новой логике)
            product_request = ProductRequest.objects.create(
                product=partner_product.product,  # Используем глобальный товар
                user=request.user,
                quantity=quantity,
                request_type='STORE',
                store=store,
                partner_product=partner_product,
                payment_method='debt',
                status='approved'  # Сразу approved, по новой логике
            )

            # Создаем долг магазина
            StoreDebt.objects.create(
                store=store,
                amount=product_request.total_price,
                request=product_request,
                created_by=request.user
            )

            # Обновляем статистику
            from apps.finance.services import update_partner_daily_stats, update_store_daily_stats
            update_partner_daily_stats(request.user, product_request.created_at.date())
            update_store_daily_stats(store, product_request.created_at.date())

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

        # Генерируем общий batch_id для группы запросов
        batch_id = uuid.uuid4()

        created_requests = []
        errors = []
        total_amount = 0

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

                # Проверяем наличие достаточного количества товара
                if product.quantity < quantity:
                    errors.append({
                        "error": f"Недостаточно товара '{product.name}' в каталоге. Доступно: {product.quantity}",
                        "item": item
                    })
                    continue

                # Уменьшаем количество товара у админа
                product.reduce_quantity(quantity)

                # Создаем запрос SELF с общим batch_id
                product_request = ProductRequest.objects.create(
                    product=product,
                    user=request.user,
                    quantity=quantity,
                    request_type='SELF',
                    status='pending',
                    batch_id=batch_id
                )

                total_amount += float(product_request.total_price)

                created_requests.append({
                    "id": product_request.id,
                    "product_name": product.name,
                    "quantity": quantity,
                    "price": float(product.price),
                    "total": float(product_request.total_price)
                })

            except Product.DoesNotExist:
                errors.append({"error": f"Товар с ID {product_id} не найден или неактивен", "item": item})

        if not created_requests:
            return Response(
                {"error": "Не удалось создать ни один запрос", "details": errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({
            "batch_id": str(batch_id),
            "created_requests": created_requests,
            "errors": errors,
            "total_items": len(created_requests),
            "total_amount": total_amount
        }, status=status.HTTP_201_CREATED)

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

        # Генерируем общий batch_id для группы запросов
        batch_id = uuid.uuid4()

        created_requests = []
        errors = []
        total_amount = 0
        bonus_items = []

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

                # Уменьшаем количество товара в каталоге партнера
                partner_product.update_quantity(quantity, operation='subtract')

                # Создаем запрос STORE (со статусом approved по новой логике)
                product_request = ProductRequest.objects.create(
                    product=partner_product.product,
                    user=request.user,
                    quantity=quantity,
                    request_type='STORE',
                    store=store,
                    partner_product=partner_product,
                    payment_method='debt',
                    status='approved',  # Сразу approved по новой логике
                    batch_id=batch_id
                )

                # Создаем долг магазина для этого запроса
                StoreDebt.objects.create(
                    store=store,
                    amount=product_request.total_price,
                    request=product_request,
                    created_by=request.user
                )

                total_amount += float(product_request.total_price)

                # Добавляем информацию о бонусах, если есть
                if product_request.bonus_quantity > 0:
                    bonus_items.append({
                        "product_name": partner_product.product.name,
                        "bonus_quantity": product_request.bonus_quantity
                    })

                created_requests.append({
                    "id": product_request.id,
                    "product_name": partner_product.product.name,
                    "quantity": quantity,
                    "price": float(partner_product.price),
                    "bonus_quantity": product_request.bonus_quantity,
                    "total": float(product_request.total_price)
                })

            except PartnerProduct.DoesNotExist:
                errors.append({"error": f"Товар с ID {partner_product_id} не найден в вашем каталоге", "item": item})

        # Если созданы запросы, обновляем статистику
        if created_requests:
            from apps.finance.services import update_partner_daily_stats, update_store_daily_stats
            update_partner_daily_stats(request.user, timezone.now().date())
            update_store_daily_stats(store, timezone.now().date())

        if not created_requests:
            return Response(
                {"error": "Не удалось создать ни один запрос", "details": errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({
            "batch_id": str(batch_id),
            "store": {
                "id": store.id,
                "name": store.name
            },
            "created_requests": created_requests,
            "bonus_items": bonus_items,
            "errors": errors,
            "total_items": len(created_requests),
            "total_amount": total_amount
        }, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(
        method='post',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['batch_id', 'status'],
            properties={
                'batch_id': openapi.Schema(type=openapi.TYPE_STRING, format='uuid'),
                'status': openapi.Schema(type=openapi.TYPE_STRING, enum=['approved', 'rejected'])
            }
        ),
        responses={
            200: "Запросы успешно обработаны",
            400: "Ошибка при обработке запросов",
            404: "Группа запросов не найдена"
        }
    )
    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def process_batch(self, request):
        """Обработка группы запросов администратором"""
        batch_id = request.data.get('batch_id')
        status_value = request.data.get('status')

        if not batch_id or not status_value:
            return Response(
                {"error": "Необходимо указать batch_id и status"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if status_value not in ['approved', 'rejected']:
            return Response(
                {"error": "Статус может быть только 'approved' или 'rejected'"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Находим все запросы SELF в группе со статусом pending
        # Согласно новой логике, STORE запросы сразу одобряются и не требуют обработки админом
        requests = ProductRequest.objects.filter(
            batch_id=batch_id,
            status='pending',
            request_type='SELF'
        )

        if not requests.exists():
            return Response(
                {"error": f"Запросы с batch_id={batch_id} не найдены или уже обработаны"},
                status=status.HTTP_404_NOT_FOUND
            )

        processed = []
        errors = []

        for req in requests:
            try:
                old_status = req.status
                req.status = status_value

                # Если статус меняется с pending на approved
                if old_status == 'pending' and status_value == 'approved':
                    # Товар уже был уменьшен в каталоге админа при создании запроса
                    # Теперь добавляем товар в каталог партнера
                    from apps.products.models import PartnerProduct
                    partner_product, created = PartnerProduct.objects.get_or_create(
                        partner=req.user,
                        product=req.product,
                        defaults={
                            'price': req.product.price,
                            'quantity': 0
                        }
                    )

                    # Увеличиваем количество товара у партнера
                    partner_product.quantity += req.quantity
                    if req.bonus_quantity > 0:
                        partner_product.bonus_quantity += req.bonus_quantity
                    partner_product.save()

                # Если статус меняется с pending на rejected
                elif old_status == 'pending' and status_value == 'rejected':
                    # Возвращаем товар в каталог администратора
                    req.product.add_quantity(req.quantity)

                req.save()

                processed.append({
                    "id": req.id,
                    "product": req.product.name if req.product else None,
                    "quantity": req.quantity,
                    "status": req.status
                })

                # Обновляем статистику для каждого запроса
                from apps.finance.services import update_partner_daily_stats
                update_partner_daily_stats(req.user, req.created_at.date())

            except Exception as e:
                errors.append({
                    "id": req.id,
                    "product": req.product.name if req.product else None,
                    "error": str(e)
                })

        return Response({
            "batch_id": batch_id,
            "status": status_value,
            "processed_count": len(processed),
            "processed": processed,
            "errors": errors
        })

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

                # Обновляем статистику
                from apps.finance.services import update_partner_daily_stats
                update_partner_daily_stats(instance.user, instance.created_at.date())

            return Response({
                "message": f"Товар '{instance.product.name}' успешно отмечен как полученный",
                "request": ProductRequestSerializer(instance).data
            })
        except Exception as e:
            return Response(
                {"error": f"Ошибка при подтверждении получения: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RecordDamageView(APIView):
    """API для записи бракованных товаров"""
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Запись бракованных товаров",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['partner_product_id', 'quantity'],
            properties={
                'partner_product_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'quantity': openapi.Schema(type=openapi.TYPE_INTEGER, minimum=1),
                'reason': openapi.Schema(type=openapi.TYPE_STRING)
            }
        ),
        responses={
            200: "Брак успешно записан",
            400: "Ошибка при записи брака",
            404: "Товар не найден"
        }
    )
    def post(self, request):
        partner_product_id = request.data.get('partner_product_id')
        quantity = request.data.get('quantity')
        reason = request.data.get('reason', '')

        if not partner_product_id or not quantity:
            return Response(
                {"error": "Необходимо указать partner_product_id и quantity"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            quantity = int(quantity)
            if quantity <= 0:
                return Response(
                    {"error": "Количество должно быть положительным числом"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Находим товар в каталоге партнера
            partner_product = PartnerProduct.objects.get(
                id=partner_product_id,
                partner=request.user
            )

            # Записываем брак
            partner_product.record_damage(quantity)

            # Создаем финансовую запись
            from apps.finance.models import FinanceEntry
            entry = FinanceEntry.objects.create(
                user=request.user,
                date=timezone.now().date(),
                entry_type='damage',
                partner_product=partner_product,
                quantity=quantity,
                note=reason
            )

            # Обновляем статистику
            from apps.finance.services import update_partner_daily_stats
            update_partner_daily_stats(request.user, timezone.now().date())

            return Response({
                "message": f"Брак {quantity} шт. товара '{partner_product.product.name}' успешно записан",
                "damaged_quantity": partner_product.damaged_quantity,
                "entry_id": entry.id
            })
        except PartnerProduct.DoesNotExist:
            return Response(
                {"error": "Товар не найден в вашем каталоге"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Ошибка при записи брака: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

class RecordExpenseView(APIView):
    """API для записи расходов"""
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Запись расходов",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['amount'],
            properties={
                'amount': openapi.Schema(type=openapi.TYPE_NUMBER, minimum=0),
                'store_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'note': openapi.Schema(type=openapi.TYPE_STRING)
            }
        ),
        responses={
            200: "Расход успешно записан",
            400: "Ошибка при записи расхода"
        }
    )
    def post(self, request):
        amount = request.data.get('amount')
        store_id = request.data.get('store_id')
        note = request.data.get('note', '')

        if amount is None:
            return Response(
                {"error": "Необходимо указать сумму расхода"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            amount = float(amount)
            if amount <= 0:
                return Response(
                    {"error": "Сумма расхода должна быть положительным числом"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Проверяем существование магазина, если указан
            store = None
            if store_id:
                try:
                    store = Store.objects.get(id=store_id)
                except Store.DoesNotExist:
                    return Response(
                        {"error": f"Магазин с ID {store_id} не найден"},
                        status=status.HTTP_404_NOT_FOUND
                    )

            # Создаем финансовую запись
            from apps.finance.models import FinanceEntry
            entry = FinanceEntry.objects.create(
                user=request.user,
                date=timezone.now().date(),
                entry_type='expense',
                amount=amount,
                store=store,
                note=note
            )

            # Обновляем статистику
            from apps.finance.services import update_partner_daily_stats
            update_partner_daily_stats(request.user, timezone.now().date())

            if store:
                from apps.finance.services import update_store_daily_stats
                update_store_daily_stats(store, timezone.now().date())

            return Response({
                "message": f"Расход на сумму {amount} успешно записан",
                "entry_id": entry.id
            })
        except Exception as e:
            return Response(
                {"error": f"Ошибка при записи расхода: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

class PayDebtView(APIView):

    """API для оплаты долга магазина"""
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Оплата долга магазина",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['store_id', 'amount'],
            properties={
                'store_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'amount': openapi.Schema(type=openapi.TYPE_NUMBER, minimum=0)
            }
        ),
        responses={
            200: "Долг успешно оплачен",
            400: "Ошибка при оплате долга",
            404: "Магазин не найден"
        }
    )
    def post(self, request):
        store_id = request.data.get('store_id')
        amount = request.data.get('amount')

        if not store_id or amount is None:
            return Response(
                {"error": "Необходимо указать store_id и amount"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            amount = float(amount)
            if amount <= 0:
                return Response(
                    {"error": "Сумма оплаты должна быть положительным числом"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Находим магазин
            store = Store.objects.get(id=store_id)

            # Проверяем права доступа (только партнеры могут оплачивать долги своих магазинов)
            if not request.user.is_staff:
                if not ProductRequest.objects.filter(user=request.user, store=store).exists():
                    return Response(
                        {"error": "У вас нет прав на оплату долга этого магазина"},
                        status=status.HTTP_403_FORBIDDEN
                    )

            # Получаем неоплаченные долги магазина
            debts = StoreDebt.objects.filter(
                store=store,
                is_paid=False
            ).order_by('created_at')

            if not debts.exists():
                return Response(
                    {"error": "У магазина нет неоплаченных долгов"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Общая сумма долга
            total_debt = sum(float(debt.amount - debt.paid_amount) for debt in debts)

            if amount > total_debt:
                return Response(
                    {"error": f"Сумма оплаты ({amount}) превышает общий долг ({total_debt})"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Оплата долгов, начиная с самых ранних
            remaining_amount = amount
            paid_debts = []

            for debt in debts:
                if remaining_amount <= 0:
                    break

                debt_remaining = float(debt.amount - debt.paid_amount)

                if remaining_amount >= debt_remaining:
                    # Полная оплата этого долга
                    payment = debt_remaining
                    debt.is_paid = True
                    debt.paid_amount = debt.amount
                    debt.paid_at = timezone.now()
                    debt.save()

                    remaining_amount -= payment
                else:
                    # Частичная оплата
                    payment = remaining_amount
                    debt.paid_amount += payment
                    debt.save()

                    remaining_amount = 0

                paid_debts.append({
                    "debt_id": debt.id,
                    "request_id": debt.request.id if debt.request else None,
                    "amount": float(debt.amount),
                    "paid_amount": float(debt.paid_amount),
                    "is_fully_paid": debt.is_paid
                })

            # Обновляем статистику магазина
            from apps.finance.services import update_store_daily_stats
            update_store_daily_stats(store, timezone.now().date())

            return Response({
                "store": {
                    "id": store.id,
                    "name": store.name
                },
                "total_debt_before": total_debt,
                "paid_amount": amount,
                "remaining_debt": total_debt - amount,
                "paid_debts": paid_debts
            })
        except Store.DoesNotExist:
            return Response(
                {"error": f"Магазин с ID {store_id} не найден"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Ошибка при оплате долга: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST)


