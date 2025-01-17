from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.NotificationViewSet.as_view({'get': 'list'}), name='notification-list'),
    path('mark-read/', views.NotificationViewSet.as_view({'post': 'mark_read'}), name='mark-read'),
    path('mark-all-read/', views.NotificationViewSet.as_view({'post': 'mark_all_read'}), name='mark-all-read'),
] 