import pytest
from unittest.mock import patch
from rest_framework.exceptions import ValidationError
from apps.users import validators
from apps.users.tasks import send_reset_email


# ==== Тесты на email ====

def test_validate_email_with_double_dot():
    with pytest.raises(ValidationError, match="Некорректный формат email."):
        validators.validate_email("invalid..email@gmail.com")


def test_validate_email_with_invalid_domain():
    with pytest.raises(ValidationError, match="Регистрация разрешена только для доменов"):
        validators.validate_email("user@unknown-domain.com")


# ==== Тесты на пароль ====

def test_validate_password_too_short():
    with pytest.raises(ValidationError, match="Пароль должен быть не менее 8 символов."):
        validators.validate_password("123")


def test_validate_password_no_digit():
    with pytest.raises(ValidationError, match="Пароль должен содержать буквы и цифры."):
        validators.validate_password("password")


def test_validate_password_no_letter():
    with pytest.raises(ValidationError, match="Пароль должен содержать буквы и цифры."):
        validators.validate_password("12345678")


# ==== Тест Celery-задачи ====

@patch("apps.users.tasks.send_mail")
def test_send_reset_email_task(mock_send_mail):
    send_reset_email("test@mail.com", "12345")
    mock_send_mail.assert_called_once_with(
        "Код для сброса пароля",                      # subject
        "Ваш код для сброса пароля: 12345",           # message
        "Поддержка BAIEL <noreply@baiEl.com>",        # from_email
        ["test@mail.com"],                            # recipient_list
        fail_silently=False                           # keyword arg
    )