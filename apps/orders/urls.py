from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductRequestViewSet

router = DefaultRouter()
router.register(r'product-requests', ProductRequestViewSet,basename='product-requests') # Не менять basename иначе тесты сломаются

urlpatterns = [
    path('', include(router.urls)),
]
