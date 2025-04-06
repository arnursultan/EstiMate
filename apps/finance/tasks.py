from celery import shared_task
from django.utils import timezone
from apps.users.models import User
from apps.stores.models import Store
from apps.orders.models import ProductRequest
from apps.finance.models import ArchivedDailySummary
from .services import generate_partner_finance_stat, generate_store_finance_stat
import logging

logger = logging.getLogger(__name__)


@shared_task
def archive_daily_data():
    """
    Архивирует ежедневные данные и подготавливает систему к новому дню
    """
    yesterday = timezone.now().date() - timezone.timedelta(days=1)
    logger.info(f"Начало архивации данных за {yesterday}")

    try:
        # Для каждого партнера создаем архивную запись
        users_count = 0
        for user in User.objects.filter(is_active=True, is_staff=False):
            try:
                # Получаем данные за вчерашний день
                requests = ProductRequest.objects.filter(
                    user=user,
                    created_at__date=yesterday
                )

                # Рассчитываем суммы
                total_sales = sum(
                    float(r.total_price) for r in requests
                    if r.status == 'received' and r.payment_method == 'cash'
                )

                # Получаем расходы
                expenses = user.manual_finance_entries.filter(date=yesterday)
                total_expenses = sum(float(e.expense) for e in expenses)

                # Расчет прибыли
                total_profit = total_sales - total_expenses

                # Сохраняем архивную запись
                ArchivedDailySummary.objects.update_or_create(
                    user=user,
                    date=yesterday,
                    defaults={
                        'total_requests': requests.count(),
                        'total_sales': total_sales,
                        'total_expenses': total_expenses,
                        'total_profit': total_profit,
                        'data': {
                            'requests_details': [
                                {
                                    'id': r.id,
                                    'product_name': r.product.name,
                                    'quantity': r.quantity,
                                    'bonus_quantity': r.bonus_quantity,
                                    'total_price': float(r.total_price),
                                    'status': r.status
                                } for r in requests
                            ],
                            'expenses_details': [
                                {
                                    'id': e.id,
                                    'amount': float(e.expense),
                                    'note': e.note
                                } for e in expenses
                            ]
                        }
                    }
                )
                users_count += 1
            except Exception as e:
                logger.error(f"Ошибка при архивации данных для пользователя {user.id}: {str(e)}")

        # Обновляем ежедневную статистику
        run_daily_finance_statistics.delay()

        logger.info(f"Архивация данных завершена. Обработано пользователей: {users_count}")
        return f"Daily data archived for {yesterday}. Processed users: {users_count}"

    except Exception as e:
        logger.error(f"Общая ошибка при архивации данных: {str(e)}")
        raise


@shared_task
def run_daily_finance_statistics():
    """
    Генерирует финансовую статистику на текущий день
    для всех партнеров и магазинов
    """
    today = timezone.now().date()
    logger.info(f"Начало генерации финансовой статистики на {today}")

    try:
        # Статистика для партнеров
        users_count = 0
        for user in User.objects.filter(is_active=True, is_staff=False):
            try:
                generate_partner_finance_stat(user)
                users_count += 1
            except Exception as e:
                logger.error(f"Ошибка при генерации статистики для пользователя {user.id}: {str(e)}")

        # Статистика для магазинов
        stores_count = 0
        for store in Store.objects.filter(is_active=True, status='approved'):
            try:
                generate_store_finance_stat(store)
                stores_count += 1
            except Exception as e:
                logger.error(f"Ошибка при генерации статистики для магазина {store.id}: {str(e)}")

        logger.info(
            f"Генерация статистики завершена. Обработано пользователей: {users_count}, магазинов: {stores_count}")
        return f"Daily finance statistics generated. Users: {users_count}, Stores: {stores_count}"

    except Exception as e:
        logger.error(f"Общая ошибка при генерации финансовой статистики: {str(e)}")
        raise