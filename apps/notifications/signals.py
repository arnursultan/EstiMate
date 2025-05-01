# # apps/notifications/signals.py
# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from apps.orders.models import Order
# from apps.stores.models import Store
# from apps.users.models import User
# from apps.chats.models import Chat, Message
# from .services import NotificationService
# import logging
#
# logger = logging.getLogger(__name__)
#
#
# @receiver(post_save, sender=Order)
# def order_notification(sender, instance, created, **kwargs):
#     """Создает уведомление при изменении статуса заказа"""
#     if not created and instance.partner:
#         # Если статус заказа изменился
#         if instance.status in ['confirmed', 'rejected']:
#             notification_type = 'order_status'
#
#             if instance.status == 'confirmed':
#                 title = 'Заказ подтвержден'
#                 message = f'Ваш заказ #{instance.id} был подтвержден администратором.'
#             else:
#                 title = 'Заказ отклонен'
#                 message = f'Ваш заказ #{instance.id} был отклонен администратором.'
#
#             # Создаем уведомление для партнера
#             NotificationService.create_notification(
#                 user_id=instance.partner.id,
#                 notification_type=notification_type,
#                 title=title,
#                 message=message,
#                 extra_data={
#                     'order_id': instance.id,
#                     'order_type': instance.order_type,
#                     'status': instance.status
#                 }
#             )
#
#
# @receiver(post_save, sender=Store)
# def store_notification(sender, instance, created, **kwargs):
#     """Создает уведомление при изменении статуса магазина"""
#     if not created and instance.partner:
#         # Если статус магазина изменился
#         if instance.status in ['approved', 'rejected']:
#             notification_type = 'store_approval'
#
#             if instance.status == 'approved':
#                 title = 'Магазин одобрен'
#                 message = f'Ваш магазин "{instance.name}" был одобрен администратором.'
#             else:
#                 title = 'Магазин отклонен'
#                 message = f'Ваш магазин "{instance.name}" был отклонен администратором.'
#
#             # Создаем уведомление для партнера
#             NotificationService.create_notification(
#                 user_id=instance.partner.id,
#                 notification_type=notification_type,
#                 title=title,
#                 message=message,
#                 extra_data={
#                     'store_id': instance.id,
#                     'store_name': instance.name,
#                     'status': instance.status
#                 }
#             )
#
#
# @receiver(post_save, sender=User)
# def user_notification(sender, instance, created, **kwargs):
#     """Создает уведомление при регистрации или изменении статуса пользователя"""
#     if instance.role == 'partner':
#         # Для новых пользователей
#         if created:
#             # Уведомление для всех администраторов о новой регистрации
#             admins = User.objects.filter(role='admin', is_active=True)
#
#             for admin in admins:
#                 NotificationService.create_notification(
#                     user_id=admin.id,
#                     notification_type='registration',
#                     title='Новая регистрация',
#                     message=f'Новый партнер {instance.first_name} {instance.last_name} зарегистрировался в системе.',
#                     extra_data={
#                         'user_id': instance.id,
#                         'user_email': instance.email,
#                         'user_name': f'{instance.first_name} {instance.last_name}'
#                     }
#                 )
#
#         # Если статус пользователя изменился
#         elif instance.status in ['approved', 'rejected']:
#             notification_type = 'registration'
#
#             if instance.status == 'approved':
#                 title = 'Регистрация подтверждена'
#                 message = 'Ваша заявка на регистрацию была одобрена администратором.'
#
#                 # Создаем чаты с администраторами
#                 try:
#                     # Проверяем, есть ли уже чаты с этим партнером
#                     existing_chats = Chat.objects.filter(partner=instance).exists()
#
#                     # Если чатов нет, создаем чаты с каждым активным администратором
#                     if not existing_chats:
#                         # Получаем всех активных администраторов
#                         admins = User.objects.filter(role='admin', is_active=True)
#
#                         # Создаем чат с каждым администратором
#                         for admin in admins:
#                             Chat.objects.create(admin=admin, partner=instance)
#
#                             # Отправляем уведомление администратору о новом чате
#                             NotificationService.create_notification(
#                                 user_id=admin.id,
#                                 notification_type='message',
#                                 title='Новый чат с партнером',
#                                 message=f'Создан новый чат с партнером {instance.first_name} {instance.last_name}',
#                                 extra_data={
#                                     'partner_id': instance.id,
#                                     'partner_name': f'{instance.first_name} {instance.last_name}'
#                                 }
#                             )
#
#                         # Дополнительное уведомление для партнера о созданных чатах
#                         NotificationService.create_notification(
#                             user_id=instance.id,
#                             notification_type='system',
#                             title='Для вас созданы чаты',
#                             message='Для удобства общения с администраторами, для вас созданы чаты со всеми активными администраторами системы.'
#                         )
#
#                         logger.info(f"Созданы чаты для партнера {instance.id} со всеми администраторами")
#                 except Exception as e:
#                     logger.error(f"Ошибка при создании чатов для партнера {instance.id}: {str(e)}")
#             else:
#                 title = 'Регистрация отклонена'
#                 message = 'Ваша заявка на регистрацию была отклонена администратором.'
#
#             # Создаем уведомление для партнера
#             NotificationService.create_notification(
#                 user_id=instance.id,
#                 notification_type=notification_type,
#                 title=title,
#                 message=message,
#                 extra_data={
#                     'status': instance.status
#                 }
#             )
#
#
# @receiver(post_save, sender=Message)
# def message_notification(sender, instance, created, **kwargs):
#     """Создает уведомления при получении нового сообщения"""
#     if created:
#         try:
#             # Определяем получателя (не отправителя)
#             receiver = None
#             if instance.chat.admin == instance.sender:
#                 receiver = instance.chat.partner
#             else:
#                 receiver = instance.chat.admin
#
#             # Формируем предварительный текст сообщения
#             if instance.content:
#                 message_preview = instance.content[:50] + ('...' if len(instance.content) > 50 else '')
#             else:
#                 message_preview = f"Новый файл ({instance.message_type})"
#
#             # Создаем уведомление
#             NotificationService.create_notification(
#                 user_id=receiver.id,
#                 notification_type='message',
#                 title='Новое сообщение',
#                 message=f'У вас новое сообщение от {instance.sender.first_name} {instance.sender.last_name}',
#                 extra_data={
#                     'chat_id': instance.chat.id,
#                     'sender_id': instance.sender.id,
#                     'sender_name': f'{instance.sender.first_name} {instance.sender.last_name}',
#                     'message_preview': message_preview,
#                     'message_type': instance.message_type
#                 }
#             )
#         except Exception as e:
#             logger.error(f"Ошибка при создании уведомления о сообщении: {str(e)}")