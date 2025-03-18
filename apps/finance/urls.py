from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FinanceSummaryView

router = DefaultRouter()

urlpatterns = [
    path("", include(router.urls)),
    path("summary/", FinanceSummaryView.as_view(), name="finance-summary"),  # ✅ Теперь View подключен правильно
]
