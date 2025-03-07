from rest_framework import viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import OrderRequest
from .serializers import OrderRequestSerializer

class OrderRequestViewSet(viewsets.ModelViewSet):
    queryset = OrderRequest.objects.all()
    serializer_class = OrderRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['store', 'status']
    ordering_fields = ['created_at']

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return OrderRequest.objects.all()
        return OrderRequest.objects.filter(partner=user)

    def perform_create(self, serializer):
        serializer.save(partner=self.request.user, status='pending')
