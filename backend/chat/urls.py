from django.urls import path
from . import views

urlpatterns = [
    path('rooms/', views.ChatRoomViewSet.as_view({'get': 'list', 'post': 'create'})),
    path('rooms/<str:pk>/', views.ChatRoomViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'delete': 'destroy'
    })),
    path('rooms/<str:room_id>/messages/', views.MessageViewSet.as_view({'get': 'list', 'post': 'create'})),
] 