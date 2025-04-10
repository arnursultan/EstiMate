from django.utils import timezone
from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.parsers import MultiPartParser, FormParser
from .models import Product, PartnerProduct
from .serializers import (
    ProductSerializer,
    ProductDetailSerializer,
    ProductQuantityUpdateSerializer,
    ProductBonusSerializer,
    PartnerProductSerializer,
    PartnerProductUpdateSerializer
)
from django.core.exceptions import  ValidationError
from apps.finance.serializers import FinanceEntrySerializer


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_staff


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_bonus_eligible', 'is_active']
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

    @property
    def get_queryset(self):
        queryset = Product.objects.all()

        # Если пользователь не админ - только активные товары
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_active=True)

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
    def add_quantity(self, request):
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
    def bonus_info(self, request):
        """Расчет бонусов для товара"""
        product = self.get_object()
        serializer = ProductBonusSerializer(data=request.query_params)

        if serializer.is_valid():
            quantity = serializer.validated_data['quantity']

            # Рассчитываем бонусы только если товар участвует в бонусной программе
            bonus_count = product.calculate_bonus(quantity)
            bonus_value = bonus_count * product.price

            return Response({
                "product_id": product.id,
                "product_name": product.name,
                "is_bonus_eligible": product.is_bonus_eligible,
                "requested_quantity": quantity,
                "bonus_count": bonus_count,
                "bonus_value": float(bonus_value)
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

    @action(detail=True, methods=['post'])
    def request_for_self(self, request):
        """Запросить товар 'для себя' (SELF)"""
        product = self.get_object()

        # Проверка, что пользователь не админ (админ не может делать запросы)
        if request.user.is_staff:
            return Response(
                {"error": "Администратор не может делать запросы на товары"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Получаем запрашиваемое количество из запроса
        quantity = request.data.get('quantity', 0)
        try:
            quantity = int(quantity)
            if quantity <= 0:
                return Response(
                    {"error": "Количество должно быть положительным числом"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Создаем запрос типа SELF
            # Это будет реализовано в директории orders, когда мы до нее дойдем
            # Для сейчас просто заглушка
            return Response(
                {"message": "Запрос товара создан успешно", "quantity": quantity, "product_id": product.id},
                status=status.HTTP_201_CREATED
            )
        except (ValueError, TypeError):
            return Response(
                {"error": "Недопустимое значение для количества"},
                status=status.HTTP_400_BAD_REQUEST
            )


class PartnerProductViewSet(viewsets.ModelViewSet):
    """ViewSet для работы с товарами партнера"""
    serializer_class = PartnerProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['product']
    search_fields = ['product__name', 'product__description']
    ordering_fields = ['created_at', 'quantity', 'remaining_quantity', 'price']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return PartnerProduct.objects.none()

        if self.request.user.is_staff:
            # Администраторы видят все товары всех партнеров
            return PartnerProduct.objects.all()
        else:
            # Партнеры видят только свои товары
            return PartnerProduct.objects.filter(partner=self.request.user)

    def get_serializer_class(self):
        if self.action in ['update_quantities', 'record_sale', 'record_damage', 'record_return']:
            return PartnerProductUpdateSerializer
        return PartnerProductSerializer

    def perform_create(self, serializer):
        serializer.save(partner=self.request.user)

    @action(detail=True, methods=['patch'])
    def update_quantities(self, request):
        """Обновление количественных показателей товара партнера"""
        partner_product = self.get_object()

        # Проверка, что товар принадлежит партнеру, делающему запрос
        if not request.user.is_staff and partner_product.partner != request.user:
            return Response(
                {"error": "У вас нет прав на редактирование этого товара"},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = self.get_serializer(partner_product, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(PartnerProductSerializer(partner_product).data)

    @action(detail=True, methods=['post'])
    def record_sale(self, request):
        """Запись о продаже товара"""
        partner_product = self.get_object()

        # Проверка прав
        if not request.user.is_staff and partner_product.partner != request.user:
            return Response(
                {"error": "У вас нет прав на редактирование этого товара"},
                status=status.HTTP_403_FORBIDDEN
            )

        amount = request.data.get('amount', 0)
        try:
            amount = int(amount)
            if amount <= 0:
                return Response(
                    {"error": "Количество должно быть положительным числом"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            partner_product.record_sale(amount)
            return Response(PartnerProductSerializer(partner_product).data)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, TypeError):
            return Response(
                {"error": "Недопустимое значение для количества"},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def record_damage(self, request):
        """Запись о бракованном товаре"""
        partner_product = self.get_object()

        # Проверка прав
        if not request.user.is_staff and partner_product.partner != request.user:
            return Response(
                {"error": "У вас нет прав на редактирование этого товара"},
                status=status.HTTP_403_FORBIDDEN
            )

        amount = request.data.get('amount', 0)
        try:
            amount = int(amount)
            if amount <= 0:
                return Response(
                    {"error": "Количество должно быть положительным числом"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            partner_product.record_damage(amount)
            return Response(PartnerProductSerializer(partner_product).data)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, TypeError):
            return Response(
                {"error": "Недопустимое значение для количества"},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def record_return(self, request):
        """Запись о возврате товара"""
        partner_product = self.get_object()

        # Проверка прав
        if not request.user.is_staff and partner_product.partner != request.user:
            return Response(
                {"error": "У вас нет прав на редактирование этого товара"},
                status=status.HTTP_403_FORBIDDEN
            )

        amount = request.data.get('amount', 0)
        try:
            amount = int(amount)
            if amount <= 0:
                return Response(
                    {"error": "Количество должно быть положительным числом"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            partner_product.record_return(amount)
            return Response(PartnerProductSerializer(partner_product).data)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, TypeError):
            return Response(
                {"error": "Недопустимое значение для количества"},
                status=status.HTTP_400_BAD_REQUEST
            )

    # Добавляем в apps/products/views.py

    @action(detail=True, methods=['post'])
    def record_sold(self, request):
        """Запись о проданных товарах"""
        partner_product = self.get_object()

        # Проверка прав
        if not request.user.is_staff and partner_product.partner != request.user:
            return Response(
                {"error": "У вас нет прав на редактирование этого товара"},
                status=status.HTTP_403_FORBIDDEN
            )

        quantity = request.data.get('quantity', 0)
        try:
            quantity = int(quantity)
            if quantity <= 0:
                return Response(
                    {"error": "Количество должно быть положительным числом"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Проверка достаточного количества товара
            if quantity > partner_product.remaining_quantity:
                return Response(
                    {"error": f"Недостаточно товара для продажи. Доступно: {partner_product.remaining_quantity}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Запись продажи
            partner_product.record_sale(quantity)

            # Создание финансовой записи
            from apps.finance.models import FinanceEntry
            entry = FinanceEntry.objects.create(
                user=request.user,
                date=timezone.now().date(),
                entry_type='sale',
                partner_product=partner_product,
                quantity=quantity,
                amount=quantity * partner_product.price
            )

            # Обновление статистики
            from apps.finance.services import update_partner_statistics
            update_partner_statistics(
                request.user,
                income_amount=quantity * partner_product.price
            )

            return Response({
                "message": f"Продажа {quantity} шт. товара '{partner_product.product.name}' успешно записана",
                "partner_product": PartnerProductSerializer(partner_product).data,
                "finance_entry": FinanceEntrySerializer(entry).data
            })
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": f"Ошибка при записи продажи: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def record_damage(self, request):
        """Запись о бракованных товарах"""
        partner_product = self.get_object()

        # Проверка прав
        if not request.user.is_staff and partner_product.partner != request.user:
            return Response(
                {"error": "У вас нет прав на редактирование этого товара"},
                status=status.HTTP_403_FORBIDDEN
            )

        quantity = request.data.get('quantity', 0)
        try:
            quantity = int(quantity)
            if quantity <= 0:
                return Response(
                    {"error": "Количество должно быть положительным числом"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Запись брака (не влияет на остаток)
            partner_product.record_damage(quantity)

            # Создание финансовой записи (без влияния на баланс)
            from apps.finance.models import FinanceEntry
            FinanceEntry.objects.create(
                user=request.user,
                date=timezone.now().date(),
                entry_type='damage',
                partner_product=partner_product,
                quantity=quantity,
                amount=0  # Брак не влияет на финансы
            )

            return Response({
                "message": f"Брак {quantity} шт. товара '{partner_product.product.name}' успешно записан",
                "partner_product": PartnerProductSerializer(partner_product).data
            })
        except Exception as e:
            return Response(
                {"error": f"Ошибка при записи брака: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )