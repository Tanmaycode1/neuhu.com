#!/bin/bash
set -e

wait_for_service() {
    local host="$1"
    local port="$2"
    local service="$3"
    
    echo "Waiting for $service..."
    while ! nc -z "$host" "$port"; do
        echo "Waiting for $service at $host:$port..."
        sleep 1
    done
    echo "$service is up!"
}

# Debug information
echo "Current directory: $(pwd)"
echo "Python path: $PYTHONPATH"
echo "Django settings module: $DJANGO_SETTINGS_MODULE"
ls -la /app/core/

# Wait for essential services
wait_for_service db 5432 "PostgreSQL"
wait_for_service redis 6379 "Redis"

# Initialize application
python manage.py migrate
python manage.py collectstatic --noinput

# Verify Django configuration
python -c "
import django
from django.conf import settings
print(f'Django version: {django.get_version()}')
print(f'Settings module: {settings.SETTINGS_MODULE}')
"

# Start application
if [ "$DJANGO_ENV" = "production" ]; then
    echo "Starting production server..."
    gunicorn core.wsgi:application --bind 0.0.0.0:8000 --workers 4 --log-level debug
else
    echo "Starting development server..."
    python manage.py runserver 0.0.0.0:8000
fi