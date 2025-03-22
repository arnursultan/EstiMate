from django.urls import path
from .views import ApplicationCreateAPIView, ApplicationActionAPIView, ApplicationListAPIView

urlpatterns = [
    path('applications/', ApplicationCreateAPIView.as_view(), name='application-create'),
    path('applications/list/', ApplicationListAPIView.as_view(), name='application-list'),
    path('applications/<int:pk>/<str:action>/', ApplicationActionAPIView.as_view(), name='application-action'),
]
