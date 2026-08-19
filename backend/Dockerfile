FROM python:3.12-slim

# System dependencies for WeasyPrint and Pillow, plus gosu — used by
# docker-entrypoint.sh to drop from root to appuser after fixing volume
# ownership (see that file for why this can't just be a Dockerfile USER).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    media-types \
    fonts-liberation \
    fonts-dejavu-core \
    gosu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# This image is reachable from the internet in production
# (docker-compose.prod.yml), so the app itself must never run as root —
# docker-entrypoint.sh does the actual privilege drop at container start
# (not here) because uploads_data/secure_uploads_data are named volumes
# that mount fresh, root-owned directories at runtime, overriding whatever
# a Dockerfile-time `USER appuser` + chown would have set.
RUN mkdir -p /app/uploads /app/secure_uploads \
    && useradd -m appuser \
    && chown -R appuser:appuser /app \
    && chmod +x /app/docker-entrypoint.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]

EXPOSE 8000
