from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductViewSet, PartnerProductViewSet

router = DefaultRouter()
router.register(r'products', ProductViewSet)
router.register(r'partner-products', PartnerProductViewSet, basename='partner-product')

urlpatterns = [
    path('', include(router.urls)),
]