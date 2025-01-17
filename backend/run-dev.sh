#!/bin/bash
set -e

echo "Starting Django development server..."
python manage.py runserver 0.0.0.0:8000