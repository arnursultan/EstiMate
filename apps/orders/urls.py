from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrderRequestViewSet, OrderCalculatorView


router = DefaultRouter()
router.register(r'order-requests', OrderRequestViewSet, basename="order-request")

urlpatterns = [
    path("", include(router.urls)),
    path("calculator/", OrderCalculatorView.as_view(), name="order-calculator"),

]
