import os
from celery import Celery
import logging

from celery.schedules import crontab

logger = logging.getLogger(__name__)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

app = Celery("backend")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    """Задача для проверки работы Celery"""
    logger.info(f"Celery работает: {self.request!r}")

# В файле backend/celery_app.py добавить

app.conf.beat_schedule.update({
    'daily-finance-statistics': {
        'task': 'apps.finance.tasks.run_daily_finance_statistics',
        'schedule': crontab(hour=0, minute=30),  # Каждый день в 00:30
    },
    'archive-daily-data': {
        'task': 'apps.finance.tasks.archive_daily_data',
        'schedule': crontab(hour=23, minute=45),  # Каждый день в 23:45
    },
})