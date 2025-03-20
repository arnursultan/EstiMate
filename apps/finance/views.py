from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Sum
from django.utils import timezone
from apps.finance.models import Finance
from datetime import timedelta

class FinanceSummaryView(APIView):
    def get_finance_summary(self, start_datetime, end_datetime=None):
        """Фильтрует финансы за заданный период, учитывая таймзоны"""
        if timezone.is_naive(start_datetime):
            start_datetime = timezone.make_aware(start_datetime)  # ✅ Делаем "aware", если нужно

        if end_datetime and timezone.is_naive(end_datetime):
            end_datetime = timezone.make_aware(end_datetime)

        summary = Finance.objects.filter(created_at__range=(start_datetime, end_datetime or timezone.now())).aggregate(
            total_income=Sum("income", default=0),
            total_expense=Sum("expense", default=0),
            new_debts=Sum("debt", default=0),
            payments=Sum("payment", default=0),
            total_bonus=Sum("bonus", default=0),
        )

        summary["total_debt"] = max(summary["new_debts"] - summary["payments"], 0)

        return summary

    def get(self, request):
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)  # ✅ UTC-aware
        today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)

        start_of_week = today_start - timedelta(days=today_start.weekday())  # Понедельник
        start_of_month = today_start.replace(day=1)  # 1-й день месяца

        return Response({
            "today": self.get_finance_summary(today_start, today_end),
            "week": self.get_finance_summary(start_of_week),
            "month": self.get_finance_summary(start_of_month),
        })
