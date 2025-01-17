from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from logging.models import SystemLog, UserRole, ModeratorAction
from .serializers import (
    SystemLogSerializer, UserRoleSerializer, 
    ModeratorActionSerializer, AdminUserSerializer
)
from .permissions import IsSuperuserOrAdmin, IsModeratorOrAbove
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

User = get_user_model()

class AdminPanelViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsSuperuserOrAdmin]

    @swagger_auto_schema(
        operation_description="Get admin dashboard statistics",
        responses={
            200: openapi.Response(
                description="Dashboard statistics",
                examples={
                    "application/json": {
                        "users": {
                            "total": 0,
                            "new_24h": 0,
                            "new_7d": 0
                        },
                        "posts": {
                            "total": 0,
                            "new_24h": 0,
                            "reported": 0
                        },
                        "moderation": {
                            "pending_reports": 0,
                            "actions_24h": 0
                        }
                    }
                }
            )
        }
    )
    @action(detail=False, methods=['get'])
    def dashboard_stats(self, request):
        """Get admin dashboard statistics"""
        now = timezone.now()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)

        stats = {
            'users': {
                'total': User.objects.count(),
                'new_24h': User.objects.filter(date_joined__gte=last_24h).count(),
                'new_7d': User.objects.filter(date_joined__gte=last_7d).count(),
            },
            'posts': {
                'total': Post.objects.count(),
                'new_24h': Post.objects.filter(created_at__gte=last_24h).count(),
                'reported': Post.objects.filter(reports__isnull=False).distinct().count(),
            },
            'moderation': {
                'pending_reports': Report.objects.filter(status='PENDING').count(),
                'actions_24h': ModeratorAction.objects.filter(created_at__gte=last_24h).count(),
            }
        }
        return Response(stats)

    @swagger_auto_schema(
        operation_description="Get system logs with filtering",
        manual_parameters=[
            openapi.Parameter(
                'level', 
                openapi.IN_QUERY,
                description="Log level",
                type=openapi.TYPE_STRING,
                enum=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            ),
            openapi.Parameter(
                'type', 
                openapi.IN_QUERY,
                description="Log type",
                type=openapi.TYPE_STRING,
                enum=['AUTH', 'USER', 'CONTENT', 'SYSTEM', 'ADMIN']
            ),
        ],
        responses={200: SystemLogSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def live_logs(self, request):
        """Get system logs with filtering"""
        queryset = SystemLog.objects.all()
        
        # Apply filters
        level = request.query_params.get('level')
        type = request.query_params.get('type')
        user_id = request.query_params.get('user_id')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        if level:
            queryset = queryset.filter(level=level.upper())
        if type:
            queryset = queryset.filter(type=type.upper())
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)

        # Paginate results
        page = self.paginate_queryset(queryset)
        serializer = SystemLogSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

class StaffManagementViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsSuperuserOrAdmin]
    serializer_class = AdminUserSerializer

    def get_queryset(self):
        return User.objects.filter(
            Q(is_staff=True) | 
            Q(role__isnull=False)
        ).select_related('role')

    @action(detail=True, methods=['post'])
    def assign_role(self, request, pk=None):
        user = self.get_object()
        role_type = request.data.get('role_type')
        permissions = request.data.get('permissions', {})

        # Validate role assignment permissions
        if not request.user.is_superuser and role_type == 'SUPERUSER':
            return Response(
                {'error': 'Only superusers can assign superuser role'},
                status=status.HTTP_403_FORBIDDEN
            )

        role, created = UserRole.objects.update_or_create(
            user=user,
            defaults={
                'role_type': role_type,
                'permissions': permissions,
                'created_by': request.user
            }
        )

        # Update user staff status
        user.is_staff = True
        if role_type == 'SUPERUSER':
            user.is_superuser = True
        user.save()

        return Response(UserRoleSerializer(role).data)

    @action(detail=True, methods=['post'])
    def remove_role(self, request, pk=None):
        user = self.get_object()
        
        # Can't remove superuser role unless you're a superuser
        if user.is_superuser and not request.user.is_superuser:
            return Response(
                {'error': 'Only superusers can remove superuser role'},
                status=status.HTTP_403_FORBIDDEN
            )

        UserRole.objects.filter(user=user).delete()
        user.is_staff = False
        user.is_superuser = False
        user.save()

        return Response(status=status.HTTP_204_NO_CONTENT)
