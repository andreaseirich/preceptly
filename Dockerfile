# TutorFlow Production Dockerfile
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=tutorflow.settings

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    gettext \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY backend/ /app/backend/
COPY scripts/entrypoint.sh /app/scripts/entrypoint.sh
RUN chmod +x /app/scripts/entrypoint.sh
WORKDIR /app/backend

# Expose port
EXPOSE 8000

# Entrypoint will run migrations/collectstatic (if applicable) and start gunicorn
# Use exec form to ensure Railway uses this instead of any startCommand
# Note: Railway may override this if a startCommand is set in the UI
ENTRYPOINT ["/bin/bash", "/app/scripts/entrypoint.sh"]
CMD ["/bin/bash", "/app/scripts/entrypoint.sh"]

