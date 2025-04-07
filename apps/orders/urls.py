from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductRequestViewSet

router = DefaultRouter()
router.register(r'product-requests', ProductRequestViewSet, basename='product-request')

urlpatterns = [
    path('', include(router.urls)),
    path('bulk-self-request/', ProductRequestViewSet.as_view({'post': 'bulk_self_request'}), name='bulk-self-request'),
    path('bulk-store-request/', ProductRequestViewSet.as_view({'post': 'bulk_store_request'}), name='bulk-store-request'),
]
