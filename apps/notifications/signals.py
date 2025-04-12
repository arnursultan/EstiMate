# apps/notifications/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.orders.models import Order
from apps.stores.models import Store
from apps.users.models import User
from .services import NotificationService


@receiver(post_save, sender=Order)
def order_notification(sender, instance, created, **kwargs):
    """Создает уведомление при изменении статуса заказа"""
    if not created and instance.partner:
        # Если статус заказа изменился
        if instance.status in ['confirmed', 'rejected']:
            notification_type = 'order_status'

            if instance.status == 'confirmed':
                title = 'Заказ подтвержден'
                message = f'Ваш заказ #{instance.id} был подтвержден администратором.'
            else:
                title = 'Заказ отклонен'
                message = f'Ваш заказ #{instance.id} был отклонен администратором.'

            # Создаем уведомление для партнера
            NotificationService.create_notification(
                user_id=instance.partner.id,
                notification_type=notification_type,
                title=title,
                message=message,
                extra_data={
                    'order_id': instance.id,
                    'order_type': instance.order_type,
                    'status': instance.status
                }
            )


@receiver(post_save, sender=Store)
def store_notification(sender, instance, created, **kwargs):
    """Создает уведомление при изменении статуса магазина"""
    if not created and instance.partner:
        # Если статус магазина изменился
        if instance.status in ['approved', 'rejected']:
            notification_type = 'store_approval'

            if instance.status == 'approved':
                title = 'Магазин одобрен'
                message = f'Ваш магазин "{instance.name}" был одобрен администратором.'
            else:
                title = 'Магазин отклонен'
                message = f'Ваш магазин "{instance.name}" был отклонен администратором.'

            # Создаем уведомление для партнера
            NotificationService.create_notification(
                user_id=instance.partner.id,
                notification_type=notification_type,
                title=title,
                message=message,
                extra_data={
                    'store_id': instance.id,
                    'store_name': instance.name,
                    'status': instance.status
                }
            )


@receiver(post_save, sender=User)
def user_notification(sender, instance, created, **kwargs):
    """Создает уведомление при регистрации или изменении статуса пользователя"""
    if instance.role == 'partner':
        # Для новых пользователей
        if created:
            # Уведомление для всех администраторов о новой регистрации
            admins = User.objects.filter(role='admin', is_active=True)

            for admin in admins:
                NotificationService.create_notification(
                    user_id=admin.id,
                    notification_type='registration',
                    title='Новая регистрация',
                    message=f'Новый партнер {instance.first_name} {instance.last_name} зарегистрировался в системе.',
                    extra_data={
                        'user_id': instance.id,
                        'user_email': instance.email,
                        'user_name': f'{instance.first_name} {instance.last_name}'
                    }
                )

        # Если статус пользователя изменился
        elif instance.status in ['approved', 'rejected']:
            notification_type = 'registration'

            if instance.status == 'approved':
                title = 'Регистрация подтверждена'
                message = 'Ваша заявка на регистрацию была одобрена администратором.'
            else:
                title = 'Регистрация отклонена'
                message = 'Ваша заявка на регистрацию была отклонена администратором.'

            # Создаем уведомление для партнера
            NotificationService.create_notification(
                user_id=instance.id,
                notification_type=notification_type,
                title=title,
                message=message,
                extra_data={
                    'status': instance.status
                }
            )