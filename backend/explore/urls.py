from django.urls import path
from . import views

urlpatterns = [
    path('users/search/', views.ExploreViewSet.as_view({'get': 'users'}), name='user-search'),
] 