from django.contrib import admin
from .models import SearchLog

@admin.register(SearchLog)
class SearchLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'query', 'search_type', 'results_count', 'created_at', 'ip_address')
    list_filter = ('search_type', 'created_at')
    search_fields = ('query', 'user__username', 'ip_address')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
