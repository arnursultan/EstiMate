from celery import shared_task
from django.utils import timezone
from django.db.models import Sum
from apps.users.models import User
from apps.stores.models import Store
from apps.orders.models import ProductRequest
from apps.finance.models import ArchivedDailySummary, FinanceEntry
from apps.products.models import PartnerProduct
from .services import generate_partner_finance_stat, generate_store_finance_stat, generate_inventory_summary
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

                # Получаем ручные записи за вчерашний день
                entries = FinanceEntry.objects.filter(
                    user=user,
                    date=yesterday
                )

                # Рассчитываем суммы
                total_sales = entries.filter(entry_type='sale').aggregate(total=Sum('amount'))['total'] or 0
                total_expenses = entries.filter(entry_type='expense').aggregate(total=Sum('amount'))['total'] or 0
                total_damages = entries.filter(entry_type='damage').aggregate(total=Sum('amount'))['total'] or 0
                total_returns = entries.filter(entry_type='return').aggregate(total=Sum('amount'))['total'] or 0

                # Общая прибыль от запросов STORE
                store_profit = sum([
                    max((r.quantity - r.damaged_quantity) * r.partner_product.price, 0)
                    for r in requests.filter(request_type='STORE', status='received') if r.partner_product
                ])

                # Расчет стоимости бонусов
                total_bonus = sum([
                    max(r.bonus_quantity * r.partner_product.price, 0)
                    for r in requests.filter(request_type='STORE', status='received') if r.partner_product
                ])

                # Расчет итоговой прибыли
                total_profit = store_profit + total_sales - total_expenses - total_damages + total_returns

                # Сохраняем архивную запись
                ArchivedDailySummary.objects.update_or_create(
                    user=user,
                    date=yesterday,
                    defaults={
                        'total_requests': requests.count(),
                        'total_sales': total_sales,
                        'total_expenses': total_expenses,
                        'total_profit': total_profit,
                        'total_damages': total_damages,
                        'total_returns': total_returns,
                        'total_bonus': total_bonus,
                        'data': {
                            'requests_details': [
                                {
                                    'id': r.id,
                                    'product_name': r.product.name,
                                    'quantity': r.quantity,
                                    'bonus_quantity': r.bonus_quantity,
                                    'damaged_quantity': r.damaged_quantity,
                                    'total_price': float(r.total_price),
                                    'status': r.status,
                                    'type': r.request_type,
                                    'store': r.store.name if r.store else None
                                } for r in requests
                            ],
                            'entries_details': [
                                {
                                    'id': e.id,
                                    'type': e.entry_type,
                                    'amount': float(e.amount),
                                    'quantity': e.quantity,
                                    'product': e.partner_product.product.name if e.partner_product else None,
                                    'note': e.note
                                } for e in entries
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
                generate_inventory_summary(user)  # Статистика по остаткам товаров
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


@shared_task
def cleanup_orphaned_entries():
    """
    Удаляет финансовые записи, связанные с удаленными товарами партнера
    """
    entries = FinanceEntry.objects.filter(
        partner_product__isnull=False,
        entry_type__in=['sale', 'damage', 'return']
    )

    orphaned_count = 0
    for entry in entries:
        try:
            # Проверка существования товара партнера
            PartnerProduct.objects.get(pk=entry.partner_product_id)
        except PartnerProduct.DoesNotExist:
            # Если товара нет, помечаем запись как сиротскую
            entry.note = f"ORPHANED: {entry.note or ''}"
            entry.partner_product = None
            entry.save()
            orphaned_count += 1

    return f"Cleaned up {orphaned_count} orphaned finance entries"


@shared_task
def sync_inventory_stats():
    """
    Синхронизирует статистику остатков товаров для всех партнеров
    """
    users_count = 0
    for user in User.objects.filter(is_active=True, is_staff=False):
        try:
            # Проверяем, есть ли товары в каталоге партнера
            if PartnerProduct.objects.filter(partner=user).exists():
                generate_inventory_summary(user)
                users_count += 1
        except Exception as e:
            logger.error(f"Ошибка при синхронизации статистики остатков для пользователя {user.id}: {str(e)}")

    return f"Synced inventory stats for {users_count} users"