from celery import shared_task
from apps.users.models import User
from apps.stores.models import Store
from .services import generate_partner_finance_stat, generate_store_finance_stat


@shared_task
def run_daily_finance_statistics():
    for user in User.objects.filter(is_active=True, is_staff=False):
        generate_partner_finance_stat(user)

    for store in Store.objects.filter(is_active=True):
        generate_store_finance_stat(store)
