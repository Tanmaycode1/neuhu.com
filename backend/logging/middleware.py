from django.utils.deprecation import MiddlewareMixin
from .models import SystemLog
import json

class LoggingMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # Skip logging for static and media files
        if request.path.startswith(('/static/', '/media/')):
            return None

        # Create log entry
        log_data = {
            'level': 'INFO',
            'type': 'USER',
            'action': f"{request.method} {request.path}",
            'details': {
                'method': request.method,
                'path': request.path,
                'query_params': dict(request.GET),
            },
            'ip_address': self.get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
        }

        if request.user.is_authenticated:
            log_data['user'] = request.user

        SystemLog.objects.create(**log_data)
        return None

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR') 