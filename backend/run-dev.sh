#!/bin/bash

# Wait for Redis
until nc -z ${CHANNEL_LAYERS_HOST} 6379; do
    echo "Waiting for Redis..."
    sleep 1
done

# Run migrations
python manage.py migrate

# Start Daphne
daphne -b 0.0.0.0 -p 8000 core.asgi:application