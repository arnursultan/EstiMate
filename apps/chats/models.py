from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Message(models.Model):
    TEXT = 'text'
    IMAGE = 'image'
    VIDEO = 'video'
    FILE = 'file'

    TYPE_CHOICES = [
        (TEXT, 'Текст'),
        (IMAGE, 'Изображение'),
        (VIDEO, 'Видео'),
        (FILE, 'Файл'),
    ]

    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages', null=True,
                                 blank=True)

    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TEXT)
    text = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to='chat_files/', blank=True, null=True)
    is_read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.sender} → {self.receiver}: {self.text or self.file.name}"
