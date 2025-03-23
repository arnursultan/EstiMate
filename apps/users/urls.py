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
    UserBlockAPIView,
    UserUnblockAPIView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("profile/", PartnerProfileAPIView.as_view(), name="profile"),
    path("profile/delete/<int:pk>/", UserDeleteAPIView.as_view(), name="delete"),
    path("admin/", AdminUserAPIView.as_view(), name="admin"),
    path("admin/<int:pk>/", AdminUserDetailAPIView.as_view(), name="admin_detail"),
    path("admin/block/<int:pk>/", UserBlockAPIView.as_view(), name="block"),
    path("admin/unblock/<int:pk>/", UserUnblockAPIView.as_view(), name="unblock"),
    path("password-reset/", PasswordResetView.as_view(), name="password_reset"),
    path("password-reset/verify/", PasswordResetVerifyView.as_view(), name="password_reset_verify"),
    path("password-reset/confirm/", PasswordResetConfirmView.as_view(), name="password_reset_confirm"),

    path("token/refresh/", CustomTokenRefreshView.as_view(), name="token_refresh"),
]
