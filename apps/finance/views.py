from rest_framework import generics, permissions, status, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.db.models import Sum
from django.utils import timezone
from datetime import datetime
from apps.users.models import User
from .models import (
    PartnerFinanceStat, FinanceEntry,
    CalendarStatistics, ArchivedDailySummary
)
from .serializers import (
    PartnerFinanceStatSerializer,
    FinanceEntrySerializer,
     PartnerProductFinanceSerializer, InventorySummarySerializer
)
from .filters import (
    FinanceEntryFilter,ProductRequestFilter
)
from apps.stores.models import StoreDebt, Store, City
from apps.orders.models import ProductRequest
from apps.products.models import  PartnerProduct
from apps.orders.serializers import ProductRequestSerializer
from .services import generate_inventory_summary, update_partner_statistics, update_store_daily_stats
import logging


logger = logging.getLogger(__name__)


class MyFinanceStatView(APIView):
    """Получение финансовой статистики для текущего пользователя"""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Финансовая статистика пользователя",
        operation_description="Возвращает финансовую статистику текущего пользователя"
    )
    def get(self, request):
        stats = PartnerFinanceStat.objects.filter(user=request.user).order_by('-date')
        serializer = PartnerFinanceStatSerializer(stats, many=True)
        return Response(serializer.data)


# В apps/finance/views.py

class StoreStatisticsView(APIView):
    """API для получения статистики магазина"""
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Статистика магазина",
        manual_parameters=[
            openapi.Parameter(
                'store_id',
                openapi.IN_QUERY,
                description="ID магазина",
                type=openapi.TYPE_INTEGER,
                required=True
            ),
            openapi.Parameter(
                'date',
                openapi.IN_QUERY,
                description="Дата (YYYY-MM-DD), по умолчанию - сегодня",
                type=openapi.TYPE_STRING,
                format='date'
            )
        ],
        responses={200: "Статистика магазина"}
    )
    def get(self, request):
        store_id = request.query_params.get('store_id')
        date_str = request.query_params.get('date')

        if not store_id:
            return Response(
                {"error": "Необходимо указать ID магазина"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            store = Store.objects.get(id=store_id)

            # Для обычных пользователей проверяем, что они взаимодействовали с этим магазином
            if not request.user.is_staff:
                has_interaction = ProductRequest.objects.filter(
                    user=request.user,
                    store=store
                ).exists()

                if not has_interaction:
                    return Response(
                        {"error": "У вас нет доступа к статистике этого магазина"},
                        status=status.HTTP_403_FORBIDDEN
                    )
        except Store.DoesNotExist:
            return Response(
                {"error": f"Магазин с ID {store_id} не найден"},
                status=status.HTTP_404_NOT_FOUND
            )

        if date_str:
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {"error": "Некорректный формат даты. Используйте YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            date_obj = timezone.now().date()

        try:
            # Обновляем статистику перед выдачей
            from apps.finance.services import update_store_daily_stats
            stats = update_store_daily_stats(store, date_obj)

            # Формируем данные для ответа
            return Response({
                "date": date_obj.isoformat(),
                "store": {
                    "id": store.id,
                    "name": store.name,
                    "city": store.city.name if store.city else None
                },
                "requested": {
                    "quantity": stats.total_received_quantity,
                    "details": stats.detailed_data.get('received', {})
                },
                "bonus": {
                    "quantity": stats.total_bonus_quantity
                },
                "damaged": {
                    "quantity": stats.total_damaged_quantity
                },
                "debt": {
                    "current": float(stats.total_debt),
                    "paid": float(stats.total_paid_debt)
                },
                "expenses": float(stats.total_partner_expenses),
                "profit": float(stats.profit)
            })
        except Exception as e:
            return Response(
                {"error": f"Ошибка при получении статистики магазина: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ManualFinanceEntryView(generics.CreateAPIView):
    """Создание ручных финансовых записей"""
    serializer_class = FinanceEntrySerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Создание финансовой записи",
        operation_description="Создает новую финансовую запись (доход/расход)"
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class FinanceEntryListView(generics.ListAPIView):
    """Получение списка финансовых записей"""
    serializer_class = FinanceEntrySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = FinanceEntryFilter
    ordering_fields = ['date', 'amount']

    def get_queryset(self):
        """Возвращает финансовые записи текущего пользователя или все записи для администратора"""
        # Проверяем, не является ли это запросом для генерации схемы Swagger
        if getattr(self, 'swagger_fake_view', False):
            # Возвращаем пустой QuerySet для Swagger
            return FinanceEntry.objects.none()

        qs = FinanceEntry.objects.all() if self.request.user.is_staff else FinanceEntry.objects.filter(
            user=self.request.user)
        return qs  # ⬅️ убери .order_by('-date')


# В apps/finance/views.py

class AdminStatisticsView(APIView):
    """API для получения общей статистики (только для администратора)"""
    permission_classes = [IsAdminUser]

    @swagger_auto_schema(
        operation_summary="Общая статистика (для администратора)",
        manual_parameters=[
            openapi.Parameter(
                'date',
                openapi.IN_QUERY,
                description="Дата (YYYY-MM-DD), по умолчанию - сегодня",
                type=openapi.TYPE_STRING,
                format='date'
            ),
            openapi.Parameter(
                'partner_id',
                openapi.IN_QUERY,
                description="ID партнера (опционально)",
                type=openapi.TYPE_INTEGER
            ),
            openapi.Parameter(
                'store_id',
                openapi.IN_QUERY,
                description="ID магазина (опционально)",
                type=openapi.TYPE_INTEGER
            ),
            openapi.Parameter(
                'city_id',
                openapi.IN_QUERY,
                description="ID города (опционально)",
                type=openapi.TYPE_INTEGER
            )
        ],
        responses={200: "Общая статистика"}
    )
    def get(self, request):
        date_str = request.query_params.get('date')
        partner_id = request.query_params.get('partner_id')
        store_id = request.query_params.get('store_id')
        city_id = request.query_params.get('city_id')

        if date_str:
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {"error": "Некорректный формат даты. Используйте YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            date_obj = timezone.now().date()

        try:
            result = {}

            # 1. Если указан ID партнера, показываем статистику партнера
            if partner_id:
                try:
                    partner = User.objects.get(id=partner_id, is_staff=False)
                    from apps.finance.services import update_partner_daily_stats
                    stats = update_partner_daily_stats(partner, date_obj)

                    result['partner'] = {
                        "id": partner.id,
                        "email": partner.email,
                        "name": f"{partner.first_name} {partner.last_name}",
                        "requested": {
                            "quantity": stats.total_requested_quantity,
                            "amount": float(stats.total_requested_amount),
                            "details": stats.detailed_data.get('requested', {})
                        },
                        "sold": {
                            "quantity": stats.total_sold_quantity,
                            "amount": float(stats.total_sold_amount),
                            "details": stats.detailed_data.get('sold', {})
                        },
                        "expenses": float(stats.total_expenses),
                        "damaged": {
                            "quantity": stats.total_damaged_quantity,
                            "details": stats.detailed_data.get('damaged', {})
                        },
                        "bonus": {
                            "quantity": stats.total_bonus_quantity
                        },
                        "remaining": {
                            "quantity": stats.total_remaining_quantity,
                            "details": stats.detailed_data.get('remaining', {})
                        },
                        "profit": float(stats.profit)
                    }
                except User.DoesNotExist:
                    return Response(
                        {"error": f"Партнер с ID {partner_id} не найден"},
                        status=status.HTTP_404_NOT_FOUND
                    )

            # 2. Если указан ID магазина, показываем статистику магазина
            if store_id:
                try:
                    store = Store.objects.get(id=store_id)
                    from apps.finance.services import update_store_daily_stats
                    stats = update_store_daily_stats(store, date_obj)

                    result['store'] = {
                        "id": store.id,
                        "name": store.name,
                        "city": store.city.name if store.city else None,
                        "requested": {
                            "quantity": stats.total_received_quantity,
                            "details": stats.detailed_data.get('received', {})
                        },
                        "bonus": {
                            "quantity": stats.total_bonus_quantity
                        },
                        "damaged": {
                            "quantity": stats.total_damaged_quantity
                        },
                        "debt": {
                            "current": float(stats.total_debt),
                            "paid": float(stats.total_paid_debt)
                        },
                        "expenses": float(stats.total_partner_expenses),
                        "profit": float(stats.profit)
                    }
                except Store.DoesNotExist:
                    return Response(
                        {"error": f"Магазин с ID {store_id} не найден"},
                        status=status.HTTP_404_NOT_FOUND
                    )

            # 3. Если указан ID города, показываем сводную статистику по городу
            if city_id:
                try:
                    from apps.stores.models import City
                    city = City.objects.get(id=city_id)

                    # Статистика по магазинам в этом городе
                    stores = Store.objects.filter(city=city)

                    # Суммарная статистика по всем магазинам города
                    city_stats = {
                        "stores_count": stores.count(),
                        "total_received": 0,
                        "total_bonus": 0,
                        "total_damaged": 0,
                        "total_debt": 0,
                        "total_paid_debt": 0,
                        "total_expenses": 0,
                        "stores": []
                    }

                    for store in stores:
                        from apps.finance.services import update_store_daily_stats
                        stats = update_store_daily_stats(store, date_obj)

                        # Добавляем информацию о магазине
                        city_stats["stores"].append({
                            "id": store.id,
                            "name": store.name,
                            "received": stats.total_received_quantity,
                            "bonus": stats.total_bonus_quantity,
                            "damaged": stats.total_damaged_quantity,
                            "debt": float(stats.total_debt),
                            "paid_debt": float(stats.total_paid_debt),
                            "expenses": float(stats.total_partner_expenses)
                        })

                        # Суммируем показатели
                        city_stats["total_received"] += stats.total_received_quantity
                        city_stats["total_bonus"] += stats.total_bonus_quantity
                        city_stats["total_damaged"] += stats.total_damaged_quantity
                        city_stats["total_debt"] += float(stats.total_debt)
                        city_stats["total_paid_debt"] += float(stats.total_paid_debt)
                        city_stats["total_expenses"] += float(stats.total_partner_expenses)

                    result['city'] = {
                        "id": city.id,
                        "name": city.name,
                        "stats": city_stats
                    }
                except City.DoesNotExist:
                    return Response(
                        {"error": f"Город с ID {city_id} не найден"},
                        status=status.HTTP_404_NOT_FOUND
                    )

            # 4. Общая статистика, если не указаны фильтры
            if not (partner_id or store_id or city_id):
                # Статистика по партнерам
                partners = User.objects.filter(is_staff=False)

                # Суммарная статистика по всем партнерам
                partners_stats = {
                    "count": partners.count(),
                    "total_requested": 0,
                    "total_sold": 0,
                    "total_expenses": 0,
                    "total_damaged": 0,
                    "total_bonus": 0,
                    "total_remaining": 0,
                    "total_profit": 0
                }

                for partner in partners:
                    from apps.finance.models import PartnerFinanceStat
                    try:
                        stats = PartnerFinanceStat.objects.get(user=partner, date=date_obj)
                        partners_stats["total_requested"] += stats.total_requested_quantity
                        partners_stats["total_sold"] += stats.total_sold_quantity
                        partners_stats["total_expenses"] += float(stats.total_expenses)
                        partners_stats["total_damaged"] += stats.total_damaged_quantity
                        partners_stats["total_bonus"] += stats.total_bonus_quantity
                        partners_stats["total_remaining"] += stats.total_remaining_quantity
                        partners_stats["total_profit"] += float(stats.profit)
                    except PartnerFinanceStat.DoesNotExist:
                        # Обновляем статистику если её нет
                        try:
                            stats = update_partner_daily_stats(partner, date_obj)
                            partners_stats["total_requested"] += stats.total_requested_quantity
                            partners_stats["total_sold"] += stats.total_sold_quantity
                            partners_stats["total_expenses"] += float(stats.total_expenses)
                            partners_stats["total_damaged"] += stats.total_damaged_quantity
                            partners_stats["total_bonus"] += stats.total_bonus_quantity
                            partners_stats["total_remaining"] += stats.total_remaining_quantity
                            partners_stats["total_profit"] += float(stats.profit)
                        except Exception:
                            pass

                # Статистика по магазинам
                stores = Store.objects.filter(status='approved')

                # Суммарная статистика по всем магазинам
                stores_stats = {
                    "count": stores.count(),
                    "total_received": 0,
                    "total_debt": 0,
                    "total_paid_debt": 0,
                    "total_bonus": 0,
                    "total_damaged": 0,
                    "total_expenses": 0,
                    "total_profit": 0
                }

                for store in stores:
                    from apps.finance.models import StoreFinanceStat
                    try:
                        stats = StoreFinanceStat.objects.get(store=store, date=date_obj)
                        stores_stats["total_received"] += stats.total_received_quantity
                        stores_stats["total_debt"] += float(stats.total_debt)
                        stores_stats["total_paid_debt"] += float(stats.total_paid_debt)
                        stores_stats["total_bonus"] += stats.total_bonus_quantity
                        stores_stats["total_damaged"] += stats.total_damaged_quantity
                        stores_stats["total_expenses"] += float(stats.total_partner_expenses)
                        stores_stats["total_profit"] += float(stats.profit)
                    except StoreFinanceStat.DoesNotExist:
                        # Обновляем статистику если её нет
                        try:
                            stats = update_store_daily_stats(store, date_obj)
                            stores_stats["total_received"] += stats.total_received_quantity
                            stores_stats["total_debt"] += float(stats.total_debt)
                            stores_stats["total_paid_debt"] += float(stats.total_paid_debt)
                            stores_stats["total_bonus"] += stats.total_bonus_quantity
                            stores_stats["total_damaged"] += stats.total_damaged_quantity
                            stores_stats["total_expenses"] += float(stats.total_partner_expenses)
                            stores_stats["total_profit"] += float(stats.profit)
                        except Exception:
                            pass

                # Статистика по запросам
                from apps.orders.models import ProductRequest
                requests_stats = {
                    "total": ProductRequest.objects.filter(created_at__date=date_obj).count(),
                    "self_requests": ProductRequest.objects.filter(created_at__date=date_obj,
                                                                   request_type='SELF').count(),
                    "store_requests": ProductRequest.objects.filter(created_at__date=date_obj,
                                                                    request_type='STORE').count(),
                    "pending": ProductRequest.objects.filter(created_at__date=date_obj, status='pending').count(),
                    "approved": ProductRequest.objects.filter(created_at__date=date_obj, status='approved').count(),
                    "rejected": ProductRequest.objects.filter(created_at__date=date_obj, status='rejected').count(),
                    "received": ProductRequest.objects.filter(created_at__date=date_obj, status='received').count()
                }

                # Общий баланс администратора
                total_income = partners_stats["total_requested"]  # Доход от запросов партнеров
                total_expenses = partners_stats["total_expenses"]  # Расходы партнеров
                total_bonus_value = partners_stats["total_bonus"]  # Стоимость бонусов

                admin_balance = float(total_income) - float(total_expenses) - float(total_bonus_value)

                result['summary'] = {
                    "partners": partners_stats,
                    "stores": stores_stats,
                    "requests": requests_stats,
                    "admin_balance": admin_balance
                }

            # Добавляем информацию о дате
            result['date'] = date_obj.isoformat()

            return Response(result)
        except Exception as e:
            return Response(
                {"error": f"Ошибка при получении статистики: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



class CalendarStatisticsView(APIView):
    """Получение меток календаря"""
    permission_classes = [IsAuthenticated]

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
        try:
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
                        'has_debt_payment': False
                    }

                # Обновляем флаги для даты
                if stat.has_sales:
                    dates_with_data[date_str]['has_sales'] = True
                if stat.has_requests:
                    dates_with_data[date_str]['has_requests'] = True
                if stat.has_expenses:
                    dates_with_data[date_str]['has_expenses'] = True
                if stat.has_debt_payment:
                    dates_with_data[date_str]['has_debt_payment'] = True

            return Response({
                'dates': dates_with_data
            })
        except Exception as e:
            logger.error(f"Ошибка при получении меток календаря: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ArchivedDataView(APIView):
    """Получение архивных данных"""
    permission_classes = [IsAuthenticated]

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
        try:
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
        except Exception as e:
            logger.error(f"Ошибка при получении архивных данных: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BalanceCalculatorView(APIView):
    """Расчет общего баланса"""
    permission_classes = [IsAuthenticated]

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
        from apps.orders.models import ProductRequest
        try:
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
            from apps.finance.models import PartnerFinanceStat
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
            expense_filter = {'user': user} if not user.is_staff else {}
            if date:
                expense_filter['date'] = date
            if city_id:
                expense_filter['city_id'] = city_id

            manual_expenses = FinanceEntry.objects.filter(entry_type='expense', **expense_filter)
            total_expenses += sum(float(e.amount) for e in manual_expenses)

            # Долги магазинов
            total_debt = 0
            debt_filter = {}
            if store_id:
                debt_filter['store_id'] = store_id

            # Если обычный пользователь, показываем только долги связанных магазинов
            if not user.is_staff:

                store_ids = ProductRequest.objects.filter(user=user).values_list('store_id', flat=True).distinct()
                debt_filter['store_id__in'] = store_ids

            store_debts = StoreDebt.objects.filter(is_paid=False, **debt_filter)
            total_debt = sum(float(d.amount) for d in store_debts)

            # Погашенные долги
            paid_debt = 0
            paid_debt_filter = {'is_paid': True}
            if store_id:
                paid_debt_filter['store_id'] = store_id
            if date:
                paid_debt_filter['paid_at__date'] = date

            # Если обычный пользователь, показываем только долги связанных магазинов
            if not user.is_staff:

                store_ids = ProductRequest.objects.filter(user=user).values_list('store_id', flat=True).distinct()
                paid_debt_filter['store_id__in'] = store_ids

            paid_debts = StoreDebt.objects.filter(**paid_debt_filter)
            paid_debt = sum(float(d.amount) for d in paid_debts)

            # Бонусы (их стоимость)
            total_bonus = 0
            bonus_filter = {"status__in": ["approved", "received"]}

            if user.is_staff:
                if store_id:
                    bonus_filter['store_id'] = store_id
                if city_id:
                    bonus_filter['store__city_id'] = city_id
            else:
                bonus_filter['user'] = user
                bonus_filter['request_type'] = 'SELF'

            if date:
                bonus_filter['created_at__date'] = date

            bonus_requests = ProductRequest.objects.filter(**bonus_filter).select_related("product")

            for req in bonus_requests:
                if req.bonus_quantity and req.product and req.product.price and req.product.is_active:
                    total_bonus += float(req.bonus_quantity * req.product.price)

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
        except Exception as e:
            logger.error(f"Ошибка при расчете баланса: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class AdminDamagedGoodsReportView(APIView):
    """Отчет по бракованным товарам"""
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
        try:
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
        except Exception as e:
            logger.error(f"Ошибка при формировании отчета по бракованным товарам: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ProductRequestHistoryView(generics.ListAPIView):
    """История запросов на товары"""
    serializer_class = ProductRequestSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ProductRequestFilter  # <-- подключаем кастомный фильтр
    search_fields = ['product__name']
    ordering_fields = ['created_at', 'quantity', 'total_price']

    def get_queryset(self):
        qs = ProductRequest.objects.all()
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs

class FinanceSummaryView(APIView):
    """Сводка по финансам"""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Финансовая сводка",
        operation_description="Возвращает сводку по финансам за указанный период",
        manual_parameters=[
            openapi.Parameter('from', openapi.IN_QUERY, description="Начало периода (YYYY-MM-DD)",
                              type=openapi.TYPE_STRING, format='date'),
            openapi.Parameter('to', openapi.IN_QUERY, description="Конец периода (YYYY-MM-DD)",
                              type=openapi.TYPE_STRING, format='date'),
            openapi.Parameter('store', openapi.IN_QUERY, description="ID магазина",
                              type=openapi.TYPE_INTEGER),
            openapi.Parameter('city', openapi.IN_QUERY, description="ID города",
                              type=openapi.TYPE_INTEGER),
        ]
    )
    def get(self, request):
        try:
            user = request.user
            from_date = request.query_params.get('from')
            to_date = request.query_params.get('to')
            store_id = request.query_params.get('store')
            city_id = request.query_params.get('city')

            filters = {}
            if from_date:
                filters['date__gte'] = from_date
            if to_date:
                filters['date__lte'] = to_date

            # Получаем queryset партнёрской статистики
            if not user.is_staff:
                partner_qs = PartnerFinanceStat.objects.filter(user=user, **filters)
            else:
                partner_qs = PartnerFinanceStat.objects.filter(**filters)
                if store_id:
                    from apps.orders.models import ProductRequest
                    partner_ids = ProductRequest.objects.filter(store_id=store_id)\
                        .values_list('user_id', flat=True).distinct()
                    partner_qs = partner_qs.filter(user_id__in=partner_ids)
                elif city_id:
                    from apps.orders.models import ProductRequest
                    store_ids = Store.objects.filter(city_id=city_id).values_list('id', flat=True)
                    partner_ids = ProductRequest.objects.filter(store_id__in=store_ids)\
                        .values_list('user_id', flat=True).distinct()
                    partner_qs = partner_qs.filter(user_id__in=partner_ids)

            # Считаем суммы вручную по property
            total_approved_cash = sum(stat.total_approved_cash for stat in partner_qs)
            total_damaged_loss = sum(stat.total_damaged_loss for stat in partner_qs)
            total_product_profit = sum(stat.profit for stat in partner_qs)

            # Ручные записи
            entry_filters = {}
            if from_date:
                entry_filters['date__gte'] = from_date
            if to_date:
                entry_filters['date__lte'] = to_date
            if not user.is_staff:
                entry_filters['user'] = user
            if city_id:
                entry_filters['city_id'] = city_id

            manual_entries = FinanceEntry.objects.filter(**entry_filters)

            total_manual_income = manual_entries.filter(entry_type='income').aggregate(
                total=Sum('amount'))['total'] or 0
            total_manual_expense = manual_entries.filter(entry_type='expense').aggregate(
                total=Sum('amount'))['total'] or 0
            total_manual_profit = total_manual_income - total_manual_expense

            # Долги
            debt_filters = {'is_paid': False}
            if store_id:
                debt_filters['store_id'] = store_id
            elif city_id:
                debt_filters['store__city_id'] = city_id
            if not user.is_staff:
                from apps.orders.models import ProductRequest
                store_ids = ProductRequest.objects.filter(user=user)\
                    .values_list('store_id', flat=True).distinct()
                debt_filters['store_id__in'] = store_ids

            total_debt = StoreDebt.objects.filter(**debt_filters).aggregate(
                total=Sum('amount'))['total'] or 0

            # Формируем ответ
            result = {
                "period": {
                    "from": from_date,
                    "to": to_date
                },
                "filters": {
                    "store_id": store_id,
                    "city_id": city_id
                },
                "finance_summary": {
                    "approved_sales": float(total_approved_cash),
                    "damaged_loss": float(total_damaged_loss),
                    "product_profit": float(total_product_profit),
                    "manual_income": float(total_manual_income),
                    "manual_expense": float(total_manual_expense),
                    "manual_profit": float(total_manual_profit),
                    "outstanding_debt": float(total_debt),
                    "total_profit": float(total_product_profit + total_manual_profit),
                }
            }

            return Response(result)

        except Exception as e:
            logger.error(f"Ошибка при получении финансовой сводки: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PartnerInventoryView(APIView):
    """Получение сводки по остаткам товаров партнера"""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Сводка по остаткам товаров",
        operation_description="Возвращает сводку по остаткам товаров в каталоге партнера"
    )
    def get(self, request):
        # Генерируем сводку по остаткам
        summary = generate_inventory_summary(request.user)

        if not summary:
            return Response({"message": "В вашем каталоге нет товаров"}, status=status.HTTP_404_NOT_FOUND)

        serializer = InventorySummarySerializer(summary)
        return Response(serializer.data)


class FinanceEntryCreateView(APIView):
    """Создание финансовой записи разных типов (расход, продажа, брак и т.д.)"""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Создание финансовой записи",
        request_body=FinanceEntrySerializer,
        responses={201: FinanceEntrySerializer()}
    )
    def post(self, request):
        serializer = FinanceEntrySerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        entry = serializer.save()

        return Response(FinanceEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


class PartnerProductFinanceView(APIView):
    """Запись финансовых операций по товару из каталога партнера"""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Финансовая операция с товаром",
        operation_description="Создает запись о продаже, браке или возврате товара из каталога",
        request_body=PartnerProductFinanceSerializer,
        responses={201: FinanceEntrySerializer()}
    )
    def post(self, request):
        serializer = PartnerProductFinanceSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        partner_product_id = serializer.validated_data['partner_product_id']
        entry_type = serializer.validated_data['entry_type']
        quantity = serializer.validated_data.get('quantity')
        note = serializer.validated_data.get('note', '')
        amount = serializer.validated_data.get('amount', 0)

        try:
            partner_product = PartnerProduct.objects.get(id=partner_product_id)

            # Создаем финансовую запись
            entry = FinanceEntry.objects.create(
                user=request.user,
                date=timezone.now().date(),
                entry_type=entry_type,
                quantity=quantity or 0,
                amount=amount,
                partner_product=partner_product,
                note=note
            )

            return Response(FinanceEntrySerializer(entry).data, status=status.HTTP_201_CREATED)

        except PartnerProduct.DoesNotExist:
            return Response(
                {"error": "Указанный товар не найден в вашем каталоге"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PartnerCatalogFinanceView(APIView):
    """Сводка по финансам, связанным с каталогом партнера"""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Финансовая сводка по каталогу",
        operation_description="Возвращает финансовую сводку по товарам из каталога партнера",
        manual_parameters=[
            openapi.Parameter('from_date', openapi.IN_QUERY, description="Начало периода (YYYY-MM-DD)", type=openapi.TYPE_STRING, format='date'),
            openapi.Parameter('to_date', openapi.IN_QUERY, description="Конец периода (YYYY-MM-DD)", type=openapi.TYPE_STRING, format='date'),
            openapi.Parameter('partner_product_id', openapi.IN_QUERY, description="ID товара из каталога", type=openapi.TYPE_INTEGER),
        ]
    )
    def get(self, request):
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        partner_product_id = request.query_params.get('partner_product_id')

        user = request.user

        # Все записи пользователя для товарных операций
        product_entries = FinanceEntry.objects.filter(user=user).exclude(partner_product=None)
        if from_date:
            product_entries = product_entries.filter(date__gte=from_date)
        if to_date:
            product_entries = product_entries.filter(date__lte=to_date)
        if partner_product_id:
            product_entries = product_entries.filter(partner_product_id=partner_product_id)

        sale_entries = product_entries.filter(entry_type='sale')
        damage_entries = product_entries.filter(entry_type='damage')
        return_entries = product_entries.filter(entry_type='return')

        total_sales = sale_entries.aggregate(total=Sum('amount'))['total'] or 0
        total_sales_quantity = sale_entries.aggregate(total=Sum('quantity'))['total'] or 0

        total_damages = damage_entries.aggregate(total=Sum('amount'))['total'] or 0
        total_damages_quantity = damage_entries.aggregate(total=Sum('quantity'))['total'] or 0

        total_returns = return_entries.aggregate(total=Sum('amount'))['total'] or 0
        total_returns_quantity = return_entries.aggregate(total=Sum('quantity'))['total'] or 0

        # Доходы и расходы считаем всегда по пользователю, без фильтра partner_product
        income_entries = FinanceEntry.objects.filter(user=user, entry_type='income')
        expense_entries = FinanceEntry.objects.filter(user=user, entry_type='expense')
        if from_date:
            income_entries = income_entries.filter(date__gte=from_date)
            expense_entries = expense_entries.filter(date__gte=from_date)
        if to_date:
            income_entries = income_entries.filter(date__lte=to_date)
            expense_entries = expense_entries.filter(date__lte=to_date)

        total_income = income_entries.aggregate(total=Sum('amount'))['total'] or 0
        total_expenses = expense_entries.aggregate(total=Sum('amount'))['total'] or 0

        profit = total_sales + total_returns + total_income - total_damages - total_expenses

        detail = None
        if partner_product_id:
            try:
                partner_product = PartnerProduct.objects.get(id=partner_product_id, partner=user)
                detail = {
                    "product_name": partner_product.product.name,
                    "price": float(partner_product.price),
                    "total_quantity": partner_product.quantity,
                    "sold_quantity": partner_product.sold_quantity,
                    "damaged_quantity": partner_product.damaged_quantity,
                    "bonus_quantity": partner_product.bonus_quantity,
                    "returned_quantity": partner_product.returned_quantity,
                    "remaining_quantity": partner_product.remaining_quantity,
                    "total_value": float(partner_product.quantity * partner_product.price),
                    "sold_value": float(partner_product.sold_quantity * partner_product.price),
                    "remaining_value": float(partner_product.remaining_quantity * partner_product.price)
                }
            except PartnerProduct.DoesNotExist:
                pass

        result = {
            "period": {"from": from_date, "to": to_date},
            "sales": {"amount": float(total_sales), "quantity": total_sales_quantity},
            "damages": {"amount": float(total_damages), "quantity": total_damages_quantity},
            "returns": {"amount": float(total_returns), "quantity": total_returns_quantity},
            "expenses": float(total_expenses),
            "income": float(total_income),
            "profit": float(profit),
        }

        if detail:
            result["product_detail"] = detail

        return Response(result)




# Добавляем в apps/finance/views.py

class ExpenseEntryView(APIView):
    """API для добавления расходов"""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Добавление расхода",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'amount': openapi.Schema(type=openapi.TYPE_NUMBER, description="Сумма расхода"),
                'note': openapi.Schema(type=openapi.TYPE_STRING, description="Примечание к расходу"),
                'city': openapi.Schema(type=openapi.TYPE_INTEGER, description="ID города (опционально)")
            },
            required=['amount']
        ),
        responses={201: "Расход успешно добавлен"}
    )
    # Модифицируем метод post в ExpenseEntryView

    def post(self, request):
        amount = request.data.get('amount')
        note = request.data.get('note', '')
        city_id = request.data.get('city')
        store_id = request.data.get('store')  # Добавляем поддержку store_id

        try:
            amount = float(amount)
            if amount <= 0:
                return Response(
                    {"error": "Сумма расхода должна быть положительной"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # Получаем город, если указан
            city = None
            if city_id:
                try:
                    city = City.objects.get(id=city_id)
                except City.DoesNotExist:
                    return Response(
                        {"error": f"Город с ID {city_id} не найден"},
                        status=status.HTTP_404_NOT_FOUND
                    )

            # Получаем магазин, если указан
            store = None
            if store_id:
                try:
                    store = Store.objects.get(id=store_id)
                except Store.DoesNotExist:
                    return Response(
                        {"error": f"Магазин с ID {store_id} не найден"},
                        status=status.HTTP_404_NOT_FOUND
                    )

            # Создаем запись о расходе
            entry = FinanceEntry.objects.create(
                user=request.user,
                date=timezone.now().date(),
                entry_type='expense',
                amount=amount,
                city=city,
                store=store,
                note=note
            )

            update_partner_statistics(
                request.user,
                expense_amount=amount
            )
            # Если указан магазин, обновляем его статистику
            if store:
                update_store_daily_stats(store, timezone.now().date())
            return Response({
                "message": f"Расход на сумму {amount} успешно добавлен",
                "entry": FinanceEntrySerializer(entry).data
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {"error": f"Ошибка при добавлении расхода: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Добавляем в apps/finance/views.py

class DailyStatisticsView(APIView):
    """API для получения ежедневной статистики"""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Ежедневная статистика",
        manual_parameters=[
            openapi.Parameter(
                'date',
                openapi.IN_QUERY,
                description="Дата (YYYY-MM-DD), по умолчанию - сегодня",
                type=openapi.TYPE_STRING,
                format='date'
            )
        ],
        responses={200: "Статистика за день"}
    )
    def get(self, request):
        date_str = request.query_params.get('date')

        if date_str:
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {"error": "Некорректный формат даты. Используйте YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            date_obj = timezone.now().date()

        try:
            # Собираем статистику из разных источников

            # 1. Товары в каталоге партнера
            partner_products = PartnerProduct.objects.filter(partner=request.user)

            # 2. Запросы на товары в этот день
            from apps.orders.models import ProductRequest
            requests = ProductRequest.objects.filter(
                user=request.user,
                created_at__date=date_obj
            )

            # 3. Финансовые записи
            entries = FinanceEntry.objects.filter(
                user=request.user,
                date=date_obj
            )

            # 4. Долги магазинов
            from apps.stores.models import StoreDebt
            debts = StoreDebt.objects.filter(
                created_by=request.user
            )
            paid_debts = debts.filter(
                is_paid=True,
                paid_at__date=date_obj
            )

            # Расчет суммарных показателей
            total_quantity = sum(p.quantity for p in partner_products)
            total_sold = sum(p.sold_quantity for p in partner_products)
            total_damaged = sum(p.damaged_quantity for p in partner_products)
            total_bonus = sum(p.bonus_quantity for p in partner_products)
            total_returned = sum(p.returned_quantity for p in partner_products)
            total_remaining = sum(p.remaining_quantity for p in partner_products)

            # Финансовые показатели
            total_income = entries.filter(entry_type='income').aggregate(total=Sum('amount'))['total'] or 0
            total_sales = entries.filter(entry_type='sale').aggregate(total=Sum('amount'))['total'] or 0
            total_expense = entries.filter(entry_type='expense').aggregate(total=Sum('amount'))['total'] or 0
            total_debt = debts.filter(is_paid=False).aggregate(total=Sum('amount'))['total'] or 0
            total_paid_debt = paid_debts.aggregate(total=Sum('amount'))['total'] or 0

            # Расчет итоговых значений
            total_revenue = total_income + total_sales
            total_profit = total_revenue - total_expense

            # Формируем ответ
            return Response({
                "date": date_obj.isoformat(),
                "inventory": {
                    "total_quantity": total_quantity,
                    "total_sold": total_sold,
                    "total_damaged": total_damaged,
                    "total_bonus": total_bonus,
                    "total_returned": total_returned,
                    "total_remaining": total_remaining
                },
                "finance": {
                    "income": float(total_income),
                    "sales": float(total_sales),
                    "expense": float(total_expense),
                    "debt": float(total_debt),
                    "paid_debt": float(total_paid_debt),
                    "revenue": float(total_revenue),
                    "profit": float(total_profit)
                },
                "requests": {
                    "total": requests.count(),
                    "self_requests": requests.filter(request_type='SELF').count(),
                    "store_requests": requests.filter(request_type='STORE').count(),
                    "pending": requests.filter(status='pending').count(),
                    "approved": requests.filter(status='approved').count(),
                    "received": requests.filter(status='received').count()
                }
            })
        except Exception as e:
            return Response(
                {"error": f"Ошибка при получении статистики: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# В apps/finance/views.py

class PartnerStatisticsView(APIView):
    """API для получения статистики партнера"""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Статистика партнера",
        manual_parameters=[
            openapi.Parameter(
                'date',
                openapi.IN_QUERY,
                description="Дата (YYYY-MM-DD), по умолчанию - сегодня",
                type=openapi.TYPE_STRING,
                format='date'
            )
        ],
        responses={200: "Статистика партнера"}
    )
    def get(self, request):
        date_str = request.query_params.get('date')

        if date_str:
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {"error": "Некорректный формат даты. Используйте YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            date_obj = timezone.now().date()

        try:
            # Обновляем статистику перед выдачей
            from apps.finance.services import update_partner_daily_stats
            stats = update_partner_daily_stats(request.user, date_obj)

            # Формируем данные для ответа
            return Response({
                "date": date_obj.isoformat(),
                "requested": {
                    "quantity": stats.total_requested_quantity,
                    "amount": float(stats.total_requested_amount),
                    "details": stats.detailed_data.get('requested', {})
                },
                "sold": {
                    "quantity": stats.total_sold_quantity,
                    "amount": float(stats.total_sold_amount),
                    "details": stats.detailed_data.get('sold', {})
                },
                "expenses": float(stats.total_expenses),
                "damaged": {
                    "quantity": stats.total_damaged_quantity,
                    "details": stats.detailed_data.get('damaged', {})
                },
                "bonus": {
                    "quantity": stats.total_bonus_quantity
                },
                "remaining": {
                    "quantity": stats.total_remaining_quantity,
                    "details": stats.detailed_data.get('remaining', {})
                },
                "profit": float(stats.profit)
            })
        except Exception as e:
            return Response(
                {"error": f"Ошибка при получении статистики: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )