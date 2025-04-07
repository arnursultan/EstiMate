from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import FinanceEntry
from apps.notifications.services import notify


@receiver(post_save, sender=FinanceEntry)
def notify_manual_entry(sender, instance, created, **kwargs):
    """Отправка уведомлений при добавлении финансовой записи"""
    if created:
        entry_type_labels = {
            'expense': 'расход',
            'income': 'доход',
            'sale': 'продажа',
            'damage': 'брак',
            'return': 'возврат'
        }

        entry_type = entry_type_labels.get(instance.entry_type, instance.entry_type)

        # Уведомление пользователю
        if instance.entry_type in ['sale', 'damage', 'return'] and instance.partner_product:
            product_name = instance.partner_product.product.name
            notify(
                user=instance.user,
                title=f"Добавлена запись: {entry_type}",
                message=f"Вы добавили запись '{entry_type}' для товара '{product_name}' - {instance.quantity} шт. на сумму {instance.amount}."
            )
        else:
            notify(
                user=instance.user,
                title=f"Добавлена запись: {entry_type}",
                message=f"Вы добавили запись '{entry_type}' на сумму {instance.amount}."
            )

        # Уведомление администраторам
        from django.contrib.auth import get_user_model
        User = get_user_model()
        admin_users = User.objects.filter(is_staff=True)

        for admin in admin_users:
            if instance.entry_type in ['sale', 'damage', 'return'] and instance.partner_product:
                product_name = instance.partner_product.product.name
                notify(
                    user=admin,
                    title=f"Новая запись от партнера: {entry_type}",
                    message=f"Партнер {instance.user.email} добавил запись '{entry_type}' для товара '{product_name}' - {instance.quantity} шт. на сумму {instance.amount}."
                )
            else:
                notify(
                    user=admin,
                    title=f"Новая запись от партнера: {entry_type}",
                    message=f"Партнер {instance.user.email} добавил запись '{entry_type}' на сумму {instance.amount}."
                )