from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import Post, TrendingScore
from django.db.models import Count

@shared_task
def update_trending_scores():
    """Update trending scores for all posts periodically"""
    time_window = timezone.now() - timedelta(days=7)
    posts = Post.objects.filter(
        created_at__gte=time_window
    ).select_related('trending_score')

    for post in posts:
        try:
            trending_score = post.trending_score
        except TrendingScore.DoesNotExist:
            trending_score = TrendingScore.objects.create(post=post)

        # Update counts
        trending_score.like_count = post.likes.count()
        trending_score.comment_count = post.comments.count()
        trending_score.share_count = post.postinteraction_set.filter(
            interaction_type='SHARE'
        ).count()

        # Calculate score
        time_diff = timezone.now() - post.created_at
        hours_since_posted = time_diff.total_seconds() / 3600

        score = (
            trending_score.like_count * 1.5 +
            trending_score.comment_count * 2.0 +
            trending_score.share_count * 2.5
        ) / (hours_since_posted + 2) ** 1.8

        trending_score.score = score
        trending_score.save() 