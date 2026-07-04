# AWS App Runner / ECS Fargate image for the UdyamMitra AI FastAPI backend.
# App Runner injects PORT (8080 by default) and serves over HTTPS at the edge.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps for psycopg2 (Postgres driver for Aurora) + build toolchain.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first for layer caching. psycopg2-binary (in
# requirements.txt) is included for Aurora Postgres connectivity; SQLite is the
# local-dev default.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy app source.
COPY . .

# Create the data dir so SQLite (local/fallback) has a writable home. On App
# Runner the real DB is Aurora via DATABASE_URL; this is just a safety net.
RUN mkdir -p data

# App Runner / Fargate expect 0.0.0.0 and the injected $PORT. Use a shell form
# so the env var expands at runtime.
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

# Health: App Runner pings this path (configured in the console/CDK).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://localhost:${PORT:-8000}/health || exit 1