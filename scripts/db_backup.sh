#!/usr/bin/env bash
# ==============================================================================
# FridgeChef AI — Production Database Backup Script
# S3 Replication & Security Requirements:
# - Target Bucket: Must have Server-Side Encryption enabled (e.g., SSE-S3 / AES256 or AWS KMS).
# - IAM Permissions: Minimal IAM policy requires `s3:PutObject` on `${S3_BACKUP_BUCKET}/*`
#   and `s3:ListBucket` on the root bucket.
# ==============================================================================
set -euo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-${PROJECT_ROOT}/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"

if [ -z "${BACKUP_DIR}" ] || [ "${BACKUP_DIR}" = "/" ]; then
    echo "ERROR: Invalid BACKUP_DIR specification: '${BACKUP_DIR}'" >&2
    exit 1
fi

# Load environment configuration if available (.env.staging or .env)
if [ -f "${PROJECT_ROOT}/.env.staging" ] && [ ! -f "${PROJECT_ROOT}/.env" ]; then
    # shellcheck disable=SC1091
    source "${PROJECT_ROOT}/.env.staging" 2>/dev/null || true
elif [ -f "${PROJECT_ROOT}/.env" ]; then
    # shellcheck disable=SC1091
    source "${PROJECT_ROOT}/.env" 2>/dev/null || true
fi

DB_USER="${POSTGRES_USER:-postgres}"
DB_NAME="${POSTGRES_DB:-fridgechef}"
TIMESTAMP="$(date -u +"%Y%m%d_%H%M%SZ")"
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_backup_${TIMESTAMP}.sql.gz"

echo "=========================================================="
echo " FridgeChef AI — Database Backup"
echo " Target DB:  ${DB_NAME}"
echo " User:       ${DB_USER}"
echo " Backup Dir: ${BACKUP_DIR}"
echo "=========================================================="

mkdir -p "${BACKUP_DIR}"
chmod 700 "${BACKUP_DIR}"

echo "[1/3] Generating pg_dump archive..."

# Prefer executing pg_dump via running Docker container (staging or standard compose)
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.staging.yml"
if [ ! -f "${COMPOSE_FILE}" ] || ! docker compose -f "${COMPOSE_FILE}" ps db 2>/dev/null | grep -q "Up"; then
    COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.yml"
fi

if docker compose -f "${COMPOSE_FILE}" ps db 2>/dev/null | grep -q "Up"; then
    echo "Using Docker Compose container in $(basename "${COMPOSE_FILE}")..."
    docker compose -f "${COMPOSE_FILE}" exec -T db \
        pg_dump -U "${DB_USER}" -d "${DB_NAME}" --clean --if-exists --no-owner --no-privileges \
        | gzip -c > "${BACKUP_FILE}"
else
    echo "Using host pg_dump directly..."
    export PGPASSWORD="${POSTGRES_PASSWORD:-postgres}"
    pg_dump -h "${POSTGRES_HOST:-localhost}" -p "${POSTGRES_PORT:-5432}" -U "${DB_USER}" -d "${DB_NAME}" \
        --clean --if-exists --no-owner --no-privileges \
        | gzip -c > "${BACKUP_FILE}"
fi

chmod 600 "${BACKUP_FILE}"

echo "[2/3] Verifying backup archive integrity..."
if [ ! -s "${BACKUP_FILE}" ]; then
    echo "ERROR: Backup file ${BACKUP_FILE} is empty or was not created!" >&2
    rm -f "${BACKUP_FILE}"
    exit 1
fi

# Verify gzip stream
gzip -t "${BACKUP_FILE}"
BACKUP_SIZE="$(du -h "${BACKUP_FILE}" | cut -f1)"
echo "Integrity verified! Archive size: ${BACKUP_SIZE} -> ${BACKUP_FILE}"

echo "[3/4] Pruning backups older than ${RETENTION_DAYS} days in ${BACKUP_DIR}..."
find "${BACKUP_DIR}" -maxdepth 1 -name "${DB_NAME}_backup_*.sql.gz" -type f -mtime +"${RETENTION_DAYS}" -delete || true

if [ -n "${S3_BACKUP_BUCKET:-}" ]; then
    echo "[4/4] Syncing backup archive to off-server storage (${S3_BACKUP_BUCKET})..."
    s3_synced=false
    if command -v aws &>/dev/null; then
        if aws s3 cp "${BACKUP_FILE}" "${S3_BACKUP_BUCKET}/$(basename "${BACKUP_FILE}")" --sse AES256 --only-show-errors; then
            s3_synced=true
            echo "Successfully uploaded backup archive to AWS S3: ${S3_BACKUP_BUCKET}"
        else
            echo "ERROR: Failed to upload backup archive to AWS S3 (${S3_BACKUP_BUCKET})!" >&2
        fi
    elif command -v rclone &>/dev/null; then
        if rclone copyto "${BACKUP_FILE}" "${S3_BACKUP_BUCKET}/$(basename "${BACKUP_FILE}")"; then
            s3_synced=true
            echo "Successfully synced backup archive via rclone to ${S3_BACKUP_BUCKET}"
        else
            echo "ERROR: Failed to sync backup archive to ${S3_BACKUP_BUCKET} via rclone!" >&2
        fi
    else
        echo "ERROR: S3_BACKUP_BUCKET is configured (${S3_BACKUP_BUCKET}), but neither 'aws' nor 'rclone' CLI is available on PATH!" >&2
    fi

    if [ "${s3_synced}" != true ]; then
        echo "=========================================================="
        echo " CRITICAL FAILURE: Off-server backup sync failed!"
        echo " Local backup succeeded at: ${BACKUP_FILE}"
        echo " Off-site disaster recovery was NOT achieved."
        echo "=========================================================="
        exit 2
    fi
else
    echo "[4/4] Off-server backup sync: NOT CONFIGURED (S3_BACKUP_BUCKET is unset)."
    echo "      NOTICE: Disaster recovery off-site replication is currently unavailable."
    echo "      Backup is stored locally in ${BACKUP_DIR}."
fi

echo "=========================================================="
echo " Database backup completed successfully!"
echo " Archive: ${BACKUP_FILE}"
if [ -n "${S3_BACKUP_BUCKET:-}" ]; then
    echo " Off-site: Synced to ${S3_BACKUP_BUCKET}"
fi
echo "=========================================================="

