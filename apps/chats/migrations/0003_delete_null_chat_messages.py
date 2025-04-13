
from django.db import migrations

def delete_null_chat_messages(apps, schema_editor):
    """Удаляет сообщения с NULL в поле chat"""
    Message = apps.get_model('chats', 'Message')
    deleted, details = Message.objects.filter(chat__isnull=True).delete()
    print(f"Удалено {deleted} сообщений с NULL в поле chat")

class Migration(migrations.Migration):

    dependencies = [
        ('chats', '0002_alter_message_chat'),
    ]

    operations = [
        migrations.RunPython(delete_null_chat_messages),
    ]