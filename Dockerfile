# TutorFlow Production Dockerfile
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=tutorflow.settings

# Set work directory
WORKDIR /app

# Install system dependencies
# git: required for Pygments VCS pin in requirements.txt (CVE-2026-4539) until PyPI > 2.19.2
RUN apt-get update && apt-get install -y \
    git \
    postgresql-client \
    gettext \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Tailscale: lets the container reach a self-hosted Ollama instance on the
# operator's own machine over the tailnet (userspace networking - Railway
# containers get no /dev/net/tun, see scripts/entrypoint.sh for the
# tailscaled startup and apps/ai/client.py for how it's used).
RUN curl -fsSL https://tailscale.com/install.sh | sh

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

