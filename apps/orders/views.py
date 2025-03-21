from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import OrderRequest
from .serializers import OrderRequestSerializer
from rest_framework.views import APIView
from rest_framework import status
from apps.products.models import Product
from apps.stores.models import Store
from apps.finance.models import Finance
from decimal import Decimal
from django.shortcuts import get_object_or_404
import logging
from django.utils import timezone
logger = logging.getLogger(__name__)


class OrderRequestViewSet(viewsets.ModelViewSet):
    queryset = OrderRequest.objects.all().order_by("-created_at")
    serializer_class = OrderRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return OrderRequest.objects.none()
        if user.is_staff:
            return OrderRequest.objects.all()
        return OrderRequest.objects.filter(partner=user)

    def perform_create(self, serializer):
        order_type = self.request.data.get("order_type", "self")
        serializer.save(partner=self.request.user, order_type=order_type)

    @action(detail=True, methods=['POST'], permission_classes=[permissions.IsAdminUser])
    def approve(self, request, pk=None):
        order = self.get_object()

        if order.status != "pending":
            logger.warning(f"⚠ Попытка одобрить уже обработанную заявку: {order.store_name} (ИНН: {order.inn})")
            return Response({"error": "Заявка уже обработана."}, status=400)

        logger.info(f"✅ Админ {request.user} подтверждает заявку {order.store_name} (ИНН: {order.inn})")
        order.approve()

        return Response({"success": f"Заявка {order.store_name} подтверждена и магазин создан."})

    @action(detail=True, methods=['POST'], permission_classes=[permissions.IsAdminUser])
    def reject(self, request, pk=None):
        order = self.get_object()

        if order.status == "approved":
            return Response({"error": "Нельзя отклонить уже подтвержденную заявку."}, status=400)

        if order.status != "pending":
            return Response({"error": "Заявка уже обработана."}, status=400)

        order.reject()
        return Response({"success": f"Заявка {order.store_name} отклонена."})

class OrderCalculatorView(APIView):
    def post(self, request, *args, **kwargs):
        data = request.data
        store_id = data.get("store_id")
        items = data.get("items", [])
        payment_type = data.get("payment_type", "cash")

        store = None
        if store_id:
            store = get_object_or_404(Store, id=store_id)

        total_price = Decimal("0.00")
        total_quantity = 0
        bonus_items = 0

        for item in items:
            product = get_object_or_404(Product, id=item["product_id"])
            quantity = item["quantity"]

            price_per_item = product.price
            total_price += price_per_item * quantity
            total_quantity += quantity

            bonus = quantity // 20
            bonus_items += bonus
            total_quantity += bonus

        previous_debt = store.debt if store else Decimal("0.00")
        new_debt = previous_debt

        if payment_type == "credit" and store:
            new_debt += total_price
            store.debt = new_debt
            store.save()

            Finance.objects.create(
                store=store,
                income=0,
                expense=0,
                debt=total_price,
                payment=0,
                bonus=bonus_items,
                defect=0,
                created_at=timezone.now(),
            )

        elif payment_type == "cash" and store:
            Finance.objects.create(
                store=store,
                income=total_price,
                expense=0,
                debt=previous_debt,
                payment=0,
                bonus=bonus_items,
                defect=0,
                created_at=timezone.now(),
            )

        order_request = OrderRequest.objects.create(
            partner=request.user,
            store_name=store.name if store else "Личный заказ",
            inn=store.inn if store else "—",
            city=store.city if store else "—",
            status="pending"
        )

        return Response({
            "total_price": float(total_price),
            "total_quantity": total_quantity,
            "bonus_items": bonus_items,
            "payment_type": payment_type,
            "store_debt": float(previous_debt) if payment_type == "cash" else float(new_debt),
            "order_id": order_request.id
        }, status=status.HTTP_201_CREATED)
