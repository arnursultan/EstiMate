from .models import Notification
import logging

logger = logging.getLogger(__name__)


def notify(user, title, message, notification_type=None, context_data=None):
    """
    Создает новое уведомление для пользователя

    :param user: Пользователь-получатель уведомления
    :param title: Заголовок уведомления
    :param message: Текст уведомления
    :param notification_type: Тип уведомления для категоризации
    :param context_data: Дополнительный контекст в формате JSON
    :return: Созданное уведомление или список уведомлений, или None в случае ошибки
    """
    try:
        # Если пользователь не указан, уведомление для всех администраторов
        if user is None:
            # Отправить всем администраторам
            from django.contrib.auth import get_user_model
            User = get_user_model()
            admin_users = User.objects.filter(is_staff=True)

            notifications = []
            for admin in admin_users:
                notification = Notification.objects.create(
                    recipient=admin,
                    title=title,
                    message=message,
                    notification_type=notification_type,
                    context_data=context_data or {}
                )
                notifications.append(notification)

            return notifications
        else:
            notification = Notification.objects.create(
                recipient=user,
                title=title,
                message=message,
                notification_type=notification_type,
                context_data=context_data or {}
            )
            return notification
    except Exception as e:
        logger.error(f"Ошибка при создании уведомления: {str(e)}")
        return None


def notify_partner_product_update(partner, partner_product, action_type):
    """
    Отправляет уведомление о изменениях в товаре партнера

    :param partner: Пользователь-партнер
    :param partner_product: Экземпляр PartnerProduct
    :param action_type: Тип действия ('sold', 'damaged', 'returned')
    """
    action_labels = {
        'sold': 'продажа',
        'damaged': 'брак',
        'returned': 'возврат'
    }

    title = f"Обновление товара в каталоге"
    message = f"Товар '{partner_product.product.name}' был изменен - {action_labels.get(action_type, action_type)}"

    context_data = {
        'partner_product_id': partner_product.id,
        'product_name': partner_product.product.name,
        'action': action_type,
        'quantity': partner_product.quantity,
        'remaining': partner_product.remaining_quantity
    }

    notify(
        user=partner,
        title=title,
        message=message,
        notification_type=f"partner_product_{action_type}",
        context_data=context_data
    )


def notify_finance_entry_created(user, entry):
    """
    Отправляет уведомление о создании финансовой записи

    :param user: Пользователь
    :param entry: Экземпляр FinanceEntry
    """
    entry_type_labels = {
        'expense': 'расход',
        'income': 'доход',
        'sale': 'продажа',
        'damage': 'брак',
        'return': 'возврат'
    }

    entry_type = entry_type_labels.get(entry.entry_type, entry.entry_type)

    # Сообщение в зависимости от типа записи
    if entry.entry_type in ['sale', 'damage', 'return']:
        product_name = entry.partner_product.product.name if entry.partner_product else "неизвестный товар"
        quantity = entry.quantity
        amount = entry.amount

        title = f"Новая финансовая запись: {entry_type}"
        message = f"Создана запись '{entry_type}' для товара '{product_name}' - {quantity} шт. на сумму {amount}"
    else:
        title = f"Новая финансовая запись: {entry_type}"
        message = f"Создана запись '{entry_type}' на сумму {entry.amount}"

    # Отправляем уведомление пользователю
    notify(
        user=user,
        title=title,
        message=message,
        notification_type=f"finance_{entry.entry_type}",
        context_data={
            'entry_id': entry.id,
            'entry_type': entry.entry_type,
            'amount': float(entry.amount),
            'quantity': entry.quantity,
            'partner_product_id': entry.partner_product.id if entry.partner_product else None,
            'product_name': entry.partner_product.product.name if entry.partner_product else None
        }
    )

    # Для админов также отправляем уведомление
    if not user.is_staff:
        # Отправляем уведомление администраторам
        from django.contrib.auth import get_user_model
        User = get_user_model()
        admin_users = User.objects.filter(is_staff=True)

        for admin in admin_users:
            notify(
                user=admin,
                title=f"Новая запись от партнера: {entry_type}",
                message=f"Партнер {user.email} создал запись '{entry_type}'" +
                        (f" для товара '{product_name}'" if entry.partner_product else "") +
                        f" на сумму {entry.amount}",
                notification_type=f"admin_finance_{entry.entry_type}",
                context_data={
                    'entry_id': entry.id,
                    'entry_type': entry.entry_type,
                    'amount': float(entry.amount),
                    'partner_id': user.id,
                    'partner_email': user.email
                }
            )


def notify_request_status_change(request):
    """
    Отправляет уведомление об изменении статуса запроса

    :param request: Экземпляр ProductRequest
    """
    # Получаем информацию о запросе
    request_type_display = "для себя" if request.request_type == 'SELF' else f"для магазина {request.store.name if request.store else ''}"
    status_display = dict(request.STATUS_CHOICES)[request.status]

    # Определяем получателя и текст в зависимости от статуса
    if request.status == 'approved':
        title = f"Запрос одобрен"
        message = f"Ваш запрос на товар '{request.product.name}' ({request_type_display}) был одобрен"

        # Дополнительное уведомление для запросов SELF
        if request.request_type == 'SELF':
            # Отправляем второе уведомление о добавлении в каталог
            notify(
                user=request.user,
                title="Товар добавлен в ваш каталог",
                message=f"Товар '{request.product.name}' ({request.quantity} шт.) добавлен в ваш личный каталог",
                notification_type="catalog_product_added",
                context_data={
                    'product_id': request.product.id,
                    'product_name': request.product.name,
                    'quantity': request.quantity
                }
            )
    elif request.status == 'rejected':
        title = f"Запрос отклонен"
        message = f"Ваш запрос на товар '{request.product.name}' ({request_type_display}) был отклонен"
    elif request.status == 'received':
        title = f"Запрос отмечен как полученный"
        message = f"Ваш запрос на товар '{request.product.name}' ({request_type_display}) отмечен как полученный"
    else:
        return  # Для других статусов не отправляем уведомления

    # Отправляем уведомление пользователю
    notify(
        user=request.user,
        title=title,
        message=message,
        notification_type=f"request_{request.status}",
        context_data={
            'request_id': request.id,
            'product_id': request.product.id,
            'product_name': request.product.name,
            'request_type': request.request_type,
            'status': request.status
        }
    )

    # Если статус changed to 'received', также отправляем уведомление админам
    if request.status == 'received':
        # Отправляем уведомление администраторам
        from django.contrib.auth import get_user_model
        User = get_user_model()
        admin_users = User.objects.filter(is_staff=True)

        for admin in admin_users:
            notify(
                user=admin,
                title="Запрос отмечен как полученный",
                message=f"Пользователь {request.user.email} отметил запрос на товар '{request.product.name}' как полученный",
                notification_type="admin_request_received",
                context_data={
                    'request_id': request.id,
                    'product_id': request.product.id,
                    'product_name': request.product.name,
                    'user_id': request.user.id,
                    'user_email': request.user.email
                }
            )