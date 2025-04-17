# apps/orders/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Order, DefectItem
from apps.notifications.services import NotificationService
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Order)
def order_notification(sender, instance, created, **kwargs):
    """Создает уведомления при создании или изменении заказа"""
    # ИСПРАВЛЕНО: Проверка наличия элементов заказа перед отправкой уведомления
    if instance.order_items.count() == 0:
        logger.warning(f"Заказ {instance.id} не содержит товаров, уведомление не будет отправлено")
        return

    # Новый заказ создан
    if created:
        # Если это заказ партнера к администратору
        if instance.order_type == 'admin_to_partner':
            # Уведомляем администраторов о новом заказе
            from apps.users.models import User
            admins = User.objects.filter(role='admin', is_active=True)
            for admin in admins:
                NotificationService.create_notification(
                    user_id=admin.id,
                    notification_type='order_status',
                    title='Новый заказ от партнера',
                    message=f'Партнер {instance.partner.first_name} {instance.partner.last_name} создал новый заказ № {instance.id}.',
                    extra_data={
                        'order_id': instance.id,
                        'order_type': instance.order_type,
                        'partner_id': instance.partner.id,
                        'partner_name': f'{instance.partner.first_name} {instance.partner.last_name}'
                    }
                )
    # Статус заказа изменен
    elif instance.tracker.has_changed('status'):
        # Если это заказ партнера к администратору и статус изменился
        if instance.order_type == 'admin_to_partner':
            # Уведомляем партнера об изменении статуса заказа
            if instance.status == 'confirmed':
                NotificationService.create_notification(
                    user_id=instance.partner.id,
                    notification_type='order_status',
                    title='Заказ подтвержден',
                    message=f'Ваш заказ № {instance.id} был подтвержден администратором.',
                    extra_data={
                        'order_id': instance.id,
                        'order_type': instance.order_type,
                        'status': instance.status
                    }
                )
            elif instance.status == 'rejected':
                NotificationService.create_notification(
                    user_id=instance.partner.id,
                    notification_type='order_status',
                    title='Заказ отклонен',
                    message=f'Ваш заказ № {instance.id} был отклонен администратором.',
                    extra_data={
                        'order_id': instance.id,
                        'order_type': instance.order_type,
                        'status': instance.status
                    }
                )


@receiver(post_save, sender=DefectItem)
def defect_notification(sender, instance, created, **kwargs):
    """Создает уведомления при регистрации бракованного товара"""
    if created:
        try:
            # Проверяем, что заказ существует и содержит элементы
            if not instance.order or instance.order.order_items.count() == 0:
                logger.warning(
                    f"Заказ {instance.order.id if instance.order else 'None'} не содержит товаров или не существует, уведомление о браке не будет отправлено")
                return

            # Если заказ принадлежит магазину
            if instance.order.store:
                # Уведомляем партнера о бракованном товаре
                NotificationService.create_notification(
                    user_id=instance.order.created_by.id,
                    notification_type='order_status',
                    title='Зарегистрирован брак',
                    message=f'В заказе № {instance.order.id} для магазина "{instance.order.store.name}" зарегистрирован брак: {instance.quantity} шт. "{instance.product.name}".',
                    extra_data={
                        'order_id': instance.order.id,
                        'store_id': instance.order.store.id,
                        'store_name': instance.order.store.name,
                        'product_id': instance.product.id,
                        'product_name': instance.product.name,
                        'quantity': instance.quantity
                    }
                )
        except Exception as e:
            logger.error(f"Ошибка при создании уведомления о бракованном товаре: {str(e)}")