# FridgeChef AI — Production Deployment Guide

**Document Version**: 1.0  
**Status**: Approved Production Standard  
**Applies to**: Staging and Production Deployments  
**Source of Truth**: [`FridgeChef_PRD.md`](file:///c:/Users/chara/Desktop/Fridge%20project/FridgeChef_PRD.md) & [`AGENTS.md`](file:///c:/Users/chara/Desktop/Fridge%20project/AGENTS.md)

---

## 1. Architecture Overview

FridgeChef AI is packaged as a multi-container Docker application orchestrated via Docker Compose. The architecture is composed of three isolated services running on a shared internal bridge network (`fridgechef-network`):

```
                     +---------------------------------------+
                     |        Client / Browser / PWA         |
                     +---------------------------------------+
                                         |
                                  HTTP:80 / HTTPS:443
                                         v
                     +---------------------------------------+
                     |       web (Nginx Reverse Proxy)       |
                     |  - Serves static Vite PWA assets      |
                     |  - Proxies /api/* to api:8000         |
                     |  - Enforces Security Headers & gzip   |
                     +---------------------------------------+
                                         |
                                   http://api:8000
                                         v
                     +---------------------------------------+
                     |        api (FastAPI + Gunicorn)       |
                     |  - 1 Gunicorn Uvicorn Worker          |
                     |  - Non-root user (UID 10001)          |
                     |  - Token-bucket rate limiting         |
                     +---------------------------------------+
                            /                       \
             postgresql://db:5432              File Volume
                          v                         v
        +--------------------------------+  +--------------------------------+
        |     db (PostgreSQL 16 Alpine)  |  |   uploads_data Volume (700)    |
        |  - postgres_data volume        |  |  - Ephemeral user scans        |
        |  - Isolated DB network         |  |  - Auto-purged in 24h          |
        +--------------------------------+  +--------------------------------+
```

### 1.1 Service Descriptions
1. **`web` (`fridgechef-web:latest`)**:
   - High-performance Nginx 1.27 Alpine web server.
   - Hosts the compiled Single Page Application and Progressive Web App service worker.
   - Acts as the unified ingress point; terminates TLS (or forwards from Cloudflare/ALB).
   - Forwards `/api/*` traffic to `api:8000` with streaming and header preservation.
   - Non-root execution (`nginx` user).
2. **`api` (`fridgechef-api:latest`)**:
   - Python 3.11+ FastAPI backend application.
   - Served via Gunicorn with `uvicorn.workers.UvicornWorker`.
   - Runs under dedicated unprivileged system user `fridgechef:fridgechef` (UID/GID 10001).
   - Bound strictly to host loopback `127.0.0.1:8000` (no public host exposure).
3. **`db` (`postgres:16-alpine`)**:
   - Relational database storing users, preferences, inventory items, canonical catalogues, recipes, meal plans, and shopping lists.
   - Internal network only (no host port publication).
   - Data persisted via named volume `postgres_data`.

---

## 2. Production Configuration and Secrets

### 2.1 Required Environment Variables

All configuration is strictly injected via environment variables using Pydantic Settings (`api/app/core/config.py`). The production server will **refuse to start** if any required secret is missing or insecure.

| Variable | Description | Type | Production Requirement | Default |
|---|---|---|---|---|
| `APP_ENV` | Application environment | `string` | Must be `production` | `development` |
| `ENVIRONMENT` | Alias for APP_ENV | `string` | Must be `production` | `development` |
| `DATABASE_URL` | PostgreSQL connection string | `string` | Required (`postgresql+psycopg://...`) | — |
| `POSTGRES_USER` | PostgreSQL superuser/app user | `string` | Required (Strong alphanumeric) | `postgres` |
| `POSTGRES_PASSWORD` | PostgreSQL user password | `string` | Required (Min 16 chars) | — |
| `POSTGRES_DB` | Application database name | `string` | Required | `fridgechef` |
| `JWT_SECRET` | Secret key for HS256 JWT tokens | `string` | Required (Min 32 chars / 256 bits) | — |
| `GROQ_API_KEY` | Groq Vision / LLM API key | `string` | Required for AI vision scans | — |
| `AUTH_REFRESH_TRANSPORT` | Refresh token transport | `string` | `cookie` (PRD Section 12.5) | `cookie` |
| `CORS_ORIGINS` | Allowed CORS origins | `string` | Comma-separated production domains | `https://yourdomain.com` |
| `UPLOAD_DIR` | Image uploads directory | `string` | Mounted volume outside web root | `/var/lib/fridgechef/uploads` |
| `GUNICORN_WORKERS` | Number of API worker processes | `integer` | Strictly `1` (unless Redis configured) | `1` |
| `API_PORT_BINDING` | Host port binding for API | `string` | Must be loopback `127.0.0.1:8000` | `127.0.0.1:8000` |
| `DEV_PORT_BINDING` | Host port binding for dev | `string` | Must be loopback `127.0.0.1:5173` | `127.0.0.1:5173` |

### 2.2 Secure Generation of Production & Staging Secrets

Before launching staging or production, generate cryptographically secure random secrets:

```bash
# Generate 256-bit JWT secret (64 hexadecimal characters)
openssl rand -hex 32

# Generate secure PostgreSQL password
openssl rand -base64 24

# For Production:
cp .env.example .env
chmod 600 .env

# For Staging:
cp .env.staging.example .env.staging
chmod 600 .env.staging
```

### 2.3 Staging vs Production Environments
- **Production Compose**: `docker-compose.yml` uses `.env`, binds API to loopback (`127.0.0.1:8000`), mounts `web/nginx.conf`.
- **Staging Compose**: `docker-compose.staging.yml` uses `.env.staging`, supports dual HTTP/HTTPS (`80` and `443`), mounts `web/nginx.staging.conf`, mounts SSL certificates volume, and isolates staging data in `postgres_data_staging` and `uploads_data_staging`.
chmod 600 .env
```

> [!CAUTION]
> Never commit `.env` or production credentials into git. `.env` is permanently excluded via `.gitignore` and `.dockerignore`. All production secrets must be managed through secure environment injection or host secret vaults.

---

## 3. Domain, HTTPS, and Reverse Proxy Configuration

### 3.1 Upstream Proxy Header Mapping (`web/nginx.conf`)

`web/nginx.conf` is configured to prevent header spoofing while correctly passing trusted upstream headers:

```nginx
# Define explicitly trusted upstream proxy CIDRs (RFC 1918 private subnets and loopback)
# Only these trusted proxies can assert X-Forwarded-Proto or client IP via X-Forwarded-For.
geo $trusted_proxy {
    default          0;
    127.0.0.1/32     1;
    10.0.0.0/8       1;
    172.16.0.0/12    1;
    192.168.0.0/16   1;
}

# Only trust incoming X-Forwarded-Proto if sent by an explicitly trusted proxy.
# Arbitrary direct clients sending X-Forwarded-Proto are ignored, falling back strictly to $scheme.
map "$trusted_proxy:$http_x_forwarded_proto" $proxy_x_forwarded_proto {
    "1:https" https;
    "1:http"  http;
    default   $scheme;
}

# Real IP module: Extract genuine client IP only from trusted reverse proxies
set_real_ip_from 127.0.0.1/32;
set_real_ip_from 10.0.0.0/8;
set_real_ip_from 172.16.0.0/12;
set_real_ip_from 192.168.0.0/16;
real_ip_header X-Forwarded-For;
real_ip_recursive on;

server {
    listen 80;
    server_name localhost;

    # Gzip Compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml image/svg+xml;

    # Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # API Reverse Proxy
    location /api {
        proxy_pass http://api:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $proxy_x_forwarded_proto;
        proxy_set_header X-Request-ID $http_x_request_id;
    }

    # SPA & Static Assets
    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files $uri $uri/ /index.html;
    }
}
```

#### Header Spoofing Protection & HSTS Emission Rules
1. **No Header Spoofing**: Direct untrusted clients (`$trusted_proxy = 0`) sending `X-Forwarded-Proto: https` are ignored. Nginx strips the spoofed header and maps `$proxy_x_forwarded_proto` strictly to `$scheme` (`http`).
2. **Dual-Layer Proxy Verification**: FastAPI verifies that the direct connecting peer (`request.client.host`) is within `TRUSTED_PROXIES` before honoring `X-Forwarded-Proto` for rate-limiting or security contexts (`app.core.security.is_request_secure`).
3. **RFC 6797 HSTS Compliance**: `Strict-Transport-Security` is **strictly emitted** only when the connection is genuine HTTPS in production. Direct plain HTTP requests (even in production mode) **never** receive HSTS headers.

### 3.2 TLS Termination Setup (Production Domain)

In production, TLS termination must be placed in front of Nginx:
- **Option A (Certbot / Let's Encrypt directly on Nginx Host)**:
  Obtain a certificate using `certbot certonly --standalone -d app.yourdomain.com` and mount `/etc/letsencrypt` into the `web` container, adding `listen 443 ssl http2;` and `ssl_certificate /etc/letsencrypt/live/...`.
- **Option B (Cloudflare / AWS ALB / GCP Load Balancer - Recommended)**:
  Terminate SSL at the cloud edge. The edge load balancer connects to port 80 and sends `X-Forwarded-Proto: https`. Nginx automatically preserves this header via `map $http_x_forwarded_proto $proxy_x_forwarded_proto`, ensuring FastAPI correctly recognizes HTTPS and issues `Secure` cookies.

### 3.3 Automated Staging SSL Provisioning (`scripts/setup_staging_ssl.sh`)

For staging environments, automated TLS provisioning is provided via `scripts/setup_staging_ssl.sh` and `web/nginx.staging.conf`:

```bash
# Provision real Let's Encrypt certificate for staging domain:
bash scripts/setup_staging_ssl.sh staging.fridgechef.com admin@fridgechef.com

# Rehearsal / offline self-signed fallback (for testing reverse proxy TLS locally):
bash scripts/setup_staging_ssl.sh staging.fridgechef.com selfsigned
```

- **Let's Encrypt Mode**: Performs HTTP-01 challenge through `web/nginx.staging.conf` (`/.well-known/acme-challenge/`), obtains certificates, and installs them into `/etc/letsencrypt/live/<domain>/`.
- **Self-Signed Mode**: Generates a 2048-bit RSA key and self-signed certificate into `/etc/nginx/ssl/` for internal staging rehearsal.
- **Automatic Reload**: Automatically executes `docker compose -f docker-compose.staging.yml exec web nginx -s reload` to apply newly issued certificates without application downtime.

---

## 4. Database Lifecycle, Migrations, and Seeding

### 4.1 Startup Initialization Flow (`api/entrypoint.sh`)

When the API container starts, `api/entrypoint.sh` executes the following deterministic lifecycle:
1. **Connectivity Polling**: Probes PostgreSQL every 2 seconds for up to 30 seconds. If the database is unreachable after 30 seconds, the entrypoint **aborts with a fatal exit (`sys.exit(1)`)**, preventing unmigrated operation.
2. **Database Migrations (`RUN_MIGRATIONS=true`)**: Runs `poetry run alembic upgrade head` to apply all pending schema changes.
3. **Idempotent Data Seeding (`RUN_SEED=true`)**: Runs `scripts/seed_db.py`, which validates referential integrity and inserts canonical ingredients, shelf-life rules, and baseline recipes using `ON CONFLICT DO UPDATE` upsert semantics.
4. **Service Startup**: Launches Gunicorn with 1 worker process.

### 4.2 Manual Migration Commands

To execute migrations or inspect revisions manually inside the container:

```bash
# Check current database revision
docker compose exec api poetry run alembic current

# Check pending migrations
docker compose exec api poetry run alembic heads

# Roll back 1 migration revision
docker compose exec api poetry run alembic downgrade -1

# Roll back to a specific revision ID
docker compose exec api poetry run alembic downgrade <revision_id>
```

> [!IMPORTANT]
> **Zero-Downtime Migration Standard**:
> 1. Never rename or drop active columns in a single release.
> 2. All new columns must be nullable or provide server-side defaults.
> 3. Perform schema expansion first, deploy application code, and then deprecate columns in subsequent releases.

---

## 5. PostgreSQL Backup and Disaster Recovery

### 5.1 Automated Database Backup (`scripts/db_backup.sh`)

The repository includes a dedicated, non-interactive backup utility:
- Executes `pg_dump` with custom/sql format inside the running `db` container.
- Compresses output using `gzip`.
- Verifies archive integrity using `gzip -t`.
- Enforces strict file permissions (`umask 077` and `chmod 600`) so archives are only readable by the owner.
- Never prints or exposes database credentials in stdout or stderr.
- Enforces an automated 7-day retention policy (`-maxdepth 1`), safely pruning older archives.
- **Off-Server Cloud Storage Replication**: If `S3_BACKUP_BUCKET` is configured in the environment (e.g. `s3://fridgechef-backups/staging/`), the script automatically syncs the verified archive to cloud storage via `aws s3 cp` (or `rclone`), providing off-site disaster recovery.

```bash
# Run manual backup (local only):
bash scripts/db_backup.sh

# Run backup with off-server S3 sync:
S3_BACKUP_BUCKET="s3://fridgechef-backups/staging/" bash scripts/db_backup.sh

# Output archive format:
# backups/fridgechef_backup_YYYYMMDD_HHMMSSZ.sql.gz
```

#### Automated Daily Backup Cron Job
Add the following entry to the host server's crontab (`crontab -e`) to run backups daily at 02:00 UTC:

```cron
0 2 * * * cd /opt/fridgechef && S3_BACKUP_BUCKET="s3://my-backup-bucket/staging/" bash scripts/db_backup.sh >> /var/log/fridgechef_backup.log 2>&1
```

### 5.2 Backup and Restore Safety Test Suite (`scripts/test_backup_restore_safety.sh`)

To prove backup and disaster recovery reliability, the repository provides an automated safety rehearsal suite:

```bash
bash scripts/test_backup_restore_safety.sh
```

This script verifies:
1. Rejection when target database is omitted (Usage check).
2. Production overwrite safeguard aborts without `--force-production-overwrite`.
3. Non-existent backup archive error handling.
4. Truncated or corrupted gzip archive detection (`gzip -t` pre-check).
5. Strict `0600` permissions and `umask 077` enforcement.
6. Zero database password leakage in execution logs or CLI arguments.
7. Successful restoration and schema/catalogue count verification in an isolated test database.

### 5.3 Database Restoration Procedure (`scripts/db_restore.sh`)

The repository includes a hardened database restore utility with built-in disaster recovery safeguards:
- **Integrity Pre-Check**: Validates archive existence and gzip integrity (`gzip -t`) *before* connecting to PostgreSQL.
- **Explicit Target Requirement**: Both the backup archive and target database must be explicitly specified (no implicit defaults).
- **Production Overwrite Safeguard**: Restoring into the primary production database (`fridgechef`) is strictly forbidden unless the `--force-production-overwrite` flag is explicitly provided.
- **Transactional Rollback**: Uses `psql -v ON_ERROR_STOP=1 --single-transaction` to ensure any SQL error immediately rolls back the restore.
- **Post-Restore Integrity Verification**: Automatically queries and verifies restored table counts (16) and catalogue records (229 ingredients, 153 recipes, 702 shelf-life rules).

```bash
# 1. Safely verify backup in an isolated test database (RECOMMENDED):
bash scripts/db_restore.sh backups/fridgechef_backup_YYYYMMDD_HHMMSSZ.sql.gz fridgechef_restore_test

# 2. Disaster recovery restoration to production database (requires explicit force flag):
bash scripts/db_restore.sh backups/fridgechef_backup_YYYYMMDD_HHMMSSZ.sql.gz fridgechef --force-production-overwrite
```

---

## 6. Monitoring, Logging, and Operational Visibility

### 6.1 Health & Readiness Probes

The API exposes a comprehensive health probe at `GET /api/health`:

```bash
curl -i http://localhost/api/health
```

**Response (HTTP 200 OK)**:
```json
{
  "status": "healthy",
  "environment": "production",
  "timestamp": "2026-11-02T12:46:50.123456"
}
```
- Includes `X-Request-ID` in headers for distributed request tracing.
- Returns HTTP 503 if PostgreSQL connectivity fails.

### 6.2 Structured JSON Logging

All API requests and internal events are logged in structured JSON to `stdout`:
```json
{
  "timestamp": "2026-11-02T12:46:50.789Z",
  "level": "INFO",
  "logger": "app.core.middleware",
  "request_id": "9cf7b02c-473d-4c3e-953a-c1860081d520",
  "method": "POST",
  "path": "/api/v1/auth/login",
  "status_code": 200,
  "duration_ms": 42.15,
  "client_ip": "172.28.0.1",
  "user_id": "e4b9...c31d"
}
```
- Passwords, bearer tokens, full image bytes, and full email addresses are **never logged**.
- Email addresses are masked (e.g. `u***@example.com`).

### 6.3 Container Log Rotation

Docker logging is configured in `docker-compose.yml` for all containers to prevent host disk exhaustion:
```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```
Logs are capped at 30MB total per container.

### 6.4 Key Operational Alerts

Configure monitoring agents (Datadog / Prometheus / CloudWatch) to trigger on:
1. **5xx Error Rate > 1%** over 5 minutes.
2. **P95 Latency > 500ms** on `/api/v1/recommendations` or `/api/v1/meal-plans`.
3. **Container Restarts > 2** in 1 hour.
4. **Host Disk Usage > 85%** on `/var/lib/docker/volumes`.
5. **Database Connection Pool Exhaustion** (`QueuePool limit of size 5 overflow 10 reached`).

### 6.5 Automated Operational Health Monitor (`scripts/monitor_staging.sh`)

The repository provides a standalone operational health monitoring script that continuously validates the running deployment:

```bash
bash scripts/monitor_staging.sh
```

**Health Checks Executed**:
- **API Health Endpoint**: Validates `GET /api/health` returns HTTP 200 with latency < 500ms.
- **Frontend App Shell**: Validates `GET /` returns HTTP 200 with HTML document.
- **PostgreSQL Database Connectivity**: Validates `SELECT 1` via `pg_isready` and container query.
- **Docker Container Health**: Inspects all compose containers (`fridgechef-db`, `fridgechef-api`, `fridgechef-web`), verifying `healthy` status and alerting if restart count > 2.
- **Host Disk Space**: Alerts if filesystem utilization exceeds 85%.
- **Database Backup Freshness & Integrity**: Checks for backups created within the last 24 hours and validates archive integrity via `gzip -t`.
- **SSL/TLS Certificate Expiration**: Inspects certificates in `/etc/letsencrypt/` or `/etc/nginx/ssl/` and warns if expiring within 30 days.

**Cron Setup for Continuous Staging Monitoring**:
Add to host crontab to run health monitoring every 5 minutes:
```cron
*/5 * * * * cd /opt/fridgechef && bash scripts/monitor_staging.sh >> /var/log/fridgechef_monitor.log 2>&1
```

---

## 7. Operational Limitations & Scaling Constraints

### 7.1 Single-Worker Rate Limiting Architecture

The current rate limiter (`api/app/core/ratelimit.py`) implements an **in-process token bucket** stored in Python process memory.
- **Current Constraint**: To guarantee strict adherence to PRD rate limits (60 req/min general, 10 req/min recommendations, 5 req/min auth), the API must run with **1 Gunicorn worker** per container (`GUNICORN_WORKERS=1`).
- **Multi-Worker Implication**: If `GUNICORN_WORKERS` is increased without a distributed store, each worker maintains an independent bucket, multiplying the effective allowance by the number of workers.
- **Horizontal Scaling Prerequisite**: Before scaling the API across multiple workers or multiple container replicas, implement a Redis-backed distributed rate limiter using Redis Lua scripts.

---

## 8. Step-by-Step Production Deployment Workflow

### Step 1: Pre-Deployment Verification
On the deployment machine or CI runner, verify repository health:
```bash
# Verify backend unit & contract tests
cd api && poetry run pytest --ignore=tests/load

# Verify frontend build & typecheck
cd ../web && npm run typecheck && npm run build
```

### Step 2: Environment Configuration
```bash
# Copy and edit production environment
cp .env.example .env
chmod 600 .env

# Populate required secrets:
# JWT_SECRET=<openssl rand -hex 32>
# POSTGRES_PASSWORD=<openssl rand -base64 24>
# GROQ_API_KEY=<your-production-groq-key>
# APP_ENV=production
# CORS_ORIGINS=https://app.fridgechef.com
```

### Step 3: Build Production Docker Images
```bash
# Build web and api images without cache
docker compose build --no-cache
```

### Step 4: Launch Application Stack
```bash
# Launch containers in detached mode
docker compose up -d

# Verify container health
docker compose ps
```

### Step 5: Smoke Testing Staging / Production
Execute the automated 14-step validation suite to verify the deployment:
```bash
python3 scripts/validate_staging_deployment.py
```
Expected output:
```
============================================================
 ALL 14 STAGING FUNCTIONAL JOURNEY CHECKS PASSED!
============================================================
```

### Step 6: Emergency Rollback Procedure
If a critical failure occurs post-deployment:
1. Revert to previous Docker image tags:
   ```bash
   docker tag fridgechef-api:previous fridgechef-api:latest
   docker tag fridgechef-web:previous fridgechef-web:latest
   docker compose up -d --no-build
   ```
2. Roll back database schema if required:
   ```bash
   docker compose exec api poetry run alembic downgrade -1
   ```
3. If database data was corrupted, restore from the latest verified backup:
   ```bash
   bash scripts/db_restore.sh backups/fridgechef_backup_YYYYMMDD_HHMMSSZ.sql.gz fridgechef
   ```

---

## 9. Dedicated Staging Deployment Workflow

Follow these steps to deploy and operate the isolated Staging environment:

### Step 1: Configure Staging Environment Variables
```bash
cp .env.staging.example .env.staging
chmod 600 .env.staging

# Edit .env.staging:
# - Set DOMAIN=staging.fridgechef.com
# - Set CORS_ORIGINS=https://staging.fridgechef.com
# - Generate secure JWT_SECRET and POSTGRES_PASSWORD
# - Provide valid GROQ_API_KEY
```

### Step 2: Provision Staging SSL/TLS Certificates
```bash
# Obtain real Let's Encrypt certificate:
bash scripts/setup_staging_ssl.sh staging.fridgechef.com ops@fridgechef.com

# Or generate self-signed cert for offline/isolated rehearsal:
bash scripts/setup_staging_ssl.sh staging.fridgechef.com selfsigned
```

### Step 3: Launch Staging Docker Stack
```bash
# Build and launch using staging compose specification
docker compose -f docker-compose.staging.yml --env-file .env.staging up -d --build

# Confirm containers are running and healthy
docker compose -f docker-compose.staging.yml ps
```

### Step 4: Run Operational Health Verification & Smoke Tests
```bash
# 1. Run operational monitor check:
bash scripts/monitor_staging.sh

# 2. Run automated 14-journey validation suite:
python3 scripts/validate_staging_deployment.py
```

### Step 5: Test Backup & Disaster Recovery Rehearsal
```bash
# Run backup with S3 off-server sync:
S3_BACKUP_BUCKET="s3://fridgechef-staging-backups/" bash scripts/db_backup.sh

# Run full safety test suite:
bash scripts/test_backup_restore_safety.sh
```

---

## 10. External Infrastructure Setup Checklist (Handoff Runbook)

Use this checklist during staging infrastructure provisioning and public cutover.

### 10.1 Checklist Overview

- [ ] **1. Server Provisioning**:
  - Operating System: Ubuntu 22.04 LTS, Debian 12, or AlmaLinux 9.
  - Sizing: Minimum 2 vCPUs, 4 GB RAM, 40 GB NVMe SSD.
  - Runtimes: Docker Engine 26.0+ and Docker Compose v2.24+ installed.
  - Firewall: Ports 80 and 443 open to the public internet; port 22 restricted to administrative bastion or VPN IPs.
- [ ] **2. Domain & DNS Configuration**:
  - Create a DNS `A` record pointing `staging.fridgechef.com` to the server's public IPv4 address.
  - Verify global propagation: `dig +short staging.fridgechef.com` or `host staging.fridgechef.com`.
- [ ] **3. Environment Secret Generation**:
  - Generate JWT secret: `JWT_SECRET=$(openssl rand -hex 32)`.
  - Generate database password: `POSTGRES_PASSWORD=$(openssl rand -base64 24)`.
  - Populate `.env.staging` from `.env.staging.example` and set permissions: `chmod 600 .env.staging`.
- [ ] **4. Groq Vision & LLM API Configuration**:
  - Obtain an official Groq API key with funded tier quota.
  - Set `GROQ_API_KEY=gsk_...` in `.env.staging`.
- [ ] **5. Cloud Object Storage (S3) & IAM Configuration**:
  - Create a dedicated private S3 bucket (e.g. `s3://fridgechef-staging-backups/`).
  - Enable Default Encryption: Server-Side Encryption with Amazon S3 managed keys (SSE-S3 / AES256).
  - Configure Lifecycle Rules: Transition to Standard-IA after 30 days; expire/delete after 90 days.
  - Attach an IAM role or credentials with the following minimal policy:
    ```json
    {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Effect": "Allow",
          "Action": ["s3:PutObject", "s3:AbortMultipartUpload"],
          "Resource": "arn:aws:s3:::fridgechef-staging-backups/*"
        },
        {
          "Effect": "Allow",
          "Action": ["s3:ListBucket"],
          "Resource": "arn:aws:s3:::fridgechef-staging-backups"
        }
      ]
    }
    ```
- [ ] **6. TLS Certificate Provisioning**:
  - Execute automated Let's Encrypt Certbot challenge:
    ```bash
    bash scripts/setup_staging_ssl.sh staging.fridgechef.com ops@fridgechef.com
    ```
  - Verify certificate files exist in `certs/` with correct permissions (`0600 privkey.pem`, `0644 fullchain.pem`).
  - Configure renewal cron job:
    ```cron
    0 3 * * * certbot renew --webroot -w /opt/fridgechef/certbot-webroot --post-hook "docker compose -f /opt/fridgechef/docker-compose.staging.yml exec web nginx -s reload" >> /var/log/certbot_renew.log 2>&1
    ```
- [ ] **7. Application Launch**:
  - Build and launch the staging stack:
    ```bash
    docker compose -f docker-compose.staging.yml --env-file .env.staging up -d --build
    ```
- [ ] **8. Automated Backup & Monitoring Cron Jobs**:
  - Add to host server crontab (`crontab -e`):
    ```cron
    # Daily database backup with off-server S3 sync at 02:00 UTC
    0 2 * * * cd /opt/fridgechef && S3_BACKUP_BUCKET="s3://fridgechef-staging-backups" bash scripts/db_backup.sh >> /var/log/fridgechef_backup.log 2>&1

    # Continuous health monitor every 5 minutes
    */5 * * * * cd /opt/fridgechef && bash scripts/monitor_staging.sh >> /var/log/fridgechef_monitor.log 2>&1
    ```
- [ ] **9. HTTPS Functional Validation**:
  - Run the full 14-journey validation suite over genuine HTTPS:
    ```bash
    STAGING_BASE_URL="https://staging.fridgechef.com" python3 scripts/validate_staging_deployment.py
    ```
- [ ] **10. Disaster Recovery Restore Rehearsal**:
  - Verify backup recovery against an isolated verification database:
    ```bash
    bash scripts/db_restore.sh backups/fridgechef_staging_backup_latest.sql.gz fridgechef_staging_restore_test
    ```
- [ ] **11. Host Disk Capacity Monitoring**:
  - Monitor host filesystem utilization (warning at 85%, critical alert at 90%).
  - Ensure safe Docker maintenance: `docker image prune -f` and log retention (`10m`, 3 files).

