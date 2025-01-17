from django.urls import path
from . import views

urlpatterns = [
    # Public endpoints (no auth required)
    path('send-verification-otp/', views.send_verification_otp, name='send-otp'),
    path('verify-email-otp/', views.verify_email_otp, name='verify-otp'),
    path('check-email/<str:email>/', views.check_email, name='check-email'),
    
    # Protected endpoints (auth required)
    path('me/', views.get_profile, name='user-profile'),
    path('me/avatar/', views.update_avatar, name='update-avatar'),
    path('me/profile/', views.update_profile, name='update-profile'),
]