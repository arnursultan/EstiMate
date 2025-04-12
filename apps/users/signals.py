# apps/users/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User
from apps.notifications.services import NotificationService


@receiver(post_save, sender=User)
def user_status_notification(sender, instance, created, **kwargs):
    """Создает уведомления при изменении статуса пользователя"""
    # Если это не новый пользователь и статус изменился
    if not created and instance.role == 'partner':
        # Сообщение для партнера об изменении статуса
        if instance.status == 'approved':
            NotificationService.create_notification(
                user_id=instance.id,
                notification_type='registration',
                title='Ваша учетная запись одобрена',
                message='Администратор одобрил вашу учетную запись. Теперь вы можете полноценно использовать систему.',
                extra_data={
                    'status': instance.status
                }
            )
        elif instance.status == 'rejected':
            NotificationService.create_notification(
                user_id=instance.id,
                notification_type='registration',
                title='Ваша учетная запись отклонена',
                message='К сожалению, администратор отклонил вашу регистрацию.',
                extra_data={
                    'status': instance.status
                }
            )

        # Уведомление для администраторов о новой регистрации
        if created:
            admins = User.objects.filter(role='admin', is_active=True)
            for admin in admins:
                NotificationService.create_notification(
                    user_id=admin.id,
                    notification_type='registration',
                    title='Новый пользователь зарегистрирован',
                    message=f'Новый партнер {instance.first_name} {instance.last_name} ({instance.email}) зарегистрировался и ожидает подтверждения.',
                    extra_data={
                        'user_id': instance.id,
                        'user_name': f'{instance.first_name} {instance.last_name}',
                        'user_email': instance.email
                    }
                )