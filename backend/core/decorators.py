import functools
import logging
from typing import Callable, Type
from django.core.exceptions import ValidationError
from rest_framework import status
from django.core.cache import cache
from .utils.response import api_response

logger = logging.getLogger(__name__)

def cache_response(timeout=300):
    """
    Cache the response of a view for a specified time
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(view, request, *args, **kwargs):
            # Generate cache key
            cache_key = f"{func.__name__}:{request.path}:{request.user.id}"
            
            # Try to get from cache
            response = cache.get(cache_key)
            if response is None:
                response = func(view, request, *args, **kwargs)
                cache.set(cache_key, response, timeout)
            return response
        return wrapper
    return decorator

def handle_exceptions(func: Callable) -> Callable:
    """
    Handle common exceptions in views
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            return api_response(
                success=False,
                message="Validation error",
                errors=e.message_dict if hasattr(e, 'message_dict') else {'error': str(e)},
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.exception(f"Unexpected error in {func.__name__}: {str(e)}")
            return api_response(
                success=False,
                message="Internal server error",
                errors={'error': str(e)},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    return wrapper

def validate_request_data(serializer_class: Type) -> Callable:
    """
    Validate request data using a serializer
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(view, request, *args, **kwargs):
            serializer = serializer_class(data=request.data)
            if not serializer.is_valid():
                return api_response(
                    success=False,
                    message="Invalid request data",
                    errors=serializer.errors,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            return func(view, request, serializer, *args, **kwargs)
        return wrapper
    return decorator

def paginate_response(func: Callable) -> Callable:
    """
    Handle pagination for list views
    """
    @functools.wraps(func)
    def wrapper(view, *args, **kwargs):
        queryset = func(view, *args, **kwargs)
        page = view.paginate_queryset(queryset)
        if page is not None:
            serializer = view.get_serializer(page, many=True)
            return view.get_paginated_response(serializer.data)
        serializer = view.get_serializer(queryset, many=True)
        return api_response(data=serializer.data)
    return wrapper 