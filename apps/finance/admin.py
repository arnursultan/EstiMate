from django.contrib import admin
from .models import Finance

@admin.register(Finance)
class FinanceAdmin(admin.ModelAdmin):
    list_display = ("store", "income", "expense", "get_balance", "debt", "payment", "created_at")  # 🔥 Фикс
    list_filter = ("store", "created_at")
    search_fields = ("store__name", "store__inn")
    readonly_fields = ("created_at",)

    def get_balance(self, obj):
        return obj.income - obj.expense

    get_balance.short_description = "Баланс"

    def save_model(self, request, obj, form, change):
        old_obj = None
        if change:
            old_obj = Finance.objects.get(pk=obj.pk)

        super().save_model(request, obj, form, change)

        if old_obj:
            if obj.debt < old_obj.debt:
                self.message_user(request, f"✅ Долг магазина {obj.store.name} уменьшен: {old_obj.debt} → {obj.debt}")
            if self.get_balance(obj) != self.get_balance(old_obj):
                self.message_user(request, f"📊 Баланс обновлён: {self.get_balance(old_obj)} → {self.get_balance(obj)}")

    def delete_model(self, request, obj):
        self.message_user(request, "❌ Удаление финансовых записей запрещено!", level="error")

    def has_delete_permission(self, request, obj=None):
        return False
