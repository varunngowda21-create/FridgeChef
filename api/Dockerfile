# Multi-stage Dockerfile for FridgeChef AI REST API
# PRD References: Section 15.1, Section 15.2, Implementation Plan Phase 9 Task 6

# ==========================================
# Stage 1: Build virtual environment
# ==========================================
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies for C-extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create isolated production virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install production dependencies only
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools && \
    pip install --no-cache-dir -r requirements.txt


# ==========================================
# Stage 2: Minimal runtime image
# ==========================================
FROM python:3.11-slim AS runner

WORKDIR /app

# Install runtime dependencies (curl for healthcheck, libpq5 for PostgreSQL)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy production virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create unprivileged application user and group (PRD 15.1)
RUN groupadd -g 10001 fridgechef && \
    useradd -u 10001 -g fridgechef -s /bin/sh -m fridgechef

# Create uploads directory outside code directory with 0700 permissions (PRD 15.1)
RUN mkdir -p /var/lib/fridgechef/uploads && \
    chown -R fridgechef:fridgechef /var/lib/fridgechef/uploads && \
    chmod 700 /var/lib/fridgechef/uploads

# Copy application source files
COPY alembic.ini ./
COPY migrations ./migrations
COPY scripts ./scripts
COPY data ./data
COPY app ./app
COPY entrypoint.sh ./entrypoint.sh

# Ensure executable permissions on entrypoint and ownership by non-root user
RUN chmod +x ./entrypoint.sh && \
    chown -R fridgechef:fridgechef /app

# Switch to non-root user
USER fridgechef

EXPOSE 8000

# Container healthcheck using PRD health route
HEALTHCHECK --interval=10s --timeout=5s --retries=3 --start-period=15s \
    CMD curl -f http://localhost:8000/api/health || exit 1

ENTRYPOINT ["./entrypoint.sh"]

# Environment configuration for concurrency
# Default is 1 worker to ensure in-process rate limiting (PRD 13.1, NFR-022) is globally enforced.
# Multi-worker topologies require an external distributed cache (e.g. Redis).
ENV GUNICORN_WORKERS=1

# Production command: Gunicorn with Uvicorn worker (PRD Section 13.1, 15.1)
CMD ["sh", "-c", "exec gunicorn app.main:app --workers ${GUNICORN_WORKERS:-1} --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --access-logfile - --error-logfile -"]

