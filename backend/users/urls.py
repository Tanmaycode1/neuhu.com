from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'', views.UserViewSet)
router.register(r'notifications', views.NotificationViewSet, basename='notification')

urlpatterns = [
    # Public endpoints (no auth required)
    path('send-verification-otp/', views.send_verification_otp, name='send_verification_otp'),
    path('verify-email-otp/', views.verify_email_otp, name='verify_email_otp'),
    path('check-email/<str:email>/', views.check_email, name='check_email'),
    
    # Protected endpoints (auth required)
    path('me/', views.get_profile, name='get-profile'),
    path('me/avatar/', views.update_avatar, name='update-avatar'),
    path('me/profile/', views.update_profile, name='update-profile'),

    # User profile endpoint
    path('profile/<uuid:user_id>/', views.get_user_profile_view, name='user-profile'),

    # Additional UserViewSet actions
    path('<uuid:pk>/follow/', views.UserViewSet.as_view({'post': 'follow'}), name='follow-user'),
    path('<uuid:pk>/unfollow/', views.UserViewSet.as_view({'post': 'unfollow'}), name='unfollow-user'),
    path('following/', views.UserViewSet.as_view({'get': 'following'}), name='user-following'),
    path('followers/', views.UserViewSet.as_view({'get': 'followers'}), name='user-followers'),
    path('me/', views.UserViewSet.as_view({'get': 'me'}), name='user-me'),
    path('search/', views.search_users, name='search-users'),
    path('suggestions/', views.UserViewSet.as_view({'get': 'suggestions'}), name='user-suggestions'),

    # Notification routes
    path('notifications/', views.NotificationViewSet.as_view({'get': 'list'}), name='notifications-list'),
    path('notifications/unread/', views.NotificationViewSet.as_view({'get': 'unread'}), name='notifications-unread'),
    path('notifications/mark-all-read/', views.NotificationViewSet.as_view({'post': 'mark_all_read'}), name='notifications-mark-all-read'),
    path('notifications/clear-all/', views.NotificationViewSet.as_view({'delete': 'clear_all'}), name='notification-clear-all'),
    path('notifications/<str:pk>/mark-read/', views.NotificationViewSet.as_view({'post': 'mark_read'}), name='notification-mark-read'),

    # Keep router.urls last
    path('', include(router.urls)),
]