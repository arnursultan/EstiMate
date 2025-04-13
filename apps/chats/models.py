from django.db import models
from django.conf import settings
import os
import uuid


def chat_file_upload_path(instance, filename):
    """Генерирует уникальный путь для сохранения файлов чата."""
    ext = filename.split('.')[-1]
    new_filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('chat_files', new_filename)


class Chat(models.Model):
    """Модель чата между администратором и партнером."""
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='admin_chats',
        limit_choices_to={'role': 'admin'}
    )
    partner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='partner_chats',
        limit_choices_to={'role': 'partner'}
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('admin', 'partner')
        verbose_name = "Чат"
        verbose_name_plural = "Чаты"
        indexes = [
            models.Index(fields=['admin']),
            models.Index(fields=['partner']),
            models.Index(fields=['updated_at']),
        ]

    def __str__(self):
        return f"Чат между {self.admin.email} и {self.partner.email}"


class Message(models.Model):
    """Модель сообщения в чате."""
    MESSAGE_TYPE_CHOICES = [
        ('text', 'Текст'),
        ('image', 'Изображение'),
        ('video', 'Видео'),
        ('document', 'Документ'),
    ]

    chat = models.ForeignKey(
        Chat,
        related_name='messages',
        on_delete=models.CASCADE,
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages'
    )
    content = models.TextField(blank=True, null=True)
    file = models.FileField(
        upload_to=chat_file_upload_path,
        blank=True,
        null=True
    )
    message_type = models.CharField(
        max_length=10,
        choices=MESSAGE_TYPE_CHOICES,
        default='text'
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['timestamp']
        verbose_name = "Сообщение"
        verbose_name_plural = "Сообщения"
        indexes = [
            models.Index(fields=['chat', 'timestamp']),
            models.Index(fields=['sender', 'is_read']),
        ]

    def __str__(self):
        return f"Сообщение от {self.sender.email} в {self.timestamp}"

    @property
    def file_type(self):
        """Определение типа файла на основе расширения."""
        if not self.file:
            return None

        filename = self.file.name.lower()
        if filename.endswith(('.jpg', '.jpeg', '.png', '.gif')):
            return 'image'
        elif filename.endswith(('.mp4', '.avi', '.mov', '.wmv')):
            return 'video'
        elif filename.endswith(('.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx')):
            return 'document'
        else:
            return 'other'