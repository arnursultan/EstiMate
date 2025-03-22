from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework.permissions import AllowAny
import os
from apps.chats.routing import websocket_urlpatterns

schema_view = get_schema_view(
    openapi.Info(
        title="BaiEl API",
        default_version="v1",
        description="Документация API BaiEl CRM",
    ),
    public=True,
    permission_classes=[AllowAny],
)

urlpatterns = [
    path("admin/", admin.site.urls),

    path("api/users/", include("apps.users.urls")),
    path("api/products/", include("apps.products.urls")),
    path("api/stores/", include("apps.stores.urls")),
    path("api/orders/", include("apps.orders.urls")),
    path("api/finance/", include("apps.finance.urls")),
    path("api/chats/", include("apps.chats.urls")),

    # re_path(r"ws/", include(websocket_urlpatterns)),
    path("api/docs/", schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui"),
    path("api/redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
    path('swagger/',schema_view.with_ui('swagger', cache_timeout=0),name='schema-swagger-ui' ),
    ]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
