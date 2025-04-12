# apps/finance/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.utils import timezone
from datetime import datetime
from django.core.cache import cache

from .services import PartnerStatisticsService, AdminStatisticsService
from apps.products.permissions import IsAdminUser, IsPartnerUser


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

        # Проверка кэша
        cache_key = f"partner_stats_{partner_id}_{period or ''}_{date_str or ''}_{start_date_str or ''}_{end_date_str or ''}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return Response(cached_data)

        # Обработка параметров даты
        date = None
        date_range = None

        if date_str:
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

        # Кэшируем результат на 15 минут
        cache.set(cache_key, statistics, 60 * 15)

        return Response(statistics)


# apps/finance/views.py - дополним существующий файл

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

        # Проверка кэша
        cache_key = f"admin_stats_{user.id}_{period or ''}_{date_str or ''}_{start_date_str or ''}_{end_date_str or ''}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return Response(cached_data)

        # Обработка параметров даты
        date = None
        date_range = None

        if date_str:
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

        # Проверка кэша
        cache_key = f"admin_partners_stats_{user.id}_{period or ''}_{date_str or ''}_{start_date_str or ''}_{end_date_str or ''}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return Response(cached_data)

        # Обработка параметров даты
        date = None
        date_range = None

        if date_str:
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

        # Кэшируем результат на 15 минут
        cache.set(cache_key, statistics, 60 * 15)

        return Response(statistics)