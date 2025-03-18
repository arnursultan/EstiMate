from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Sum
from apps.finance.models import Finance
from datetime import datetime, timedelta


class FinanceSummaryView(APIView):
    def get_finance_summary(self, start_date):
        summary = Finance.objects.filter(created_at__gte=start_date).aggregate(
            total_income=Sum("income", default=0),
            total_expense=Sum("expense", default=0),
            total_debt=Sum("debt", default=0),
            total_payment=Sum("payment", default=0),
            total_bonus=Sum("bonus", default=0),
        )
        summary["total_debt"] = max(summary["total_debt"] - summary["total_payment"], 0)

        return summary

    def get(self, request):
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        return Response({
            "today": self.get_finance_summary(today),
            "week": self.get_finance_summary(week_ago),
            "month": self.get_finance_summary(month_ago),
        })
