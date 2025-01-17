#!/bin/bash
set -e

echo "Starting Celery beat..."
celery -A core beat \
    -l INFO \
    --uid=celery \
    --gid=celery 