# apps/finance/views.py
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions, filters, viewsets
from django.utils import timezone
from datetime import datetime
from django.core.cache import cache
from datetime import timedelta
from .models import PartnerExpense
from .serializers import PartnerExpenseSerializer
from .services import PartnerStatisticsService, AdminStatisticsService
from apps.products.permissions import IsAdminUser, IsPartnerUser, IsOwnerOrAdmin
from rest_framework.decorators import action


# Обновление файла apps/finance/views.py

# Добавление периодов выбора даты в представлениях статистики
# Внутри класса PartnerStatisticsView и AdminFinanceStatisticsView

class PartnerStatisticsView(APIView):
    """Представление для получения статистики партнера"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk=None):
        # Проверка прав доступа
        user = request.user

        # Если указан конкретный партнер, проверяем права
        if pk:
            if user.role != 'admin' and user.id != int(pk):
                return Response(
                    {"detail": "У вас нет прав для просмотра статистики этого партнера"},
                    status=status.HTTP_403_FORBIDDEN
                )
            partner_id = pk
        else:
            # Если партнер не указан, используем текущего пользователя
            if user.role != 'partner':
                return Response(
                    {"detail": "Только партнеры могут просматривать свою статистику"},
                    status=status.HTTP_403_FORBIDDEN
                )
            partner_id = user.id

        # Получаем параметры запроса
        date_str = request.query_params.get('date')
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        period = request.query_params.get('period')

        # Новые параметры для гибкого выбора периода
        timespan = request.query_params.get('timespan', 'today')  # По умолчанию - сегодня

        # Проверка кэша
        cache_key = f"partner_stats_{partner_id}_{period or ''}_{timespan or ''}_{date_str or ''}_{start_date_str or ''}_{end_date_str or ''}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return Response(cached_data)

        # Обработка параметров даты
        date = None
        date_range = None

        # Если указан timespan, используем его для определения периода
        if timespan and not (date_str or start_date_str or period):
            today = timezone.now().date()

            if timespan == 'today':
                date = today
            elif timespan == 'yesterday':
                date = today - timedelta(days=1)
            elif timespan == 'week':
                # Последние 7 дней
                end_date = today
                start_date = today - timedelta(days=6)
                date_range = (start_date, end_date)
            elif timespan == 'month':
                # Последние 30 дней
                end_date = today
                start_date = today - timedelta(days=29)
                date_range = (start_date, end_date)
            elif timespan == 'six_months':
                # Последние 6 месяцев
                end_date = today
                start_date = today - timedelta(days=180)
                date_range = (start_date, end_date)
            elif timespan == 'year':
                # Последний год
                end_date = today
                start_date = today - timedelta(days=365)
                date_range = (start_date, end_date)
            else:
                # По умолчанию - сегодня
                date = today

        # Стандартная обработка, если не использовался timespan
        elif date_str:
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {"detail": "Неверный формат даты. Используйте YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        elif start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

                if start_date > end_date:
                    return Response(
                        {"detail": "Начальная дата не может быть позже конечной даты"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                date_range = (start_date, end_date)
            except ValueError:
                return Response(
                    {"detail": "Неверный формат даты. Используйте YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        elif period:
            # Оставляем существующую логику для параметра period
            pass
        else:
            # По умолчанию используем сегодняшнюю дату
            date = timezone.now().date()

        # Получаем статистику
        service = PartnerStatisticsService()
        statistics = service.get_partner_statistics(
            partner_id=partner_id,
            date=date,
            date_range=date_range,
            period=period
        )

        # Если есть ошибка, возвращаем её
        if "error" in statistics:
            return Response(
                {"detail": statistics["error"]},
                status=status.HTTP_404_NOT_FOUND
            )

        # Добавляем информацию о выбранном периоде для UI
        statistics["selected_timespan"] = timespan or period or (date_str and "custom_date") or (
                    (start_date_str and end_date_str) and "custom_range") or "today"

        # Кэшируем результат на 15 минут
        cache.set(cache_key, statistics, 60 * 15)

        return Response(statistics)


class AdminFinanceStatisticsView(APIView):
    """Представление для получения финансовой статистики администратора"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        """Получение общей статистики администратора"""
        user = request.user

        # Получаем параметры запроса
        date_str = request.query_params.get('date')
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        period = request.query_params.get('period')

        # Новые параметры для гибкого выбора периода
        timespan = request.query_params.get('timespan', 'today')  # По умолчанию - сегодня

        # Проверка кэша
        cache_key = f"admin_stats_{user.id}_{period or ''}_{timespan or ''}_{date_str or ''}_{start_date_str or ''}_{end_date_str or ''}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return Response(cached_data)

        # Обработка параметров даты
        date = None
        date_range = None

        # Если указан timespan, используем его для определения периода
        if timespan and not (date_str or start_date_str or period):
            today = timezone.now().date()

            if timespan == 'today':
                date = today
            elif timespan == 'yesterday':
                date = today - timedelta(days=1)
            elif timespan == 'week':
                # Последние 7 дней
                end_date = today
                start_date = today - timedelta(days=6)
                date_range = (start_date, end_date)
            elif timespan == 'month':
                # Последние 30 дней
                end_date = today
                start_date = today - timedelta(days=29)
                date_range = (start_date, end_date)
            elif timespan == 'six_months':
                # Последние 6 месяцев
                end_date = today
                start_date = today - timedelta(days=180)
                date_range = (start_date, end_date)
            elif timespan == 'year':
                # Последний год
                end_date = today
                start_date = today - timedelta(days=365)
                date_range = (start_date, end_date)
            else:
                # По умолчанию - сегодня
                date = today

        # Стандартная обработка, если не использовался timespan
        elif date_str:
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {"detail": "Неверный формат даты. Используйте YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        elif start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

                if start_date > end_date:
                    return Response(
                        {"detail": "Начальная дата не может быть позже конечной даты"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                date_range = (start_date, end_date)
            except ValueError:
                return Response(
                    {"detail": "Неверный формат даты. Используйте YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        elif period:
            # Оставляем существующую логику для параметра period
            pass
        else:
            # По умолчанию используем сегодняшнюю дату
            date = timezone.now().date()

        # Получаем статистику
        service = AdminStatisticsService()
        statistics = service.get_admin_statistics(
            admin_id=user.id,
            date=date,
            date_range=date_range,
            period=period
        )

        # Если есть ошибка, возвращаем её
        if "error" in statistics:
            return Response(
                {"detail": statistics["error"]},
                status=status.HTTP_404_NOT_FOUND
            )

        # Добавляем информацию о выбранном периоде для UI
        statistics["selected_timespan"] = timespan or period or (date_str and "custom_date") or (
                    (start_date_str and end_date_str) and "custom_range") or "today"

        # Кэшируем результат на 15 минут
        cache.set(cache_key, statistics, 60 * 15)

        return Response(statistics)


class AdminPartnersStatisticsView(APIView):
    """Представление для получения статистики по партнерам для администратора"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        """Получение статистики по всем партнерам"""
        user = request.user

        # Получаем параметры запроса
        date_str = request.query_params.get('date')
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        period = request.query_params.get('period')

        # Новые параметры для гибкого выбора периода
        timespan = request.query_params.get('timespan', 'today')  # По умолчанию - сегодня

        # Проверка кэша
        cache_key = f"admin_partners_stats_{user.id}_{period or ''}_{timespan or ''}_{date_str or ''}_{start_date_str or ''}_{end_date_str or ''}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return Response(cached_data)

        # Обработка параметров даты
        date = None
        date_range = None

        # Если указан timespan, используем его для определения периода
        if timespan and not (date_str or start_date_str or period):
            today = timezone.now().date()

            if timespan == 'today':
                date = today
            elif timespan == 'yesterday':
                date = today - timedelta(days=1)
            elif timespan == 'week':
                # Последние 7 дней
                end_date = today
                start_date = today - timedelta(days=6)
                date_range = (start_date, end_date)
            elif timespan == 'month':
                # Последние 30 дней
                end_date = today
                start_date = today - timedelta(days=29)
                date_range = (start_date, end_date)
            elif timespan == 'six_months':
                # Последние 6 месяцев
                end_date = today
                start_date = today - timedelta(days=180)
                date_range = (start_date, end_date)
            elif timespan == 'year':
                # Последний год
                end_date = today
                start_date = today - timedelta(days=365)
                date_range = (start_date, end_date)
            else:
                # По умолчанию - сегодня
                date = today

        # Стандартная обработка, если не использовался timespan
        elif date_str:
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {"detail": "Неверный формат даты. Используйте YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        elif start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

                if start_date > end_date:
                    return Response(
                        {"detail": "Начальная дата не может быть позже конечной даты"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                date_range = (start_date, end_date)
            except ValueError:
                return Response(
                    {"detail": "Неверный формат даты. Используйте YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        elif period:
            # Оставляем существующую логику для параметра period
            pass
        else:
            # По умолчанию используем сегодняшнюю дату
            date = timezone.now().date()

        # Получаем статистику
        service = AdminStatisticsService()
        statistics = service.get_partners_statistics(
            admin_id=user.id,
            date=date,
            date_range=date_range,
            period=period
        )

        # Если есть ошибка, возвращаем её
        if "error" in statistics:
            return Response(
                {"detail": statistics["error"]},
                status=status.HTTP_404_NOT_FOUND
            )

        # Добавляем информацию о выбранном периоде для UI
        statistics["selected_timespan"] = timespan or period or (date_str and "custom_date") or (
                    (start_date_str and end_date_str) and "custom_range") or "today"

        # Кэшируем результат на 15 минут
        cache.set(cache_key, statistics, 60 * 15)

        return Response(statistics)


# Добавление в файл apps/finance/views.py

class PartnerExpenseViewSet(viewsets.ModelViewSet):
    """
    Представление для работы с расходами партнера
    """
    serializer_class = PartnerExpenseSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['expense_date']
    ordering_fields = ['expense_date', 'amount', 'created_at']
    ordering = ['-expense_date']

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return PartnerExpense.objects.all()
        return PartnerExpense.objects.filter(partner=user)

    def get_permissions(self):
        if self.action in ['destroy', 'update', 'partial_update']:
            return [IsOwnerOrAdmin()]
        return [permissions.IsAuthenticated()]

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Получение сводки по расходам за период"""
        # Получаем параметры запроса
        date_str = request.query_params.get('date')
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        period = request.query_params.get('period')
        timespan = request.query_params.get('timespan', 'today')  # По умолчанию - сегодня

        # Определяем временные рамки
        today = timezone.now().date()

        if timespan == 'today':
            start_date = end_date = today
        elif timespan == 'yesterday':
            start_date = end_date = today - timedelta(days=1)
        elif timespan == 'week':
            # Последние 7 дней
            end_date = today
            start_date = today - timedelta(days=6)
        elif timespan == 'month':
            # Последние 30 дней
            end_date = today
            start_date = today - timedelta(days=29)
        elif timespan == 'six_months':
            # Последние 6 месяцев
            end_date = today
            start_date = today - timedelta(days=180)
        elif timespan == 'year':
            # Последний год
            end_date = today
            start_date = today - timedelta(days=365)
        elif date_str:
            try:
                start_date = end_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {"detail": "Неверный формат даты. Используйте YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        elif start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                if start_date > end_date:
                    return Response(
                        {"detail": "Начальная дата не может быть позже конечной даты"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except ValueError:
                return Response(
                    {"detail": "Неверный формат даты. Используйте YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            start_date = end_date = today

        # Получаем расходы за указанный период
        queryset = self.get_queryset().filter(
            expense_date__gte=start_date,
            expense_date__lte=end_date
        )

        # Расчет общих показателей
        total_amount = sum(expense.amount for expense in queryset)
        count = queryset.count()

        # Группировка по дням
        expenses_by_date = {}
        for expense in queryset:
            date_key = expense.expense_date.isoformat()
            if date_key not in expenses_by_date:
                expenses_by_date[date_key] = {
                    "date": date_key,
                    "total": 0,
                    "count": 0,
                    "expenses": []
                }

            expenses_by_date[date_key]["total"] += float(expense.amount)
            expenses_by_date[date_key]["count"] += 1
            expenses_by_date[date_key]["expenses"].append({
                "id": expense.id,
                "amount": float(expense.amount),
                "description": expense.description,
                "created_at": expense.created_at.isoformat()
            })

        return Response({
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "timespan": timespan
            },
            "total_amount": float(total_amount),
            "count": count,
            "expenses_by_date": list(expenses_by_date.values())
        })