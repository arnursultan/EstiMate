from rest_framework import viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import Store
from .serializers import StoreSerializer

class StoreViewSet(viewsets.ModelViewSet):
    queryset = Store.objects.all()
    serializer_class = StoreSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    filterset_fields = ['city', 'status']
    search_fields = ['name', 'inn']
    ordering_fields = ['debt', 'payment']

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return Store.objects.all()
        return Store.objects.filter(owner=user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
