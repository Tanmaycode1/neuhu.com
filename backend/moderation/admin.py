from django.contrib import admin
from .models import Report, ContentFilter

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('reporter', 'reported_user', 'report_type', 'status', 'created_at')
    list_filter = ('report_type', 'status', 'created_at')
    search_fields = ('reporter__username', 'reported_user__username', 'content')
    readonly_fields = ('created_at',)

@admin.register(ContentFilter)
class ContentFilterAdmin(admin.ModelAdmin):
    list_display = ('keyword', 'is_regex', 'is_active', 'created_by', 'created_at')
    list_filter = ('is_regex', 'is_active', 'created_at')
    search_fields = ('keyword', 'replacement')
