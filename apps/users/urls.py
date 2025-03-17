from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterView,
    LoginView,
    LogoutView,
    ProfileView,
    PasswordResetView,
    PasswordResetConfirmView,
    # PasswordResetPhoneView,
    # PasswordResetPhoneConfirmView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("password-reset/", PasswordResetView.as_view(), name="password_reset"),
    path("password-reset/confirm/", PasswordResetConfirmView.as_view(), name="password_reset_confirm"),

    # path("password-reset/phone/", PasswordResetPhoneView.as_view(), name="password_reset_phone"),
    # path("password-reset/phone/confirm/", PasswordResetPhoneConfirmView.as_view(), name="password_reset_phone_confirm"),

    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]
