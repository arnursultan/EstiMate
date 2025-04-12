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
    Разрешение на редактирование только для владельца или администратора
    """

    def has_object_permission(self, request, view, obj):
        # Администратор имеет полный доступ
        if request.user.role == 'admin':
            return True

        # Проверяем, является ли пользователь владельцем объекта
        if hasattr(obj, 'partner'):
            return obj.partner == request.user
        return False