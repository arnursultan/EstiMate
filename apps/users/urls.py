# apps/users/urls.py
from django.urls import path
from .views import (
    RegisterView,
    LoginView,
    LogoutView,
    PasswordResetView,
    PasswordResetVerifyView,
    PasswordResetConfirmView,
    CustomTokenRefreshView,
    PartnerProfileAPIView,
    AdminUserAPIView,
    AdminUserDetailAPIView,
    UserDeleteAPIView,
    UserRestoreAPIView, # ДОБАВЛЕН
    UserBlockAPIView,
    UserUnblockAPIView,
    RejectUserAPIView,
    ApproveUserAPIView,
    DeactivateOwnAccountAPIView,
    UserActivateAPIView,
    # PartnerDailySummaryView, - УДАЛЕН
    # AdminDashboardView, - УДАЛЕН
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),

    path("profile/", PartnerProfileAPIView.as_view(), name="profile"),
    path("profile/deactivate/", DeactivateOwnAccountAPIView.as_view(), name="deactivate"),
    path("admin/users/<int:pk>/activate/", UserActivateAPIView.as_view(), name="admin-user-activate"),# Для пользователя

    path("admin/users/", AdminUserAPIView.as_view(), name="admin-user-list"), # Изменено имя для ясности
    path("admin/users/<int:pk>/", AdminUserDetailAPIView.as_view(), name="admin-user-detail"),
    path("admin/users/<int:pk>/delete/", UserDeleteAPIView.as_view(), name="admin-user-delete"), # Метод DELETE
    path("admin/users/<int:pk>/restore/", UserRestoreAPIView.as_view(), name="admin-user-restore"), # Метод POST
    path("admin/users/<int:pk>/block/", UserBlockAPIView.as_view(), name="admin-user-block"), # Метод POST
    path("admin/users/<int:pk>/unblock/", UserUnblockAPIView.as_view(), name="admin-user-unblock"), # Метод POST
    path("admin/users/<int:pk>/approve/", ApproveUserAPIView.as_view(), name="admin-user-approve"), # Метод POST
    path("admin/users/<int:pk>/reject/", RejectUserAPIView.as_view(), name="admin-user-reject"), # Метод POST

    path("password-reset/", PasswordResetView.as_view(), name="password_reset"),
    path("password-reset/verify/", PasswordResetVerifyView.as_view(), name="password_reset_verify"),
    path("password-reset/confirm/", PasswordResetConfirmView.as_view(), name="password_reset_confirm"),

    path("token/refresh/", CustomTokenRefreshView.as_view(), name="token_refresh"),

    # path('daily-summary/', PartnerDailySummaryView.as_view(), name='daily-summary'), - УДАЛЕН
    # path('admin/dashboard/', AdminDashboardView.as_view(), name='admin-dashboard'), - УДАЛЕН
]