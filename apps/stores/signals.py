# apps/stores/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Store, StoreDebt, StoreDebtPayment
from apps.users.models import User
from apps.notifications.services import NotificationService


@receiver(post_save, sender=Store)
def store_status_notification(sender, instance, created, **kwargs):
    """Создает уведомления при создании магазина"""
    # Новый магазин создан
    if created:
        # Уведомляем партнера о создании магазина
        NotificationService.create_notification(
            user_id=instance.partner.id,
            notification_type='store_approval',
            title='Магазин создан',
            message=f'Ваш магазин "{instance.name}" был успешно создан.',
            extra_data={
                'store_id': instance.id,
                'store_name': instance.name,
                'status': instance.status
            }
        )

        # Уведомляем администраторов о создании нового магазина
        admins = User.objects.filter(role='admin', is_active=True)
        for admin in admins:
            NotificationService.create_notification(
                user_id=admin.id,
                notification_type='store_approval',
                title='Создан новый магазин',
                message=f'Партнер {instance.partner.first_name} {instance.partner.last_name} создал новый магазин "{instance.name}".',
                extra_data={
                    'store_id': instance.id,
                    'store_name': instance.name,
                    'partner_id': instance.partner.id,
                    'partner_name': f'{instance.partner.first_name} {instance.partner.last_name}'
                }
            )


@receiver(post_save, sender=StoreDebt)
def store_debt_notification(sender, instance, created, **kwargs):
    """Создает уведомления при создании нового долга магазина"""
    if created:
        # Уведомляем партнера о новом долге магазина
        NotificationService.create_notification(
            user_id=instance.store.partner.id,
            notification_type='financial',
            title='Новый долг магазина',
            message=f'Для магазина "{instance.store.name}" был зарегистрирован новый долг на сумму {instance.amount} сом.',
            extra_data={
                'store_id': instance.store.id,
                'store_name': instance.store.name,
                'debt_id': instance.id,
                'amount': float(instance.amount)
            }
        )


@receiver(post_save, sender=StoreDebtPayment)
def store_payment_notification(sender, instance, created, **kwargs):
    """Создает уведомления при регистрации платежа магазина"""
    if created:
        # Уведомляем партнера о новом платеже магазина
        NotificationService.create_notification(
            user_id=instance.store.partner.id,
            notification_type='financial',
            title='Новый платеж от магазина',
            message=f'От магазина "{instance.store.name}" получен платеж на сумму {instance.amount} сом.',
            extra_data={
                'store_id': instance.store.id,
                'store_name': instance.store.name,
                'payment_id': instance.id,
                'amount': float(instance.amount)
            }
        )