from django.db import models
from django.conf import settings


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

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,  # Используем AUTH_USER_MODEL вместо 'auth.User'
        on_delete=models.CASCADE,
        related_name='sent_messages'
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,  # Используем AUTH_USER_MODEL вместо 'auth.User'
        on_delete=models.CASCADE,
        related_name='received_messages',
        null=True,
        blank=True
    )

    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TEXT)
    text = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to='attachments/%Y/%m/%d/', blank=True, null=True)
    is_read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']
        verbose_name = "Сообщение"
        verbose_name_plural = "Сообщения"

    def __str__(self):
        receiver_info = f" для {self.receiver}" if self.receiver else ""
        return f"{self.sender}{receiver_info}: {self.text or self.file.name}"

    def mark_as_read(self):
        """Отметить сообщение как прочитанное"""
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])
            return True
        return False