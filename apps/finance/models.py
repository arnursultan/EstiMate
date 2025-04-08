from django.db import models
from django.core.exceptions import ValidationError
from apps.orders.models import ProductRequest
from apps.stores.models import Store, City
from apps.users.models import User
from apps.products.models import PartnerProduct


# Модифицируем apps/finance/models.py

class PartnerFinanceStat(models.Model):
    """Статистика по финансам партнера"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='finance_stats')
    date = models.DateField()

    # Запрошенные товары (для себя)
    total_requested_quantity = models.PositiveIntegerField(default=0,
                                                           verbose_name="Общее количество запрошенных товаров")
    total_requested_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                                 verbose_name="Общая сумма запрошенных товаров")

    # Проданные товары (для магазинов)
    total_sold_quantity = models.PositiveIntegerField(default=0, verbose_name="Общее количество проданных товаров")
    total_sold_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                            verbose_name="Общая сумма проданных товаров")

    # Долг администратору (по SELF-запросам)
    total_debt_to_admin = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                              verbose_name="Долг администратору")

    # Расходы партнера
    total_expenses = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Общие расходы")

    # Бракованные товары
    total_damaged_quantity = models.PositiveIntegerField(default=0, verbose_name="Общее количество бракованных товаров")

    # Бонусные товары
    total_bonus_quantity = models.PositiveIntegerField(default=0, verbose_name="Общее количество бонусных товаров")

    # Остаток товаров в каталоге
    total_remaining_quantity = models.PositiveIntegerField(default=0, verbose_name="Общий остаток товаров")

    # Детали по товарам (для хранения разбивки по товарам)
    detailed_data = models.JSONField(default=dict, blank=True, verbose_name="Детальные данные по товарам")

    class Meta:
        unique_together = ('user', 'date')
        ordering = ['-date']
        verbose_name = "Финансовая статистика партнера"
        verbose_name_plural = "Финансовая статистика партнеров"

    def __str__(self):
        return f"{self.user} - {self.date}"


class StoreFinanceStat(models.Model):
    """Статистика по финансам магазина"""
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='finance_stats')
    date = models.DateField()

    # Полученные товары (от партнеров)
    total_received_quantity = models.PositiveIntegerField(default=0, verbose_name="Общее количество полученных товаров")

    # Бонусные товары
    total_bonus_quantity = models.PositiveIntegerField(default=0, verbose_name="Общее количество бонусных товаров")

    # Бракованные товары
    total_damaged_quantity = models.PositiveIntegerField(default=0, verbose_name="Общее количество бракованных товаров")

    # Долг (общий)
    total_debt = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Общий долг")

    # Погашенный долг
    total_paid_debt = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Погашенный долг")

    # Расходы партнера, связанные с этим магазином
    total_partner_expenses = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                                 verbose_name="Расходы партнера")

    # Прибыль (погашенный долг - расходы)
    profit = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Прибыль")

    # Детали по товарам
    detailed_data = models.JSONField(default=dict, blank=True, verbose_name="Детальные данные по товарам")

    class Meta:
        unique_together = ('store', 'date')
        ordering = ['-date']
        verbose_name = "Финансовая статистика магазина"
        verbose_name_plural = "Финансовая статистика магазинов"

    def __str__(self):
        return f"{self.store} - {self.date}"


class FinanceEntry(models.Model):
    """Ручные финансовые записи"""
    ENTRY_TYPE_CHOICES = (
        ('expense', 'Расход'),
        ('income', 'Доход'),
        ('sale', 'Продажа'),
        ('damage', 'Брак'),
        ('return', 'Возврат'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='manual_finance_entries')
    date = models.DateField(blank=False, null=False)
    entry_type = models.CharField(max_length=10, choices=ENTRY_TYPE_CHOICES, default='expense',
                                  verbose_name="Тип записи")
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Сумма")
    quantity = models.PositiveIntegerField(default=0, verbose_name="Количество")
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Город")

    store = models.ForeignKey(
        'stores.Store',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='finance_entries',
        verbose_name="Магазин"
    )

    # Для записей, связанных с товарами
    partner_product = models.ForeignKey(
        'products.PartnerProduct',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='finance_entries',
        verbose_name="Товар из каталога"
    )

    note = models.TextField(blank=True, verbose_name="Примечание")

    class Meta:
        ordering = ['-date']
        verbose_name = "Финансовая запись"
        verbose_name_plural = "Финансовые записи"

    def __str__(self):
        return f"{self.user} - {self.date}: {self.get_entry_type_display()}={self.amount}"

    def clean(self):
        """Валидация модели"""
        super().clean()

        # Для записей типа 'sale', 'damage', 'return' нужен partner_product
        if self.entry_type in ['sale', 'damage', 'return'] and not self.partner_product:
            raise ValidationError({
                                      "partner_product": f"Для записи типа '{self.get_entry_type_display()}' необходимо указать товар из каталога"})

        # Для записей типа 'sale', 'damage', 'return' нужен quantity
        if self.entry_type in ['sale', 'damage', 'return'] and self.quantity <= 0:
            raise ValidationError({
                                      "quantity": f"Для записи типа '{self.get_entry_type_display()}' необходимо указать положительное количество"})

        # Для записей типа 'expense', 'income' quantity не нужен
        if self.entry_type in ['expense', 'income'] and self.quantity > 0:
            raise ValidationError(
                {"quantity": f"Для записи типа '{self.get_entry_type_display()}' не нужно указывать количество"})

        # Проверка достаточного количества товара для записей типа 'sale', 'damage'
        if self.entry_type in ['sale', 'damage'] and self.partner_product:
            if self.quantity > self.partner_product.remaining_quantity:
                raise ValidationError(
                    {"quantity": f"Недостаточно товара в каталоге. Доступно: {self.partner_product.remaining_quantity}"}
                )

        # Проверка достаточного проданного количества для записей типа 'return'
        if self.entry_type == 'return' and self.partner_product:
            if self.quantity > self.partner_product.sold_quantity:
                raise ValidationError(
                    {
                        "quantity": f"Возврат не может превышать проданное количество ({self.partner_product.sold_quantity})"}
                )

    def save(self, *args, **kwargs):
        # Обработка для разных типов записей
        if self.entry_type == 'sale' and self.partner_product:
            # Записываем продажу в партнерский товар
            self.partner_product.record_sale(self.quantity)

            # Расчет суммы на основе цены товара и количества
            self.amount = self.quantity * self.partner_product.price

        elif self.entry_type == 'damage' and self.partner_product:
            # Записываем брак в партнерский товар
            self.partner_product.record_damage(self.quantity)

            # Расчет суммы на основе цены товара и количества
            self.amount = self.quantity * self.partner_product.price

        elif self.entry_type == 'return' and self.partner_product:
            # Записываем возврат в партнерский товар
            self.partner_product.record_return(self.quantity)

            # Расчет суммы на основе цены товара и количества
            self.amount = self.quantity * self.partner_product.price

        super().save(*args, **kwargs)

        # Обновляем статистику календаря
        from .services import update_calendar_statistics
        update_calendar_statistics(
            self.date,
            user=self.user,
            has_expenses=(self.entry_type == 'expense'),
            has_sales=(self.entry_type == 'sale')
        )


class CalendarStatistics(models.Model):
    """Модель для хранения меток календаря с данными"""
    date = models.DateField(verbose_name="Дата")
    has_sales = models.BooleanField(default=False, verbose_name="Были продажи")
    has_requests = models.BooleanField(default=False, verbose_name="Были запросы")
    has_expenses = models.BooleanField(default=False, verbose_name="Были расходы")
    has_debt_payment = models.BooleanField(default=False, verbose_name="Были погашения долгов")
    has_damages = models.BooleanField(default=False, verbose_name="Был брак")  # Новое поле
    has_returns = models.BooleanField(default=False, verbose_name="Были возвраты")  # Новое поле

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='calendar_marks',
        null=True,
        blank=True,
        verbose_name="Партнер"
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name='calendar_marks',
        null=True,
        blank=True,
        verbose_name="Магазин"
    )
    city = models.ForeignKey(
        City,
        on_delete=models.CASCADE,
        related_name='calendar_marks',
        null=True,
        blank=True,
        verbose_name="Город"
    )

    class Meta:
        unique_together = ('date', 'user', 'store', 'city')
        verbose_name = "Метка календаря"
        verbose_name_plural = "Метки календаря"
        ordering = ['-date']

    def __str__(self):
        entity = self.user or self.store or self.city or "Общие данные"
        return f"{entity} - {self.date}"


class ArchivedDailySummary(models.Model):
    """Архивная сводка данных по дням для партнера"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='archived_summaries')
    date = models.DateField()

    total_requests = models.IntegerField(default=0, verbose_name="Всего запросов")
    total_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Общая сумма продаж")
    total_expenses = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                         verbose_name="Общая сумма расходов")
    total_profit = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Общая прибыль")
    total_damages = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Общая сумма брака")
    total_returns = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                        verbose_name="Общая сумма возвратов")
    total_bonus = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Общая сумма бонусов")

    data = models.JSONField(default=dict, blank=True, verbose_name="Дополнительные данные")

    class Meta:
        unique_together = ('user', 'date')
        verbose_name = "Архивная сводка"
        verbose_name_plural = "Архивные сводки"
        ordering = ['-date']

    def __str__(self):
        return f"{self.user} - {self.date}: Прибыль={self.total_profit}"


class InventorySummary(models.Model):
    """Сводка по остаткам товаров партнера"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='inventory_summaries')
    date = models.DateField(auto_now_add=True)

    total_quantity = models.PositiveIntegerField(default=0, verbose_name="Общее количество")
    total_sold = models.PositiveIntegerField(default=0, verbose_name="Продано")
    total_damaged = models.PositiveIntegerField(default=0, verbose_name="Брак")
    total_bonus = models.PositiveIntegerField(default=0, verbose_name="Бонус")
    total_returned = models.PositiveIntegerField(default=0, verbose_name="Возвращено")
    total_remaining = models.PositiveIntegerField(default=0, verbose_name="Остаток")

    # Стоимостные показатели
    total_value = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Общая стоимость")
    total_sold_value = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                           verbose_name="Стоимость проданного")
    total_damaged_value = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                              verbose_name="Стоимость брака")
    total_bonus_value = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                            verbose_name="Стоимость бонусов")
    total_remaining_value = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                                verbose_name="Стоимость остатков")

    data = models.JSONField(default=dict, blank=True, verbose_name="Детализация по товарам")

    class Meta:
        unique_together = ('user', 'date')
        verbose_name = "Сводка по остаткам"
        verbose_name_plural = "Сводки по остаткам"
        ordering = ['-date']

    def __str__(self):
        return f"{self.user} - {self.date}: Остаток={self.total_remaining} шт."