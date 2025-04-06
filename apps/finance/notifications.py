from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import FinanceEntry
from apps.notifications.services import notify


@receiver(post_save, sender=FinanceEntry)
def notify_manual_entry(sender, instance, created, **kwargs):
    """Отправка уведомлений при добавлении финансовой записи"""
    if created:
        # Уведомление пользователю
        notify(
            user=instance.user,
            title="Добавлена финансовая запись",
            message=f"Вы добавили запись: Доход {instance.income}, Расход {instance.expense}."
        )

        # Уведомление администраторам
        from django.contrib.auth import get_user_model
        User = get_user_model()
        admin_users = User.objects.filter(is_staff=True)

        for admin in admin_users:
            notify(
                user=admin,
                title="Новая финансовая запись",
                message=f"Пользователь {instance.user} добавил запись: Доход {instance.income}, Расход {instance.expense}."
            )