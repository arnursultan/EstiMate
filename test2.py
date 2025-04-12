import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

sender_email = "azatss442@gmail.com"
password = "asooownxasynzuci"  # Пароль приложения
receiver_email = "murzaevazat2@gmail.com"  # Замените на реальный email для теста

message = MIMEMultipart()
message["From"] = sender_email
message["To"] = receiver_email
message["Subject"] = "Test email from Python"
body = "This is a test email sent from Python!"
message.attach(MIMEText(body, "plain"))

try:
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(sender_email, password)
        text = message.as_string()
        server.sendmail(sender_email, receiver_email, text)
    print("Email sent successfully!")
except Exception as e:
    print(f"Error: {e}")
