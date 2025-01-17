from django.contrib import admin
from .models import Post, Comment, PostInteraction, TrendingScore

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('id', 'author', 'type', 'title', 'created_at', 'likes_count')
    list_filter = ('type', 'created_at')
    search_fields = ('title', 'description', 'author__username')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'

    def likes_count(self, obj):
        return obj.likes.count()

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'author', 'post', 'content', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('content', 'author__username')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(PostInteraction)
class PostInteractionAdmin(admin.ModelAdmin):
    list_display = ('id', 'post', 'user', 'interaction_type', 'created_at')
    list_filter = ('interaction_type', 'created_at')
    search_fields = ('post__title', 'user__username')

@admin.register(TrendingScore)
class TrendingScoreAdmin(admin.ModelAdmin):
    list_display = ('post', 'score', 'view_count', 'like_count', 'comment_count', 'share_count')
    list_filter = ('last_calculated',)
    search_fields = ('post__title',)
    readonly_fields = ('last_calculated',)
