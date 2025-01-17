from celery import shared_task

@shared_task
def example_task():
    """Example periodic task"""
    return "Task completed successfully" 