from rest_framework import generics, permissions
from rest_framework.views import APIView
from .models import PartnerFinanceStat, StoreFinanceStat, FinanceEntry, ArchivedDailySummary
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
from .services import CalendarStatistics
from datetime import datetime


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


# apps/finance/views.py


# apps/finance/views.py
# Добавить новые представления
class CalendarStatisticsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Получение меток календаря",
        operation_description="Возвращает даты, на которые есть какие-либо данные (продажи, запросы, расходы)",
        manual_parameters=[
            openapi.Parameter(
                'year',
                openapi.IN_QUERY,
                description="Год (YYYY)",
                type=openapi.TYPE_INTEGER
            ),
            openapi.Parameter(
                'month',
                openapi.IN_QUERY,
                description="Месяц (1-12)",
                type=openapi.TYPE_INTEGER
            ),
            openapi.Parameter(
                'store',
                openapi.IN_QUERY,
                description="ID магазина",
                type=openapi.TYPE_INTEGER
            ),
            openapi.Parameter(
                'city',
                openapi.IN_QUERY,
                description="ID города",
                type=openapi.TYPE_INTEGER
            ),
        ]
    )
    def get(self, request):
        # Получаем параметры запроса
        year = request.query_params.get('year')
        month = request.query_params.get('month')
        store_id = request.query_params.get('store')
        city_id = request.query_params.get('city')

        # Базовый QuerySet
        queryset = CalendarStatistics.objects.all()

        # Ограничиваем данные по пользователю, если не админ
        if not request.user.is_staff:
            queryset = queryset.filter(user=request.user)

        # Применяем фильтры
        if year:
            queryset = queryset.filter(date__year=year)
        if month:
            queryset = queryset.filter(date__month=month)
        if store_id:
            queryset = queryset.filter(store_id=store_id)
        if city_id:
            queryset = queryset.filter(city_id=city_id)

        # Формируем результат
        dates_with_data = {}
        for stat in queryset:
            date_str = stat.date.isoformat()

            if date_str not in dates_with_data:
                dates_with_data[date_str] = {
                    'has_sales': False,
                    'has_requests': False,
                    'has_expenses': False,
                    'has_damaged': False,
                    'has_debt_payment': False
                }

            # Обновляем флаги для даты
            if stat.has_sales:
                dates_with_data[date_str]['has_sales'] = True
            if stat.has_requests:
                dates_with_data[date_str]['has_requests'] = True
            if stat.has_expenses:
                dates_with_data[date_str]['has_expenses'] = True
            if stat.has_damaged:
                dates_with_data[date_str]['has_damaged'] = True
            if stat.has_debt_payment:
                dates_with_data[date_str]['has_debt_payment'] = True

        return Response({
            'dates': dates_with_data
        })


class ArchivedDataView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Получение архивных данных",
        operation_description="Возвращает архивные данные по запросам за указанную дату",
        manual_parameters=[
            openapi.Parameter(
                'date',
                openapi.IN_QUERY,
                description="Дата (YYYY-MM-DD)",
                type=openapi.TYPE_STRING,
                format='date',
                required=True
            )
        ]
    )
    def get(self, request):
        date_str = request.query_params.get('date')

        if not date_str:
            return Response({"error": "Параметр 'date' обязателен"}, status=400)

        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({"error": "Неверный формат даты. Используйте YYYY-MM-DD"}, status=400)

        # Получаем архивные данные
        if request.user.is_staff:
            # Для админа - данные по всем пользователям
            archives = ArchivedDailySummary.objects.filter(date=date_obj)
        else:
            # Для партнера - только его данные
            archives = ArchivedDailySummary.objects.filter(date=date_obj, user=request.user)

        if not archives.exists():
            return Response({"message": "Нет данных за указанную дату"}, status=404)

        # Формируем ответ
        result = []
        for archive in archives:
            result.append({
                "user": {
                    "id": archive.user.id,
                    "email": archive.user.email,
                    "name": f"{archive.user.first_name} {archive.user.last_name}"
                },
                "date": archive.date,
                "total_requests": archive.total_requests,
                "total_sales": float(archive.total_sales),
                "total_expenses": float(archive.total_expenses),
                "total_profit": float(archive.total_profit),
                "details": archive.data
            })

        return Response(result)


class BalanceCalculatorView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Расчет общего баланса",
        operation_description="Возвращает общий баланс с учетом доходов, расходов, долгов и бонусов",
        manual_parameters=[
            openapi.Parameter(
                'date',
                openapi.IN_QUERY,
                description="Дата (YYYY-MM-DD)",
                type=openapi.TYPE_STRING,
                format='date'
            ),
            openapi.Parameter(
                'store',
                openapi.IN_QUERY,
                description="ID магазина",
                type=openapi.TYPE_INTEGER
            ),
            openapi.Parameter(
                'city',
                openapi.IN_QUERY,
                description="ID города",
                type=openapi.TYPE_INTEGER
            ),
        ]
    )
    def get(self, request):
        user = request.user
        date = request.query_params.get('date')
        store_id = request.query_params.get('store')
        city_id = request.query_params.get('city')

        # Базовые параметры фильтрации
        filter_params = {}
        if date:
            filter_params['date'] = date

        # Для партнера - только его статистика
        if not user.is_staff:
            filter_params['user'] = user

        # Рассчитываем компоненты баланса
        from apps.finance.models import PartnerFinanceStat, StoreFinanceStat
        from apps.stores.models import StoreDebt

        # Доход (подтвержденные запросы)
        total_income = 0
        income_stats = PartnerFinanceStat.objects.filter(**filter_params)
        for stat in income_stats:
            total_income += float(stat.total_approved_cash)

        # Расходы (ручные записи + убытки от брака)
        total_expenses = 0
        expense_stats = PartnerFinanceStat.objects.filter(**filter_params)
        for stat in expense_stats:
            total_expenses += float(stat.total_damaged_loss)

        # Добавляем ручные расходы
        from apps.finance.models import FinanceEntry
        expense_filter = {'user': user} if not user.is_staff else {}
        if date:
            expense_filter['date'] = date
        if city_id:
            expense_filter['city_id'] = city_id

        manual_expenses = FinanceEntry.objects.filter(**expense_filter)
        total_expenses += sum(float(e.expense) for e in manual_expenses)

        # Долги магазинов
        total_debt = 0
        debt_filter = {}
        if store_id:
            debt_filter['store_id'] = store_id

        store_debts = StoreDebt.objects.filter(is_paid=False, **debt_filter)
        total_debt = sum(float(d.amount) for d in store_debts)

        # Погашенные долги
        paid_debt = 0
        paid_debt_filter = {'is_paid': True}
        if store_id:
            paid_debt_filter['store_id'] = store_id
        if date:
            paid_debt_filter['paid_at__date'] = date

        paid_debts = StoreDebt.objects.filter(**paid_debt_filter)
        paid_debt = sum(float(d.amount) for d in paid_debts)

        # Бонусы (их стоимость)
        total_bonus = 0
        bonus_filter = {}
        if user.is_staff:
            if store_id:
                bonus_filter['store_id'] = store_id
            if city_id:
                bonus_filter['store__city_id'] = city_id
        else:
            bonus_filter['user'] = user

        if date:
            bonus_filter['created_at__date'] = date

        from apps.orders.models import ProductRequest
        bonus_requests = ProductRequest.objects.filter(
            status__in=['approved', 'received'],
            **bonus_filter
        )

        for req in bonus_requests:
            bonus_value = req.bonus_quantity * req.product.price
            total_bonus += float(bonus_value)

        # Расчет общего баланса
        balance = total_income - total_expenses - total_debt + paid_debt + total_bonus

        return Response({
            "balance_components": {
                "income": total_income,
                "expenses": total_expenses,
                "outstanding_debt": total_debt,
                "paid_debt": paid_debt,
                "bonus_value": total_bonus
            },
            "total_balance": balance
        })


class AdminDamagedGoodsReportView(APIView):
    permission_classes = [IsAdminUser]

    @swagger_auto_schema(
        operation_summary="Отчет по бракованным товарам",
        operation_description="Возвращает детальный отчет по бракованным товарам за период",
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
                'store',
                openapi.IN_QUERY,
                description="ID магазина",
                type=openapi.TYPE_INTEGER
            ),
            openapi.Parameter(
                'city',
                openapi.IN_QUERY,
                description="ID города",
                type=openapi.TYPE_INTEGER
            ),
        ]
    )
    def get(self, request):
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        store_id = request.query_params.get('store')
        city_id = request.query_params.get('city')

        # Базовый фильтр - только запросы с браком
        queryset = ProductRequest.objects.filter(damaged_quantity__gt=0)

        # Применяем фильтры
        if date_from and date_to:
            queryset = queryset.filter(created_at__date__range=[date_from, date_to])
        if store_id:
            queryset = queryset.filter(store_id=store_id)
        elif city_id:
            queryset = queryset.filter(store__city_id=city_id)

        # Группируем по товарам
        from django.db.models import Sum, F
        product_damages = queryset.values(
            'product__id', 'product__name'
        ).annotate(
            total_damaged=Sum('damaged_quantity'),
            total_loss=Sum(F('damaged_quantity') * F('product__price'))
        ).order_by('-total_damaged')

        # Группируем по партнерам
        partner_damages = queryset.values(
            'user__id', 'user__email', 'user__first_name', 'user__last_name'
        ).annotate(
            total_damaged=Sum('damaged_quantity'),
            total_loss=Sum(F('damaged_quantity') * F('product__price'))
        ).order_by('-total_damaged')

        # Группируем по магазинам (если применимо)
        store_damages = []
        if queryset.filter(store__isnull=False).exists():
            store_damages = queryset.filter(store__isnull=False).values(
                'store__id', 'store__name', 'store__city__name'
            ).annotate(
                total_damaged=Sum('damaged_quantity'),
                total_loss=Sum(F('damaged_quantity') * F('product__price'))
            ).order_by('-total_damaged')

        # Общая статистика
        total_damaged = queryset.aggregate(
            total=Sum('damaged_quantity'),
            total_loss=Sum(F('damaged_quantity') * F('product__price'))
        )

        return Response({
            "filters": {
                "date_from": date_from,
                "date_to": date_to,
                "store_id": store_id,
                "city_id": city_id
            },
            "summary": {
                "total_damaged_items": total_damaged['total'] or 0,
                "total_loss": float(total_damaged['total_loss'] or 0)
            },
            "by_product": list(product_damages),
            "by_partner": list(partner_damages),
            "by_store": list(store_damages)
        })