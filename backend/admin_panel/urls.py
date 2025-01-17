from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AdminPanelViewSet, StaffManagementViewSet

router = DefaultRouter()
router.register(r'dashboard', AdminPanelViewSet, basename='admin-dashboard')
router.register(r'staff', StaffManagementViewSet, basename='staff-management')

urlpatterns = [
    path('', include(router.urls)),
] 