from celery import shared_task
from django.core.mail import send_mail

@shared_task
def send_reset_email(email, reset_code):
    send_mail(
        "Код для сброса пароля",
        f"Ваш код для сброса пароля: {reset_code}",
         "Поддержка BAIEL <noreply@baiEl.com>",
        [email],
        fail_silently=False,
    )

