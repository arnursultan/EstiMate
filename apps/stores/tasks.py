from celery import shared_task
from django.utils import timezone
from django.core.cache import cache
from .services import StoreStatisticsService
from .models import Store


@shared_task
def calculate_stores_statistics():
    """
    Задача для расчета и кэширования статистики магазинов
    """
    today = timezone.now().date()
    service = StoreStatisticsService()

    # Рассчитываем общую статистику
    try:
        general_stats = service.get_store_statistics(date=today)
        if general_stats:
            cache.set(f"stores_stats_general_{today}", general_stats, 60 * 60 * 24)  # Кэш на сутки
    except Exception as e:
        print(f"Ошибка при расчете общей статистики: {str(e)}")

    # Рассчитываем статистику для каждого магазина
    for store in Store.objects.filter(status='approved'):
        try:
            store_stats = service.get_store_statistics(store_id=store.id, date=today)
            if store_stats:
                cache.set(f"store_stats_{store.id}_{today}", store_stats, 60 * 60 * 24)  # Кэш на сутки
        except Exception as e:
            print(f"Ошибка при расчете статистики для магазина {store.id}: {str(e)}")