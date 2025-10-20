# Use a slim, stable version of Python as the base
FROM python:3.10-slim

# Set environment variables for best practices
# PYTHONUNBUFFERED ensures logs are sent directly to Render's log stream
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies needed by some Python packages
RUN apt-get update && apt-get install -y \
    # Needed for PostgreSQL
    libpq-dev \
    # build-essential contains tools like 'gcc'
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file first to leverage Docker's layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your project's code into the container
COPY . .

# Expose the port that gunicorn will run on
EXPOSE 8000

# The CMD is now gone. The start command will be handled by a separate script.