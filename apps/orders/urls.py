from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductRequestViewSet

router = DefaultRouter()
router.register(r'product-requests', ProductRequestViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
