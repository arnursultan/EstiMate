from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import OrderRequest
from .serializers import OrderRequestSerializer
from rest_framework.views import APIView
from rest_framework import status
from apps.products.models import Product
from apps.stores.models import Store
from decimal import Decimal
from django.shortcuts import get_object_or_404
import logging

logger = logging.getLogger(__name__)


class OrderRequestViewSet(viewsets.ModelViewSet):
    queryset = OrderRequest.objects.all().order_by("-created_at")
    serializer_class = OrderRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return OrderRequest.objects.all()
        return OrderRequest.objects.filter(partner=user)

    def perform_create(self, serializer):
        serializer.save(partner=self.request.user)

    @action(detail=True, methods=['POST'], permission_classes=[permissions.IsAdminUser])
    def approve(self, request, pk=None):
        order = self.get_object()

        if order.status != "pending":
            logger.warning(f"⚠ Попытка одобрить уже обработанную заявку: {order.store_name} (ИНН: {order.inn})")
            return Response({"error": "Заявка уже обработана."}, status=400)

        logger.info(f"✅ Админ {request.user} подтверждает заявку {order.store_name} (ИНН: {order.inn})")
        order.approve()  # Теперь approve() создаст магазин в Store

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
        items = data.get("items", [])
        payment_type = data.get("payment_type", "cash")

        total_price = Decimal("0.00")
        total_quantity = 0
        bonus_items = 0

        for item in items:
            product = get_object_or_404(Product, id=item["product_id"])
            quantity = item["quantity"]

            price_per_item = product.price
            total_price += price_per_item * quantity
            total_quantity += quantity
            bonus_items += quantity // 20

        return Response({
            "total_price": float(total_price),
            "total_quantity": total_quantity,
            "bonus_items": bonus_items,
            "payment_type": payment_type
        }, status=status.HTTP_200_OK)
