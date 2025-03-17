from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Store
from .serializers import StoreSerializer


class StoreViewSet(viewsets.ModelViewSet):

    queryset = Store.objects.all().order_by("-created_at")
    serializer_class = StoreSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        return Response({"error": "Создание магазинов доступно только через заявки."}, status=status.HTTP_403_FORBIDDEN)
