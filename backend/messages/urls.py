from django.urls import path, include
from rest_framework_nested import routers
from .views import ChatRoomViewSet, MessageViewSet

app_name = 'messages'

router = routers.SimpleRouter()
router.register(r'rooms', ChatRoomViewSet, basename='chatroom')

messages_router = routers.NestedSimpleRouter(router, r'rooms', lookup='room')
messages_router.register(r'messages', MessageViewSet, basename='room-messages')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(messages_router.urls)),
] 