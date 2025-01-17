from django.contrib import admin
from .models import SystemLog, UserRole, ModeratorAction

@admin.register(SystemLog)
class SystemLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'level', 'type', 'user', 'action', 'ip_address')
    list_filter = ('level', 'type', 'timestamp')
    search_fields = ('action', 'user__username', 'ip_address')
    readonly_fields = ('timestamp',)

@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('user', 'role_type', 'created_by', 'created_at')
    list_filter = ('role_type', 'created_at')
    search_fields = ('user__username', 'created_by__username')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(ModeratorAction)
class ModeratorActionAdmin(admin.ModelAdmin):
    list_display = ('moderator', 'action_type', 'target_user', 'created_at')
    list_filter = ('action_type', 'created_at')
    search_fields = ('moderator__username', 'target_user__username', 'reason')
    readonly_fields = ('created_at',) 