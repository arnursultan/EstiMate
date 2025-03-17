from celery import shared_task
from django.core.mail import send_mail
# from twilio.rest import Client
# import os

@shared_task
def send_reset_email(email, reset_code):
    send_mail(
        "Код для сброса пароля",
        f"Ваш код для сброса пароля: {reset_code}",
         "Поддержка BAIEL <noreply@baiEl.com>",
        [email],
        fail_silently=False,
    )

# @shared_task
# def send_sms(to, message):
#     account_sid = os.getenv("TWILIO_ACCOUNT_SID")
#     auth_token = os.getenv("TWILIO_AUTH_TOKEN")
#     client = Client(account_sid, auth_token)
#     client.messages.create(
#         body=message,
#         from_=os.getenv("TWILIO_PHONE_NUMBER"),
#         to=to
#     )
