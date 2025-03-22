from django.core.exceptions import ValidationError
from django.db import models
from django.conf import settings


class Application(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Ожидает'),
        ('approved', 'Активирована'),
        ('rejected', 'Отклонена'),
    ]

    full_name = models.CharField(max_length=255, verbose_name="ФИО владельца")
    phone_number = models.CharField(max_length=50, verbose_name="Телефон")
    inn = models.CharField(max_length=14, unique=True, verbose_name="ИНН магазина")
    city = models.CharField(max_length=50, verbose_name="Город")
    address = models.CharField(max_length=255, verbose_name="Адрес")
    title = models.CharField(max_length=255, verbose_name="Название магазина", blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', verbose_name="Статус заявки")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата подачи заявки")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Владелец")

    def move_to_store(self):
        existing_store = Store.objects.filter(inn=self.inn).first()

        if existing_store:
            raise ValidationError("Магазин с таким ИНН уже существует.")
        # Создание магазина
        store = Store(
            name=self.title,
            inn=self.inn,
            city=self.city,
            address=self.address,
            contact_name=self.full_name,
            phone=self.phone_number,
            status="active",
            owner=self.owner
        )
        store.save()

        self.status = "approved"
        self.save()

        return store


class Store(models.Model):
    STATUS_CHOICES = [('active', 'Активен'), ('inactive', 'Неактивен')]
    CITY_CHOICES = [('Ош', 'Ош'), ('Джалал-Абад', 'Джалал-Абад'), ('Баткен', 'Баткен')]

    name = models.CharField(max_length=255, verbose_name="Название")
    inn = models.CharField(max_length=14, unique=True, verbose_name="ИНН")
    city = models.CharField(max_length=50, choices=CITY_CHOICES, verbose_name="Город")
    address = models.CharField(max_length=255, verbose_name="Адрес")
    contact_name = models.CharField(max_length=255, verbose_name="ФИО владельца")
    phone = models.CharField(max_length=50, verbose_name="Телефон")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Владелец")
    debt = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Текущий долг")
    payment_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Сумма оплат")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="inactive", verbose_name="Статус")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")
    debt_limit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Лимит долга",
                                     null=True, blank=True)

    def __str__(self):
        return f'{self.name} - {self.inn}'

