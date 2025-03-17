from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import OrderRequest
from .serializers import OrderRequestSerializer


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
            return Response({"error": "Заявка уже обработана."}, status=400)

        print(f"📌 Одобряем заявку ID {order.id}")
        order.approve()

        return Response({"success": f"Заявка {order.store_name} подтверждена."})

    @action(detail=True, methods=['POST'], permission_classes=[permissions.IsAdminUser])
    def reject(self, request, pk=None):
        order = self.get_object()
        if order.status != "pending":
            return Response({"error": "Заявка уже обработана."}, status=400)
        order.reject()
        return Response({"success": f"Заявка {order.store_name} отклонена."})
