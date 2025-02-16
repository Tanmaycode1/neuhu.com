FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV DEBIAN_FRONTEND noninteractive
ENV PYTHONPATH=/app:$PYTHONPATH
ENV DJANGO_SETTINGS_MODULE=core.settings

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev \
    python3-dev \
    ffmpeg \
    libmagic1 \
    gcc \
    g++ \
    make \
    curl \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install channels channels-redis daphne

COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh

RUN mkdir -p /app/media/audio /app/media/avatars /app/static /app/staticfiles /app/core/utils
RUN chmod -R 755 /app

COPY . .

RUN python -c "import core; print('Core module found')"

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "core.asgi:application", "--websocket-timeout", "300"]