from rest_framework import permissions


class AdminOrPartnerReadOnly(permissions.BasePermission):
    """
    • Администратор — полный read‑only доступ ко всем объектам.
    • Партнёр — видит только свои записи (`user == request.user`
      или `store.partner == request.user`), тоже read‑only.
    • Любые методы, кроме SAFE (GET/HEAD/OPTIONS), запрещены.
    """

    def has_permission(self, request, view):
        # Разрешаем только SAFE методы
        if request.method not in permissions.SAFE_METHODS:
            return False

        # Доступ есть у авторизованных админов и партнёров
        return request.user and request.user.is_authenticated and request.user.role in ("admin", "partner")

    def has_object_permission(self, request, view, obj):
        # Админ видит всё
        if request.user.role == "admin":
            return True

        # Партнёр — только свои записи
        return getattr(obj, "user_id", None) == request.user.id or getattr(obj, "store", None) and obj.store.partner_id == request.user.id
