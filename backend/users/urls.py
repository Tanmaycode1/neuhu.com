from django.urls import path
from . import views

urlpatterns = [
    # Public endpoints (no auth required)
    path('send-verification-otp/', views.send_verification_otp, name='send-otp'),
    path('verify-email-otp/', views.verify_email_otp, name='verify-otp'),
    path('check-email/<str:email>/', views.check_email, name='check-email'),
    
    # Protected endpoints (auth required)
    path('me/', views.get_profile, name='get-profile'),
    path('me/avatar/', views.update_avatar, name='update-avatar'),
    path('me/profile/', views.update_profile, name='update-profile'),

    # Additional UserViewSet actions
    path('<uuid:pk>/follow/', views.UserViewSet.as_view({'post': 'follow'}), name='follow-user'),
    path('<uuid:pk>/unfollow/', views.UserViewSet.as_view({'post': 'unfollow'}), name='unfollow-user'),
    path('following/', views.UserViewSet.as_view({'get': 'following'}), name='user-following'),
    path('followers/', views.UserViewSet.as_view({'get': 'followers'}), name='user-followers'),
    path('me/', views.UserViewSet.as_view({'get': 'me'}), name='user-me'),
    path('search/', views.UserViewSet.as_view({'get': 'search'}), name='user-search'),
    path('suggestions/', views.UserViewSet.as_view({'get': 'suggestions'}), name='user-suggestions'),
]