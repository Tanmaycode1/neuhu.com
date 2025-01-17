#!/bin/bash
set -e

echo "Starting Celery worker..."
celery -A core worker \
    -l INFO \
    --uid=celery \
    --gid=celery 