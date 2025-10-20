# Use a single, slim Python base image
FROM python:3.10-slim

# Set environment variables for the container
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set Application environment variables (use for deploy production)
ENV PRODUCTION=0
ENV USE_HTTPS=0
ENV SECRET_KEY=offline-secret-key-need-to-change-when-deploy-production


# Set Django superuser credentials (for development/initial setup)
ENV DJANGO_SUPERUSER_USERNAME=admin
ENV DJANGO_SUPERUSER_EMAIL=admin@example.com
ENV DJANGO_SUPERUSER_PASSWORD=1234

# Set the working directory in the container
WORKDIR /app

# --- Step 1: Install System Dependencies ---
# First, install the build-time dependencies needed to install Python packages.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        pkg-config \
        default-libmysqlclient-dev \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

# --- Step 2: Install Python Dependencies ---
# Copy the requirements file and install the packages.
# This is done in a separate step to leverage Docker's layer caching.
# If your requirements.txt doesn't change, Docker will reuse the cached layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Step 3: Install Runtime-Only System Dependencies & Clean Up ---
# Now that pip install is done, we can remove the build dependencies
# and install the smaller set of runtime-only libraries.
RUN apt-get purge -y --auto-remove \
        build-essential \
        pkg-config \
        default-libmysqlclient-dev \
    && apt-get update && \
    apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# --- Step 4: Copy Project Code ---
# Copy the rest of your application's source code.
COPY . .

# --- Step 5: Run Django Management Commands ---
# This single RUN command executes all necessary setup steps.
RUN python manage.py migrate && \
    python manage.py unpack && \
    python manage.py createsuperuser --noinput && \
    python manage.py collectstatic --noinput

# Expose the port the app runs on
EXPOSE 8000

# --- Step 6: Define the command to run the application ---
# For development, runserver is okay. For production, consider using Gunicorn.
# CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "Blue_Archive_Gacha_Simulator.wsgi:application"]