from rest_framework import permissions

class IsSuperuserOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.is_superuser or (
            hasattr(request.user, 'role') and 
            request.user.role.role_type in ['SUPERUSER', 'ADMIN']
        )

class IsModeratorOrAbove(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.is_superuser or (
            hasattr(request.user, 'role') and 
            request.user.role.role_type in ['SUPERUSER', 'ADMIN', 'MODERATOR']
        ) 