from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import Store
from apps.notifications.services import notify


@receiver(pre_save, sender=Store)
def store_status_notify(sender, instance, **kwargs):
    if not instance.pk:
        return  # Магазин ещё не создан

    try:
        previous = Store.objects.get(pk=instance.pk)
        if previous.status != instance.status:
            if instance.status == 'approved':
                # Отправляем уведомление администраторам
                from django.contrib.auth import get_user_model
                User = get_user_model()
                admin_users = User.objects.filter(is_staff=True)

                for admin in admin_users:
                    notify(
                        user=admin,
                        title="Магазин одобрен",
                        message=f"Магазин '{instance.name}' был одобрен и активирован."
                    )
            elif instance.status == 'rejected':
                # Отправляем уведомление администраторам
                from django.contrib.auth import get_user_model
                User = get_user_model()
                admin_users = User.objects.filter(is_staff=True)

                for admin in admin_users:
                    notify(
                        user=admin,
                        title="Магазин отклонён",
                        message=f"Магазин '{instance.name}' был отклонён администратором."
                    )
    except Store.DoesNotExist:
        pass  # Магазин новый, уведомления не нужны