from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import FinanceEntry
from apps.notifications.services import notify


@receiver(post_save, sender=FinanceEntry)
def notify_manual_entry(sender, instance, created, **kwargs):
    if created:
        notify(
            user=instance.user,
            title="Добавлена финансовая запись",
            message=f"Вы добавили запись: Доход {instance.income}, Расход {instance.expense}."
        )
