from django_celery_beat.utils import now
from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import ProductRequest, Product
from .serializers import (
    ProductRequestSerializer,
    AdminProductRequestStatusSerializer,
    PartnerMarkReceivedSerializer,
    ReportDamagedSerializer
)


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_staff)


class ProductRequestViewSet(viewsets.ModelViewSet):
    queryset = ProductRequest.objects.all()
    serializer_class = ProductRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'payment_method', 'for_store', 'store']
    search_fields = ['product__name', 'user__email', 'store__name']
    ordering_fields = ['created_at']

    def get_queryset(self):
        # Поддержка генерации схемы без падения
        if getattr(self, 'swagger_fake_view', False):
            return ProductRequest.objects.none()

        if self.request.user.is_staff:
            return ProductRequest.objects.all()
        return ProductRequest.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def update_status(self, request, pk=None):
        instance = self.get_object()
        serializer = AdminProductRequestStatusSerializer(instance, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(ProductRequestSerializer(instance).data)
        return Response(serializer.errors, status=400)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def mark_received(self, request, pk=None):
        instance = self.get_object()
        if instance.user != request.user:
            return Response({"error": "Вы не можете отмечать чужие запросы"}, status=403)
        serializer = PartnerMarkReceivedSerializer(instance, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(ProductRequestSerializer(instance).data)
        return Response(serializer.errors, status=400)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def report_damaged(self, request, pk=None):
        instance = self.get_object()
        if instance.user != request.user:
            return Response({"error": "Вы не можете редактировать чужие запросы"}, status=403)
        if instance.status != 'received':
            return Response({"error": "Брак можно указать только после получения"}, status=400)
        serializer = ReportDamagedSerializer(instance, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(ProductRequestSerializer(instance).data)
        return Response(serializer.errors, status=400)

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        if not isinstance(request.data, list):
            return Response({"error": "Ожидается список объектов"}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        created = []
        errors = []
        total_quantity = 0
        total_price = 0

        for item in request.data:
            serializer = ProductRequestSerializer(data=item, context={"request": request})
            if serializer.is_valid():
                instance = serializer.save(user=user)
                created.append(ProductRequestSerializer(instance).data)
                total_quantity += instance.quantity
                total_price += float(instance.total_price)
            else:
                errors.append(serializer.errors)

        response_data = {
            "created": created,
            "total_quantity": total_quantity,
            "total_price": total_price
        }
        if errors:
            response_data["errors"] = errors

        return Response(response_data, status=status.HTTP_201_CREATED if created else status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def cart(self, request):
        user = request.user
        queryset = ProductRequest.objects.filter(
            user=user,
            for_store=False,
            status='approved'
        ).order_by('-created_at')
        serializer = ProductRequestSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def daily_report(self, request):
        user = request.user
        today = now().date()

        queryset = ProductRequest.objects.filter(
            user=user,
            status='received',
            created_at__date=today
        )

        total_spent = sum(
            float(r.total_price) for r in queryset
            if r.payment_method == 'cash'
        )
        total_damaged = sum(r.damaged_quantity for r in queryset)
        total_quantity = sum(r.quantity for r in queryset)

        serializer = ProductRequestSerializer(queryset, many=True)
        return Response({
            "date": str(today),
            "requests": serializer.data,
            "total_quantity": total_quantity,
            "total_damaged": total_damaged,
            "total_spent_cash": total_spent
        })

    @action(detail=False, methods=['post'])
    def calculate_total(self, request):
        """
        Калькулятор для расчета общей стоимости запроса без его создания.
        Используется при изменении количества товаров в интерфейсе.
        """
        items = request.data.get('items', [])
        total_quantity = 0
        total_price = 0

        for item in items:
            product_id = item.get('product')
            quantity = int(item.get('quantity', 0))

            if product_id and quantity > 0:
                try:
                    product = Product.objects.get(id=product_id)
                    bonus_quantity = quantity // 21  # Расчет бонусных товаров
                    actual_quantity = quantity - bonus_quantity
                    item_price = product.price * actual_quantity

                    total_quantity += quantity
                    total_price += float(item_price)

                except Product.DoesNotExist:
                    pass

        return Response({
            "total_quantity": total_quantity,
            "total_price": total_price
        })

    @action(detail=False, methods=['post'])
    def calculate_total(self, request):
        """
        Калькулятор для расчета общей стоимости запроса без его создания.
        Используется при изменении количества товаров в интерфейсе.
        """
        items = request.data.get('items', [])
        total_quantity = 0
        total_price = 0

        for item in items:
            product_id = item.get('product')
            quantity = int(item.get('quantity', 0))

            if product_id and quantity > 0:
                try:
                    product = Product.objects.get(id=product_id)
                    bonus_quantity = quantity // 21  # Расчет бонусных товаров
                    actual_quantity = quantity - bonus_quantity
                    item_price = product.price * actual_quantity

                    total_quantity += quantity
                    total_price += float(item_price)

                except Product.DoesNotExist:
                    pass

        return Response({
            "total_quantity": total_quantity,
            "total_price": total_price
        })

    @action(detail=False, methods=['get'])
    def pending_cart(self, request):
        """
        Возвращает запросы в ожидании (для корзины партнера)
        """
        user = request.user
        queryset = ProductRequest.objects.filter(
            user=user,
            for_store=False,
            status='pending'
        ).order_by('-created_at')
        serializer = ProductRequestSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def approved_cart(self, request):
        """
        Возвращает одобренные запросы (для корзины партнера)
        """
        user = request.user
        queryset = ProductRequest.objects.filter(
            user=user,
            for_store=False,
            status='approved'
        ).order_by('-created_at')
        serializer = ProductRequestSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def mark_received_check(self, request, pk=None):
        """
        Проверяет, можно ли отметить запрос как полученный
        """
        instance = self.get_object()
        if instance.user != request.user:
            return Response({
                "can_mark_received": False,
                "message": "Вы не можете отмечать чужие запросы"
            })

        can_mark = instance.status == 'approved'
        return Response({
            "can_mark_received": can_mark,
            "message": "Запрос можно отметить как полученный" if can_mark else
            "Только подтвержденные запросы можно отметить как полученные"
        })

    # Обновить метод report_damaged
    @action(detail=True, methods=['post'])
    def report_damaged(self, request, pk=None):
        instance = self.get_object()
        if instance.user != request.user:
            return Response({"error": "Вы не можете редактировать чужие запросы"}, status=403)

        if instance.status != 'received':
            return Response({"error": "Брак можно указать только после получения"}, status=400)

        serializer = ReportDamagedSerializer(instance, data=request.data)
        if serializer.is_valid():
            prev_damaged = instance.damaged_quantity
            instance = serializer.save()

            # Если количество брака изменилось, обновляем финансовую статистику
            if prev_damaged != instance.damaged_quantity:
                # Получаем или создаем статистику за текущий день
                from apps.finance.models import PartnerFinanceStat
                from django.utils import timezone

                today = timezone.now().date()
                stats, _ = PartnerFinanceStat.objects.get_or_create(
                    user=instance.user,
                    date=today
                )

                # Рассчитываем сумму убытка от брака
                damage_loss = instance.damaged_quantity * instance.product.price
                stats.total_damaged_loss = damage_loss
                stats.total_profit = stats.total_approved_cash - damage_loss
                stats.save()

                # Обновляем метки календаря
                from apps.finance.services import update_calendar_statistics
                update_calendar_statistics(
                    today,
                    user=instance.user,
                    has_damaged=True
                )

                # Если это для магазина, обновляем его статистику тоже
                if instance.store:
                    from apps.finance.models import StoreFinanceStat
                    store_stats, _ = StoreFinanceStat.objects.get_or_create(
                        store=instance.store,
                        date=today
                    )
                    store_stats.total_damaged = sum(
                        r.damaged_quantity * r.product.price
                        for r in ProductRequest.objects.filter(
                            store=instance.store,
                            status='received',
                            created_at__date=today
                        )
                    )
                    store_stats.save()

                    # Обновляем метки календаря для магазина
                    update_calendar_statistics(
                        today,
                        store=instance.store,
                        has_damaged=True
                    )

            return Response(ProductRequestSerializer(instance).data)

        return Response(serializer.errors, status=400)
