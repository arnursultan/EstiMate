from rest_framework import viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import Finance
from .serializers import FinanceSerializer

class FinanceViewSet(viewsets.ModelViewSet):
    queryset = Finance.objects.all()
    serializer_class = FinanceSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['store']
    ordering_fields = ['created_at', 'balance']

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return Finance.objects.all()
        return Finance.objects.filter(store__owner=user)
