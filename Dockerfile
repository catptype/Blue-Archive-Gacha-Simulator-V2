# --- Stage 1: Builder ---
FROM python:3.10-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    pkg-config \
    default-libmysqlclient-dev \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install them in isolated path
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Stage 2: Final Image ---
FROM python:3.10-slim

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    curl \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SUPERUSER_USERNAME=admin \
    DJANGO_SUPERUSER_EMAIL=admin@example.com \
    DJANGO_SUPERUSER_PASSWORD=1234

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy project code
COPY . .

# Collect staticfiles for deploy production
RUN python manage.py migrate && \
    python manage.py unpack && \
    python manage.py createsuperuser --noinput && \
    python manage.py collectstatic --noinput

# Expose necessary ports
EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]