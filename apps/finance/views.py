from rest_framework import generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import PartnerFinanceStat, StoreFinanceStat, FinanceEntry
from .serializers import (
    PartnerFinanceStatSerializer,
    StoreFinanceStatSerializer,
    FinanceEntrySerializer
)


class MyFinanceStatView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        stats = PartnerFinanceStat.objects.filter(user=request.user).order_by('-date')
        serializer = PartnerFinanceStatSerializer(stats, many=True)
        return Response(serializer.data)


class StoreFinanceView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        stats = StoreFinanceStat.objects.all().order_by('-date')
        serializer = StoreFinanceStatSerializer(stats, many=True)
        return Response(serializer.data)


class ManualFinanceEntryView(generics.ListCreateAPIView):
    serializer_class = FinanceEntrySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = FinanceEntry.objects.filter(user=self.request.user).order_by('-date')
        city = self.request.query_params.get('city')
        date = self.request.query_params.get('date')
        if city:
            qs = qs.filter(city_id=city)
        if date:
            qs = qs.filter(date=date)
        return qs
