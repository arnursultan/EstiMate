from rest_framework import viewsets, permissions, status, filters
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from .models import Store
from .serializers import StoreSerializer
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q



class StoreViewSet(viewsets.ModelViewSet):
    queryset = Store.objects.all().order_by("-created_at")
    serializer_class = StoreSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["inn", "city"]
    search_fields = ["name", "inn", "city"]

    def create(self, request, *args, **kwargs):
        return Response({"error": "Создание магазинов доступно только через заявки."}, status=status.HTTP_403_FORBIDDEN)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)

        try:
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": "Ошибка сервера", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_queryset(self):
        queryset = Store.objects.all().order_by("-created_at")
        search_query = self.request.GET.get("search")

        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(inn__icontains=search_query) |
                Q(city__icontains=search_query)
            )

        return queryset