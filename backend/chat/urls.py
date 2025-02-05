from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'chat'

# Create a router for chat rooms
router = DefaultRouter()
router.register(r'rooms', views.ChatRoomViewSet, basename='chatroom')

urlpatterns = [
    # Nested routes for messages within rooms
    path('rooms/<uuid:room_pk>/messages/', views.MessageViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='room-messages'),
    
    path('rooms/<uuid:room_pk>/messages/mark-all-read/', views.MessageViewSet.as_view({
        'post': 'mark_all_read'
    }), name='room-messages-mark-all-read'),
    
    path('rooms/<uuid:room_pk>/messages/delete-all/', views.MessageViewSet.as_view({
        'delete': 'delete_all'
    }), name='room-messages-delete-all'),
    
    path('rooms/<uuid:room_pk>/messages/filter/', views.MessageViewSet.as_view({
        'get': 'filter'
    }), name='room-messages-filter'),
    
    path('rooms/<uuid:room_pk>/messages/<uuid:pk>/mark-read/', views.MessageViewSet.as_view({
        'post': 'mark_read'
    }), name='message-mark-read'),
    
    # Include the router URLs
    path('', include(router.urls)),
]