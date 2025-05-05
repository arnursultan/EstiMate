# apps/chats/management/commands/create_missing_chats.py
from django.core.management.base import BaseCommand
from apps.users.models import User
from apps.chats.models import Chat


class Command(BaseCommand):
    help = 'Создает чаты для существующих одобренных партнеров'

    def handle(self, *args, **options):
        # Получаем всех админов
        admins = User.objects.filter(role='admin', is_active=True, is_deleted=False)
        admin_count = admins.count()

        # Получаем всех одобренных партнеров
        partners = User.objects.filter(role='partner', status='approved', is_active=True, is_deleted=False)
        partner_count = partners.count()

        self.stdout.write(f'\nНачинаем проверку...')
        self.stdout.write(f'Админов: {admin_count}')
        self.stdout.write(f'Одобренных партнеров: {partner_count}')
        self.stdout.write('-' * 50)

        created = 0
        already_exists = 0

        for partner in partners:
            for admin in admins:
                chat, was_created = Chat.objects.get_or_create(admin=admin, partner=partner)
                if was_created:
                    created += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Создан чат #{chat.id} между {admin.email} и {partner.email}')
                    )
                else:
                    already_exists += 1

        self.stdout.write('-' * 50)
        self.stdout.write(self.style.SUCCESS(f'Создано новых чатов: {created}'))
        self.stdout.write(f'Уже существовало: {already_exists}')

        # Проверка на корректность
        expected_total = admin_count * partner_count
        actual_total = Chat.objects.count()
        self.stdout.write('-' * 50)
        self.stdout.write(f'Ожидалось всего чатов: {expected_total}')
        self.stdout.write(f'Реально чатов в базе: {actual_total}')

        if expected_total == actual_total:
            self.stdout.write(self.style.SUCCESS('✅ Все чаты созданы корректно!'))
        else:
            self.stdout.write(self.style.ERROR(f'❌ Не хватает {expected_total - actual_total} чатов'))