FROM python:3.12-slim

# System dependencies for psycopg (libpq), GeoAlchemy2 (geos/proj/gdal), and build tools
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libgeos-dev \
        libproj-dev \
        gdal-bin \
        git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN useradd --uid 1000 --create-home app

WORKDIR /app

# Ensure the backend directory exists so the COPY below is always valid
RUN mkdir -p /app/backend

# Copy source (no-op if backend/ is empty or not yet scaffolded — Bundle 3 fills this)
COPY backend/ /app/backend/

# Install in editable mode; falls back gracefully if pyproject.toml doesn't exist yet
RUN pip install --no-cache-dir -e /app/backend \
    || echo 'backend not yet scaffolded — install at runtime'

USER app

EXPOSE 8000

# --reload enables live-reload during development; override CMD for celery workers
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
