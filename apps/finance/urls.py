from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FinanceViewSet

router = DefaultRouter()
router.register(r'finance', FinanceViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
