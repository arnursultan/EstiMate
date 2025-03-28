from rest_framework import generics, permissions
from rest_framework.views import APIView
from .models import PartnerFinanceStat, StoreFinanceStat, FinanceEntry
from .serializers import (
    PartnerFinanceStatSerializer,
    StoreFinanceStatSerializer,
    FinanceEntrySerializer
)
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from django.db.models import Sum, Q, F, ExpressionWrapper, IntegerField
from apps.stores.models import StoreDebt
from apps.orders.models import ProductRequest
from apps.products.models import Product


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

class AdminFinanceStatView(APIView):
    permission_classes = [IsAdminUser]

    @swagger_auto_schema(
        operation_summary="Аналитика для админа",
        operation_description="""
    Возвращает общую финансовую статистику: доход, убытки, долги, бонусы, погашенные долги, прибыль, остаток товаров.

    Фильтры:
    - По дате: date_from, date_to
    - По городу (city): ID города
    - По магазину (store): ID магазина
    """,
        manual_parameters=[
            openapi.Parameter(
                'date_from',
                openapi.IN_QUERY,
                description="Начало периода (YYYY-MM-DD)",
                type=openapi.TYPE_STRING,
                format='date'
            ),
            openapi.Parameter(
                'date_to',
                openapi.IN_QUERY,
                description="Конец периода (YYYY-MM-DD)",
                type=openapi.TYPE_STRING,
                format='date'
            ),
            openapi.Parameter(
                'city',
                openapi.IN_QUERY,
                description="ID города",
                type=openapi.TYPE_INTEGER
            ),
            openapi.Parameter(
                'store',
                openapi.IN_QUERY,
                description="ID магазина",
                type=openapi.TYPE_INTEGER
            ),
        ],
        responses={200: openapi.Response(
            description="Успешный ответ",
            examples={
                "application/json": {
                    "date_range": {
                        "from": "2025-03-01",
                        "to": "2025-03-27"
                    },
                    "filters": {
                        "city": "3",
                        "store": "12"
                    },
                    "metrics": {
                        "income": 542000.0,
                        "damaged_loss": 12000.0,
                        "debt": 245000.0,
                        "bonus": 420,
                        "repaid_debt": 45000.0,
                        "profit": 530000.0,
                        "balance": 575000.0,
                        "remaining_stock": 3921
                    }
                }
            }
        )}
    )
    def get(self, request):
        # Получаем параметры фильтрации
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        city_id = request.query_params.get('city')
        store_id = request.query_params.get('store')

        # ---------------------------
        # 1. Доход, брак, долг — из StoreFinanceStat
        # ---------------------------
        stat_qs = StoreFinanceStat.objects.all()
        if date_from and date_to:
            stat_qs = stat_qs.filter(date__range=[date_from, date_to])
        if store_id:
            stat_qs = stat_qs.filter(store_id=store_id)
        elif city_id:
            stat_qs = stat_qs.filter(store__city_id=city_id)

        stats = stat_qs.aggregate(
            income=Sum('total_approved'),
            damaged_loss=Sum('total_damaged'),
            debt=Sum('total_debt')
        )

        # Заменяем None на 0
        for key in stats:
            stats[key] = stats[key] or 0

        # ---------------------------
        # 2. Бонусы — из ProductRequest
        # ---------------------------
        pr_filter = Q(status='received')
        if date_from and date_to:
            pr_filter &= Q(created_at__date__range=[date_from, date_to])
        if store_id:
            pr_filter &= Q(store_id=store_id)
        elif city_id:
            pr_filter &= Q(store__city_id=city_id)

        bonus = ProductRequest.objects.filter(pr_filter).aggregate(
            total_bonus=Sum('bonus_quantity')
        )['total_bonus'] or 0

        # ---------------------------
        # 3. Погашенные долги — из StoreDebt
        # ---------------------------
        debt_filter = Q(is_paid=True)
        if date_from and date_to:
            debt_filter &= Q(paid_at__date__range=[date_from, date_to])
        if store_id:
            debt_filter &= Q(store_id=store_id)
        elif city_id:
            debt_filter &= Q(store__city_id=city_id)

        repaid_debt = StoreDebt.objects.filter(debt_filter).aggregate(
            total=Sum('amount')
        )['total'] or 0

        # ---------------------------
        # 4. Остаток — из Product
        # ---------------------------
        total_in_stock = Product.objects.aggregate(
            total=Sum('quantity')
        )['total'] or 0

        total_requested = ProductRequest.objects.filter(pr_filter).aggregate(
            total=Sum(
                ExpressionWrapper(
                    F('quantity') - F('bonus_quantity') - F('damaged_quantity'),
                    output_field=IntegerField()
                )
            )
        )['total'] or 0

        remaining_stock = (total_in_stock or 0) - (total_requested or 0)

        # ---------------------------
        # 5. Вычисляем прибыль и баланс
        # ---------------------------
        profit = stats['income'] - stats['damaged_loss']
        balance = profit - stats['debt'] + bonus + repaid_debt

        # ---------------------------
        # 6. Финальный ответ
        # ---------------------------
        return Response({
            "date_range": {
                "from": date_from,
                "to": date_to
            },
            "filters": {
                "city": city_id,
                "store": store_id
            },
            "metrics": {
                "income": stats['income'],
                "damaged_loss": stats['damaged_loss'],
                "debt": stats['debt'],
                "bonus": bonus,
                "repaid_debt": repaid_debt,
                "profit": profit,
                "balance": balance,
                "remaining_stock": remaining_stock
            }
        })
