# apps/finance/views.py
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions, filters, viewsets, serializers # Добавили serializers
from django.utils import timezone
from datetime import datetime, timedelta, date, time # Добавили date, time
from django.core.cache import cache
from decimal import Decimal # Добавили Decimal
from .models import PartnerExpense
from .serializers import PartnerExpenseSerializer
from .services import PartnerStatisticsService, AdminStatisticsService
# Импортируем разрешения из users
from apps.users.permissions import IsAdminUser, IsPartnerUser, IsOwnerOrAdmin
from rest_framework.decorators import action
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import logging
from django.db.models import Sum, Count
from django.core.exceptions import  PermissionDenied


logger = logging.getLogger(__name__)

# --- Хелпер функция для обработки дат ---
def get_date_range_from_params(request):
    """
    Определяет диапазон дат на основе параметров запроса:
    timespan, date, start_date, end_date, period.
    ПО УМОЛЧАНИЮ возвращает диапазон за ВСЕ ВРЕМЯ.
    Возвращает tuple (start_date, end_date, selected_timespan_label).
    start_date может быть None, если данных нет совсем.
    """
    date_str = request.query_params.get('date')
    start_date_str = request.query_params.get('start_date')
    end_date_str = request.query_params.get('end_date')
    period = request.query_params.get('period') # Старый параметр
    # --- ИЗМЕНЕНИЕ: Устанавливаем 'all' как timespan по умолчанию ---
    timespan = request.query_params.get('timespan', 'all')

    # ИСПРАВЛЕНИЕ: Используем localdate вместо now().date() для корректного учета часового пояса
    today = timezone.localdate()
    start_date = None # Инициализируем как None для 'all' по умолчанию
    end_date = today # Конечная дата всегда today или указанная
    selected_timespan_label = timespan # Используем переданный или 'all'

    # --- Логика обработки параметров ---
    # Сначала обрабатываем явные даты или старый период, они имеют приоритет над timespan='all'
    if date_str:
        try:
            start_date = end_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            selected_timespan_label = "custom_date" # Перезаписываем метку
            timespan = None # Сбрасываем timespan, т.к. дата важнее
        except ValueError:
            raise serializers.ValidationError({"detail": "Неверный формат даты. Используйте YYYY-MM-DD"})
    elif start_date_str and end_date_str:
         try:
             start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
             end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
             if start_date > end_date:
                 raise serializers.ValidationError({"detail": "Начальная дата не может быть позже конечной."})
             selected_timespan_label = "custom_range"
             timespan = None # Сбрасываем timespan
         except ValueError:
             raise serializers.ValidationError({"detail": "Неверный формат даты. Используйте YYYY-MM-DD"})
    elif period: # Обработка старого параметра period
         try:
             start_date, end_date = PartnerStatisticsService()._get_dates_from_period(period)
             selected_timespan_label = period
             timespan = None # Сбрасываем timespan
         except ValueError:
             raise serializers.ValidationError({"detail": f"Неизвестный период: {period}"})

    # Если явные даты/период не были заданы, обрабатываем timespan
    if timespan:
        selected_timespan_label = timespan # Метка соответствует timespan
        if timespan == 'today':
            start_date = end_date = today
        elif timespan == 'yesterday':
            start_date = end_date = today - timedelta(days=1)
        elif timespan == 'week':
            start_date = today - timedelta(days=today.weekday())
            end_date = today
        elif timespan == 'last_week':
             # Корректный расчет прошлой недели (с пн по вс)
             end_date = today - timedelta(days=today.weekday() + 1)
             start_date = end_date - timedelta(days=6)
        elif timespan == 'month':
            start_date = today.replace(day=1)
            end_date = today
        elif timespan == 'last_month':
            end_date = today.replace(day=1) - timedelta(days=1)
            start_date = end_date.replace(day=1)
        elif timespan == 'six_months':
             end_date = today
             # Отсчитываем 6 месяцев назад
             month = end_date.month - 6
             year = end_date.year
             if month <= 0:
                  month += 12
                  year -= 1
             # Устанавливаем первый день того месяца
             try:
                 start_date = end_date.replace(year=year, month=month, day=1)
             except ValueError: # Если в том месяце нет такого дня (напр. 31)
                 # Берем последний день предыдущего месяца
                 start_date = end_date.replace(year=year, month=month+1, day=1) - timedelta(days=1)

        elif timespan == 'year':
             start_date = today.replace(month=1, day=1)
             end_date = today
        elif timespan == 'last_year':
             year = today.year - 1
             start_date = date(year, 1, 1)
             end_date = date(year, 12, 31)
        elif timespan == 'all':
             start_date = None # Оставляем None, сервис определит самую раннюю дату
             end_date = today
        else: # Неизвестный timespan
             logger.warning(f"Получен неизвестный timespan: '{timespan}'. Используется 'all'.")
             start_date = None
             end_date = today
             selected_timespan_label = 'all'

    # --- Определение реальной начальной даты для 'all' ---
    if start_date is None and selected_timespan_label == 'all':
         from apps.orders.models import Order # Локальный импорт
         # Ищем самую раннюю запись (можно проверить и другие модели)
         first_entry = Order.objects.order_by('created_at').values('created_at').first()
         if first_entry and first_entry['created_at']:
              start_date = first_entry['created_at'].date()
              print(f"[get_date_range_from_params] Для 'all' определена start_date по первому заказу: {start_date}")
         else:
              # Если вообще нет данных, ставим условную дату
              start_date = date(2020, 1, 1)
              print(f"[get_date_range_from_params] Для 'all' данных не найдено, используется start_date: {start_date}")

    # Дополнительная проверка на случай, если start_date все еще None (хотя не должно)
    if start_date is None:
         start_date = date(2020, 1, 1)
         logger.error("[get_date_range_from_params] start_date осталась None, установлена на 2020-01-01.")

    print(f"[get_date_range_from_params] Возвращает: start={start_date}, end={end_date}, label={selected_timespan_label}")
    return start_date, end_date, selected_timespan_label
# --- Конец хелпер функции ---


class PartnerStatisticsView(APIView):
    """Представление для получения статистики партнера"""
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Статистика партнера",
        manual_parameters=[
             openapi.Parameter('timespan', openapi.IN_QUERY, description="Период (today, yesterday, week, last_week, month, last_month, six_months, year, last_year, all)", type=openapi.TYPE_STRING, default='all'), # Указываем default='all'
             openapi.Parameter('date', openapi.IN_QUERY, description="Конкретная дата (YYYY-MM-DD)", type=openapi.TYPE_STRING, format='date'),
             openapi.Parameter('start_date', openapi.IN_QUERY, description="Начальная дата (YYYY-MM-DD)", type=openapi.TYPE_STRING, format='date'),
             openapi.Parameter('end_date', openapi.IN_QUERY, description="Конечная дата (YYYY-MM-DD)", type=openapi.TYPE_STRING, format='date'),
             openapi.Parameter('period', openapi.IN_QUERY, description="Старый параметр периода (this_week и т.д.)", type=openapi.TYPE_STRING),
         ]
    )
    def get(self, request, pk=None):
        user = request.user
        if pk: # Если ID передан в URL (для админа)
            if user.role != 'admin' and user.id != int(pk):
                return Response({"detail": "У вас нет прав для просмотра статистики этого партнера"}, status=status.HTTP_403_FORBIDDEN)
            partner_id = pk
        else: # Если ID не передан, берем текущего пользователя
            if user.role != 'partner':
                return Response({"detail": "Укажите ID партнера или войдите как партнер"}, status=status.HTTP_403_FORBIDDEN)
            partner_id = user.id

        # Получаем диапазон дат из хелпера
        try:
            start_date, end_date, selected_timespan = get_date_range_from_params(request)
        except serializers.ValidationError as e:
             return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

        # Формируем ключ кэша, включая None для start_date, если timespan='all'
        date_cache_key = f"{start_date.isoformat() if start_date else 'all'}_{end_date.isoformat()}"
        cache_key = f"partner_stats_{partner_id}_{date_cache_key}"
        # Закомментируем кэш на время отладки
        # cached_data = cache.get(cache_key)
        # if cached_data:
        #     cached_data["selected_timespan"] = selected_timespan
        #     print(f"[View] Возвращены кэшированные данные для ключа {cache_key}")
        #     return Response(cached_data)

        # Получаем статистику
        service = PartnerStatisticsService()
        # Передаем кортеж (start_date, end_date)
        statistics = service.get_partner_statistics(
            partner_id=partner_id,
            date_range=(start_date, end_date)
        )

        if "error" in statistics:
            return Response({"detail": statistics["error"]}, status=status.HTTP_404_NOT_FOUND)

        # Добавляем выбранный период
        statistics["selected_timespan"] = selected_timespan

        # Кэшируем результат на 15 минут
        # cache.set(cache_key, statistics, 60 * 15)
        # print(f"[View] Данные сохранены в кэш по ключу {cache_key}")

        return Response(statistics)


class AdminFinanceStatisticsView(APIView):
    """Представление для получения финансовой статистики администратора"""
    permission_classes = [IsAdminUser]

    @swagger_auto_schema(
        operation_summary="Общая финансовая статистика админа",
         manual_parameters=[
             openapi.Parameter('timespan', openapi.IN_QUERY, description="Период (today, yesterday, week, last_week, month, last_month, six_months, year, last_year, all)", type=openapi.TYPE_STRING, default='all'),
             openapi.Parameter('date', openapi.IN_QUERY, description="Конкретная дата (YYYY-MM-DD)", type=openapi.TYPE_STRING, format='date'),
             openapi.Parameter('start_date', openapi.IN_QUERY, description="Начальная дата (YYYY-MM-DD)", type=openapi.TYPE_STRING, format='date'),
             openapi.Parameter('end_date', openapi.IN_QUERY, description="Конечная дата (YYYY-MM-DD)", type=openapi.TYPE_STRING, format='date'),
             openapi.Parameter('period', openapi.IN_QUERY, description="Старый параметр периода (this_week и т.д.)", type=openapi.TYPE_STRING),
         ]
    )
    def get(self, request):
        user = request.user
        try:
            start_date, end_date, selected_timespan = get_date_range_from_params(request)
        except serializers.ValidationError as e:
             return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

        date_cache_key = f"{start_date.isoformat() if start_date else 'all'}_{end_date.isoformat()}"
        cache_key = f"admin_stats_{user.id}_{date_cache_key}"
        # Закомментируем кэш
        # cached_data = cache.get(cache_key)
        # if cached_data:
        #     cached_data["selected_timespan"] = selected_timespan
        #     return Response(cached_data)

        service = AdminStatisticsService()
        statistics = service.get_admin_statistics(
            admin_id=user.id,
            date_range=(start_date, end_date)
        )

        if "error" in statistics:
            return Response({"detail": statistics["error"]}, status=status.HTTP_404_NOT_FOUND)

        statistics["selected_timespan"] = selected_timespan
        # cache.set(cache_key, statistics, 60 * 15)

        return Response(statistics)


class AdminPartnersStatisticsView(APIView):
    """Представление для получения статистики по партнерам для администратора"""
    permission_classes = [IsAdminUser]

    @swagger_auto_schema(
         operation_summary="Статистика по всем партнерам для админа",
         manual_parameters=[
             openapi.Parameter('timespan', openapi.IN_QUERY, description="Период (today, yesterday, week, last_week, month, last_month, six_months, year, last_year, all)", type=openapi.TYPE_STRING, default='all'),
             openapi.Parameter('date', openapi.IN_QUERY, description="Конкретная дата (YYYY-MM-DD)", type=openapi.TYPE_STRING, format='date'),
             openapi.Parameter('start_date', openapi.IN_QUERY, description="Начальная дата (YYYY-MM-DD)", type=openapi.TYPE_STRING, format='date'),
             openapi.Parameter('end_date', openapi.IN_QUERY, description="Конечная дата (YYYY-MM-DD)", type=openapi.TYPE_STRING, format='date'),
             openapi.Parameter('period', openapi.IN_QUERY, description="Старый параметр периода (this_week и т.д.)", type=openapi.TYPE_STRING),
         ]
    )
    def get(self, request):
        user = request.user
        try:
            start_date, end_date, selected_timespan = get_date_range_from_params(request)
        except serializers.ValidationError as e:
             return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

        date_cache_key = f"{start_date.isoformat() if start_date else 'all'}_{end_date.isoformat()}"
        cache_key = f"admin_partners_stats_{user.id}_{date_cache_key}"
        # Закомментируем кэш
        # cached_data = cache.get(cache_key)
        # if cached_data:
        #     cached_data["selected_timespan"] = selected_timespan
        #     return Response(cached_data)

        service = AdminStatisticsService()
        statistics = service.get_partners_statistics(
            admin_id=user.id,
            date_range=(start_date, end_date)
        )

        if "error" in statistics:
            return Response({"detail": statistics["error"]}, status=status.HTTP_404_NOT_FOUND)

        statistics["selected_timespan"] = selected_timespan
        # cache.set(cache_key, statistics, 60 * 15)

        return Response(statistics)


# --- PartnerExpenseViewSet ---
# apps/finance/views.py
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions, filters, viewsets, serializers
from django.utils import timezone
from datetime import datetime, timedelta, date, time # Добавили date, time
from django.core.cache import cache
from decimal import Decimal
from .models import PartnerExpense, User # Добавили User
from .serializers import PartnerExpenseSerializer
from .services import PartnerStatisticsService, AdminStatisticsService
# Импортируем разрешения из users
from apps.users.permissions import IsAdminUser, IsPartnerUser, IsOwnerOrAdmin
from rest_framework.decorators import action
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import logging
from django.db.models import Sum, Count, F # Добавили F, Sum, Count
from django.core.exceptions import PermissionDenied # Импортируем PermissionDenied
from django.db.models.functions import TruncDate # Для возможной группировки в БД

logger = logging.getLogger(__name__)

# --- Хелпер функция get_date_range_from_params ---
# (Код функции остается как в предыдущем ответе)
def get_date_range_from_params(request):
    # ... (код функции) ...
    date_str = request.query_params.get('date')
    start_date_str = request.query_params.get('start_date')
    end_date_str = request.query_params.get('end_date')
    period = request.query_params.get('period')
    timespan = request.query_params.get('timespan', 'all')
    today = timezone.localdate()
    start_date = None
    end_date = today
    selected_timespan_label = timespan

    if date_str:
        try:
            start_date = end_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            selected_timespan_label = "custom_date"
            timespan = None
        except ValueError:
            raise serializers.ValidationError({"detail": "Неверный формат даты. Используйте YYYY-MM-DD"})
    elif start_date_str and end_date_str:
         try:
             start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
             end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
             if start_date > end_date:
                 raise serializers.ValidationError({"detail": "Начальная дата не может быть позже конечной."})
             selected_timespan_label = "custom_range"
             timespan = None
         except ValueError:
             raise serializers.ValidationError({"detail": "Неверный формат даты. Используйте YYYY-MM-DD"})
    elif period:
         try:
             start_date, end_date = PartnerStatisticsService()._get_dates_from_period(period)
             selected_timespan_label = period
             timespan = None
         except ValueError:
             raise serializers.ValidationError({"detail": f"Неизвестный период: {period}"})

    if timespan:
        selected_timespan_label = timespan
        if timespan == 'today': start_date = end_date = today
        elif timespan == 'yesterday': start_date = end_date = today - timedelta(days=1)
        elif timespan == 'week': start_date = today - timedelta(days=today.weekday()); end_date = today
        elif timespan == 'last_week': end_date = today - timedelta(days=today.weekday() + 1); start_date = end_date - timedelta(days=6)
        elif timespan == 'month': start_date = today.replace(day=1); end_date = today
        elif timespan == 'last_month': end_date = today.replace(day=1) - timedelta(days=1); start_date = end_date.replace(day=1)
        elif timespan == 'six_months':
             end_date = today
             month = end_date.month - 6; year = end_date.year
             if month <= 0: month += 12; year -= 1
             try: start_date = end_date.replace(year=year, month=month, day=1)
             except ValueError: start_date = end_date.replace(year=year, month=month+1, day=1) - timedelta(days=1)
        elif timespan == 'year': start_date = today.replace(month=1, day=1); end_date = today
        elif timespan == 'last_year': year = today.year - 1; start_date = date(year, 1, 1); end_date = date(year, 12, 31)
        elif timespan == 'all': start_date = None; end_date = today
        else: logger.warning(f"Неизвестный timespan: '{timespan}'. Используется 'all'."); start_date = None; end_date = today; selected_timespan_label = 'all'

    if start_date is None and selected_timespan_label == 'all':
         from apps.orders.models import Order
         first_entry = Order.objects.order_by('created_at').values('created_at').first()
         print(f"[get_date_range_from_params] Найденная первая запись для 'all': {first_entry}")
         if first_entry and first_entry['created_at']: start_date = first_entry['created_at'].date()
         else: start_date = date(2020, 1, 1)
         print(f"[get_date_range_from_params] Для 'all' определена start_date: {start_date}")

    if start_date is None: start_date = date(2020, 1, 1); logger.error("[get_date_range_from_params] start_date осталась None, установлена на 2020-01-01.")

    print(f"[get_date_range_from_params] Возвращает: start={start_date}, end={end_date}, label={selected_timespan_label}")
    return start_date, end_date, selected_timespan_label

# --- PartnerStatisticsView, AdminFinanceStatisticsView, AdminPartnersStatisticsView ---
# (Код этих Views остается как в предыдущих ответах)


# --- ИСПРАВЛЕННЫЙ PartnerExpenseViewSet ---
class PartnerExpenseViewSet(viewsets.ModelViewSet):
    """
    Представление для работы с расходами партнера.
    Список (list) возвращается сгруппированным по датам.
    Поддерживает фильтрацию по дате/периоду и partner (для админа).
    """
    serializer_class = PartnerExpenseSerializer
    # permission_classes определяется в get_permissions
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = {
        'expense_date': ['exact', 'gte', 'lte'],
        'partner': ['exact'], # Фильтр по партнеру (для админа)
    }
    search_fields = ['description']

    def get_queryset(self):
        """Базовый queryset, НЕ фильтрует по роли здесь."""
        # Фильтрация по роли будет в get_permissions и/или list/retrieve
        queryset = PartnerExpense.objects.select_related('partner')
        return queryset.order_by('-expense_date', '-created_at')

    def get_permissions(self):
        """Определяет права доступа для разных действий."""
        # --- ИЗМЕНЕНИЕ: Проверка для list/retrieve ---
        if self.action in ['list', 'retrieve']:
             # Разрешаем всем аутентифицированным, но get_queryset/list отфильтруют
            return [permissions.IsAuthenticated()]
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---
        elif self.action == 'create':
            # Создавать могут админы и партнеры (проверяется в perform_create)
            return [permissions.IsAuthenticated()]
        elif self.action in ['update', 'partial_update', 'destroy']:
            # Редактировать/удалять может владелец или админ
            return [IsOwnerOrAdmin()] # Проверяет поле 'partner'
        # По умолчанию (на всякий случай)
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        # Логика создания остается прежней
        user = self.request.user
        if user.role == 'admin':
            partner_id = self.request.data.get('partner')
            if not partner_id:
                 raise serializers.ValidationError({"partner": ["Это поле обязательно для администратора."]})
            try:
                 partner_obj = User.objects.get(id=int(partner_id), role='partner')
                 serializer.save(partner=partner_obj)
            except User.DoesNotExist:
                 raise serializers.ValidationError({"partner": f"Партнер с ID {partner_id} не найден."})
            except (ValueError, TypeError):
                 raise serializers.ValidationError({"partner": "Неверный ID партнера."})
        elif user.role == 'partner':
            serializer.save(partner=user)
        else:
            # Эта проверка дублируется в get_permissions, но для надежности
            raise PermissionDenied("У вас нет прав создавать расходы.")

    @swagger_auto_schema(
        operation_summary="Список расходов партнера (сгруппированный)",
        operation_description="""
        Возвращает список расходов, сгруппированный по датам.
        Партнер видит только свои расходы.
        Администратор видит все расходы, но может фильтровать по `partner=ID`.
        Поддерживает фильтрацию по дате/периоду (`timespan`, `date`, `start_date`, `end_date`) и `expense_date=YYYY-MM-DD`.
        Поддерживает поиск по описанию (`search`).
        """,
        manual_parameters=[
             openapi.Parameter('timespan', openapi.IN_QUERY, description="Период (today, yesterday, week, ..., all)", type=openapi.TYPE_STRING, default='all'),
             openapi.Parameter('date', openapi.IN_QUERY, description="Конкретная дата (YYYY-MM-DD)", type=openapi.TYPE_STRING, format='date'),
             openapi.Parameter('start_date', openapi.IN_QUERY, description="Начальная дата (YYYY-MM-DD)", type=openapi.TYPE_STRING, format='date'),
             openapi.Parameter('end_date', openapi.IN_QUERY, description="Конечная дата (YYYY-MM-DD)", type=openapi.TYPE_STRING, format='date'),
             openapi.Parameter('partner', openapi.IN_QUERY, description="Фильтр по ID партнера (только для админа)", type=openapi.TYPE_INTEGER),
             openapi.Parameter('expense_date', openapi.IN_QUERY, description="Точная дата расхода (YYYY-MM-DD)", type=openapi.TYPE_STRING, format='date'),
             openapi.Parameter('search', openapi.IN_QUERY, description="Поиск по описанию", type=openapi.TYPE_STRING),
        ]
    )
    def list(self, request, *args, **kwargs):
        """
        Переопределенный метод для возврата сгруппированного списка расходов.
        Применяет фильтрацию по роли и параметрам.
        """
        user = request.user

        # 1. Получаем диапазон дат
        try:
            start_date, end_date, selected_timespan = get_date_range_from_params(request)
        except serializers.ValidationError as e:
             return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

        # 2. Получаем базовый queryset (все расходы)
        queryset = self.get_queryset() # Вызываем get_queryset без изменений

        # --- ИЗМЕНЕНИЕ: Явная фильтрация по роли ПЕРЕД стандартными фильтрами ---
        if user.role == 'partner':
             queryset = queryset.filter(partner=user)
             # Если партнер передал ?partner=ID, он все равно увидит только свои
        elif user.role != 'admin':
             queryset = PartnerExpense.objects.none() # Другие роли ничего не видят
        # Для админа оставляем queryset как есть (все расходы)
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---

        # 3. Применяем стандартные фильтры DRF (expense_date, search, partner для админа)
        # filter_queryset применит фильтр ?partner=ID из запроса, ТОЛЬКО ЕСЛИ user.role == 'admin'
        # (т.к. для партнера queryset уже отфильтрован)
        queryset = self.filter_queryset(queryset)

        # 4. Фильтруем queryset по диапазону дат (если expense_date не был точным фильтром)
        if 'expense_date' not in request.query_params:
            queryset = queryset.filter(
                expense_date__gte=start_date,
                expense_date__lte=end_date
            )

        # 5. Расчет общих показателей
        summary_agg = queryset.aggregate(
             total_amount=Sum('amount', default=Decimal('0.00')),
             count=Count('id')
         )
        total_amount = summary_agg['total_amount']
        count = summary_agg['count']

        # 6. Группировка по дням
        expenses_by_date = {}
        expenses_list = queryset.values(
             'id', 'amount', 'description', 'expense_date', 'created_at',
             'partner_id', 'partner__first_name', 'partner__last_name'
         ) # Сортировка уже применена в get_queryset

        for expense in expenses_list:
            date_key = expense['expense_date'].isoformat()
            day_summary = expenses_by_date.setdefault(date_key, {
                 "date": date_key, "total": 0.0, "count": 0, "expenses": []
             })
            amount_float = float(expense['amount'] or 0)
            day_summary["total"] += amount_float
            day_summary["count"] += 1
            expense_detail = {
                "id": expense['id'],
                "amount": amount_float,
                "description": expense['description'],
                "created_at": expense['created_at'].isoformat(),
                "partner_id": expense['partner_id'],
                "partner_name": f"{expense['partner__first_name']} {expense['partner__last_name']}".strip()
            }
            day_summary["expenses"].append(expense_detail)

        # 7. Формируем итоговый ответ
        response_data = {
             "filters": request.query_params.dict(),
             "period": {"start_date": start_date.isoformat() if start_date else None,"end_date": end_date.isoformat(),"selected_timespan": selected_timespan},
             "total_amount": float(total_amount),
             "count": count,
             "expenses_by_date": list(expenses_by_date.values())
         }

        return Response(response_data)
