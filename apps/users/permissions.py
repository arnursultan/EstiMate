from rest_framework import permissions

class IsAdminUser(permissions.BasePermission):
    """
    Разрешение доступа только для администраторов
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'admin'

class IsPartnerUser(permissions.BasePermission):
    """
    Разрешение доступа только для партнеров
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'partner'

class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Разрешение на редактирование объекта только для его владельца (поле partner) или администратора.
    """
    def has_object_permission(self, request, view, obj):
        # Администратор имеет полный доступ
        if request.user and request.user.is_authenticated and request.user.role == 'admin':
            return True

        # Проверяем, является ли пользователь владельцем объекта (если у объекта есть поле partner)
        if hasattr(obj, 'partner'):
            return obj.partner == request.user
        # Добавим проверку для объектов, где владелец - сам пользователь (например, его собственный профиль)
        if isinstance(obj, request.user.__class__):
             return obj == request.user
        # Добавим проверку для объектов, где владелец указан в поле user
        if hasattr(obj, 'user'):
             return obj.user == request.user
        # Добавим проверку для заказов (создатель или получатель-партнер)
        if hasattr(obj, 'created_by') and hasattr(obj, 'partner'):
             return obj.created_by == request.user or obj.partner == request.user

        return False

class IsInventoryOwnerOrAdmin(permissions.BasePermission):
    """
    Разрешение на редактирование записи инвентаря только для его владельца или администратора.
    """
    def has_object_permission(self, request, view, obj):
        # Администратор имеет полный доступ
        if request.user and request.user.is_authenticated and request.user.role == 'admin':
            return True
        # Проверяем, является ли пользователь владельцем записи инвентаря
        # (поле partner в модели PartnerInventory)
        return obj.partner == request.user