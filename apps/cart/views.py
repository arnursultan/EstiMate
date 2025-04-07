from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import CartItem
from .serializers import (
    CartItemSerializer,
    AddToCartSerializer,
    UpdateCartItemSerializer,
    CheckoutSerializer
)
from apps.products.models import Product, PartnerProduct
from apps.stores.models import Store
from apps.orders.models import ProductRequest
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi


class CartViewSet(viewsets.ModelViewSet):
    serializer_class = CartItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['cart_type']
    ordering_fields = ['created_at', 'quantity']
    ordering = ['-created_at']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return CartItem.objects.none()

        return CartItem.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == 'add_to_cart':
            return AddToCartSerializer
        elif self.action == 'update_quantity':
            return UpdateCartItemSerializer
        elif self.action == 'checkout':
            return CheckoutSerializer
        return self.serializer_class

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @swagger_auto_schema(
        method='post',
        request_body=AddToCartSerializer,
        responses={201: CartItemSerializer()}
    )
    @action(detail=False, methods=['post'])
    def add_to_cart(self, request):
        """Добавить товар в корзину"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cart_type = serializer.validated_data['cart_type']
        quantity = serializer.validated_data.get('quantity', 1)

        try:
            # Обработка для разных типов корзины
            if cart_type == 'SELF':
                product_id = serializer.validated_data['product_id']
                product = Product.objects.get(id=product_id, is_active=True)

                # Проверяем, есть ли уже такой товар в корзине
                existing_item = CartItem.objects.filter(
                    user=request.user,
                    cart_type='SELF',
                    product=product
                ).first()

                if existing_item:
                    # Увеличиваем количество
                    existing_item.quantity += quantity
                    existing_item.save()
                    return Response(
                        CartItemSerializer(existing_item).data,
                        status=status.HTTP_200_OK
                    )
                else:
                    # Создаем новый элемент корзины
                    cart_item = CartItem.objects.create(
                        user=request.user,
                        cart_type='SELF',
                        product=product,
                        quantity=quantity
                    )
                    return Response(
                        CartItemSerializer(cart_item).data,
                        status=status.HTTP_201_CREATED
                    )

            elif cart_type == 'STORE':
                partner_product_id = serializer.validated_data['partner_product_id']
                store_id = serializer.validated_data['store_id']

                partner_product = PartnerProduct.objects.get(id=partner_product_id, partner=request.user)
                store = Store.objects.get(id=store_id, status='approved', is_active=True)

                # Проверка достаточного количества товара
                if partner_product.remaining_quantity < quantity:
                    return Response(
                        {
                            "error": f"Недостаточно товара в вашем каталоге. Доступно: {partner_product.remaining_quantity}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Проверяем, есть ли уже такой товар в корзине
                existing_item = CartItem.objects.filter(
                    user=request.user,
                    cart_type='STORE',
                    partner_product=partner_product,
                    store=store
                ).first()

                if existing_item:
                    # Увеличиваем количество
                    existing_item.quantity += quantity
                    existing_item.save()
                    return Response(
                        CartItemSerializer(existing_item).data,
                        status=status.HTTP_200_OK
                    )
                else:
                    # Создаем новый элемент корзины
                    cart_item = CartItem.objects.create(
                        user=request.user,
                        cart_type='STORE',
                        partner_product=partner_product,
                        store=store,
                        quantity=quantity
                    )
                    return Response(
                        CartItemSerializer(cart_item).data,
                        status=status.HTTP_201_CREATED
                    )

        except Product.DoesNotExist:
            return Response(
                {"error": "Указанный товар не найден или неактивен"},
                status=status.HTTP_404_NOT_FOUND
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

    @swagger_auto_schema(
        method='patch',
        request_body=UpdateCartItemSerializer,
        responses={200: CartItemSerializer()}
    )
    @action(detail=True, methods=['patch'])
    def update_quantity(self, request, pk=None):
        """Обновить количество товара в корзине"""
        cart_item = self.get_object()
        serializer = self.get_serializer(cart_item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            CartItemSerializer(cart_item).data,
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['get'])
    def self_cart(self, request):
        """Получить товары из корзины 'для себя'"""
        cart_items = CartItem.objects.filter(user=request.user, cart_type='SELF')
        serializer = self.get_serializer(cart_items, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def store_cart(self, request):
        """Получить товары из корзины 'для магазина'"""
        cart_items = CartItem.objects.filter(user=request.user, cart_type='STORE')
        serializer = self.get_serializer(cart_items, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        method='post',
        request_body=CheckoutSerializer,
        responses={201: "Заказы созданы успешно"}
    )
    @action(detail=False, methods=['post'])
    def checkout(self, request):
        """Оформить заказ из корзины"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cart_type = serializer.validated_data['cart_type']
        cart_items = CartItem.objects.filter(user=request.user, cart_type=cart_type)

        if not cart_items.exists():
            return Response(
                {"error": f"В корзине '{cart_type}' нет товаров"},
                status=status.HTTP_400_BAD_REQUEST
            )

        created_requests = []

        # Создаем запросы в зависимости от типа корзины
        if cart_type == 'SELF':
            for item in cart_items:
                request = ProductRequest.objects.create(
                    product=item.product,
                    user=request.user,
                    quantity=item.quantity,
                    request_type='SELF',
                    status='pending'
                )
                created_requests.append(request.id)

                # Удаляем товар из корзины после создания запроса
                item.delete()

        elif cart_type == 'STORE':
            for item in cart_items:
                request = ProductRequest.objects.create(
                    product=item.partner_product.product,
                    user=request.user,
                    quantity=item.quantity,
                    request_type='STORE',
                    store=item.store,
                    partner_product=item.partner_product,
                    payment_method='debt',
                    status='pending'
                )
                created_requests.append(request.id)

                # Удаляем товар из корзины после создания запроса
                item.delete()

        return Response({
            "message": f"Успешно создано {len(created_requests)} запросов из корзины '{cart_type}'",
            "request_ids": created_requests
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['delete'])
    def clear_cart(self, request):
        """Очистить корзину определенного типа"""
        cart_type = request.query_params.get('cart_type')

        if not cart_type or cart_type not in ['SELF', 'STORE']:
            return Response(
                {"error": "Необходимо указать корректный тип корзины (SELF или STORE)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        count = CartItem.objects.filter(user=request.user, cart_type=cart_type).count()
        CartItem.objects.filter(user=request.user, cart_type=cart_type).delete()

        return Response({
            "message": f"Корзина '{cart_type}' очищена. Удалено {count} элементов."
        }, status=status.HTTP_200_OK)