#!/usr/bin/env bash
# ==============================================================================
# FridgeChef AI — Production Database Restore & Verification Script
# PRD Reference: Section 15.1, Section 15.2 (Data Persistence & Recovery)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Load environment configuration if available (.env.staging or .env)
if [ -f "${PROJECT_ROOT}/.env.staging" ] && [ ! -f "${PROJECT_ROOT}/.env" ]; then
    # shellcheck disable=SC1091
    source "${PROJECT_ROOT}/.env.staging" 2>/dev/null || true
elif [ -f "${PROJECT_ROOT}/.env" ]; then
    # shellcheck disable=SC1091
    source "${PROJECT_ROOT}/.env" 2>/dev/null || true
fi

DB_USER="${POSTGRES_USER:-postgres}"
PRIMARY_DB="${POSTGRES_DB:-fridgechef}"

BACKUP_FILE="${1:-}"
TARGET_DB="${2:-}"
FORCE_FLAG="${3:-}"

if [ -z "${BACKUP_FILE}" ] || [ -z "${TARGET_DB}" ]; then
    echo "Usage: $0 <path_to_backup.sql.gz> <target_database> [--force-production-overwrite]"
    echo ""
    echo "ERROR: Target database must be explicitly specified (no implicit defaults allowed)!" >&2
    echo ""
    echo "Examples:"
    echo "  # Safely verify backup in an isolated test database (RECOMMENDED):"
    echo "  $0 backups/fridgechef_backup_20261102.sql.gz fridgechef_restore_test"
    echo ""
    echo "  # Disaster recovery restoration to production database:"
    echo "  $0 backups/fridgechef_backup_20261102.sql.gz fridgechef --force-production-overwrite"
    exit 1
fi

# Guard against accidental production database overwrite
if [ "${TARGET_DB}" = "${PRIMARY_DB}" ] || [ "${TARGET_DB}" = "fridgechef" ]; then
    if [ "${FORCE_FLAG}" != "--force-production-overwrite" ]; then
        echo "=========================================================="
        echo " DANGER: Target database '${TARGET_DB}' is the primary/production database!"
        echo " Restoration will drop and overwrite existing production tables and data!"
        echo " To proceed with disaster recovery, explicitly supply: --force-production-overwrite"
        echo "=========================================================="
        exit 1
    fi
fi

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "ERROR: Backup archive '${BACKUP_FILE}' does not exist!" >&2
    exit 1
fi

echo "[0/4] Checking backup archive integrity with gzip -t..."
if ! gzip -t "${BACKUP_FILE}"; then
    echo "ERROR: Backup archive '${BACKUP_FILE}' failed gzip integrity test (corrupted or truncated archive)!" >&2
    exit 1
fi
echo "Archive integrity verified."

echo "=========================================================="
echo " FridgeChef AI — Database Restoration & Verification"
echo " Archive:   ${BACKUP_FILE}"
echo " Target DB: ${TARGET_DB}"
echo " User:      ${DB_USER}"
echo "=========================================================="

# Check if database service is running in Docker Compose (staging or standard)
USE_DOCKER=false
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.staging.yml"
if [ ! -f "${COMPOSE_FILE}" ] || ! docker compose -f "${COMPOSE_FILE}" ps db 2>/dev/null | grep -q "Up"; then
    COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.yml"
fi

if docker compose -f "${COMPOSE_FILE}" ps db 2>/dev/null | grep -q "Up"; then
    USE_DOCKER=true
    echo "Connecting via Docker Compose container in $(basename "${COMPOSE_FILE}")..."
else
    echo "Connecting to host PostgreSQL directly..."
    export PGPASSWORD="${POSTGRES_PASSWORD:-postgres}"
fi

exec_psql_maintenance() {
    local sql_query="$1"
    if [ "${USE_DOCKER}" = true ]; then
        docker compose -f "${COMPOSE_FILE}" exec -T db \
            psql -U "${DB_USER}" -d postgres -c "${sql_query}"
    else
        psql -h "${POSTGRES_HOST:-localhost}" -p "${POSTGRES_PORT:-5432}" -U "${DB_USER}" -d postgres -c "${sql_query}"
    fi
}

exec_psql_target() {
    local sql_query="$1"
    if [ "${USE_DOCKER}" = true ]; then
        docker compose -f "${COMPOSE_FILE}" exec -T db \
            psql -U "${DB_USER}" -d "${TARGET_DB}" -t -A -c "${sql_query}"
    else
        psql -h "${POSTGRES_HOST:-localhost}" -p "${POSTGRES_PORT:-5432}" -U "${DB_USER}" -d "${TARGET_DB}" -t -A -c "${sql_query}"
    fi
}

echo "[1/4] Ensuring target database '${TARGET_DB}' exists..."
# Create database if it doesn't exist
exec_psql_maintenance "SELECT 1 FROM pg_database WHERE datname = '${TARGET_DB}';" | grep -q 1 || \
    exec_psql_maintenance "CREATE DATABASE \"${TARGET_DB}\";"

echo "[2/4] Restoring database schema and records from archive..."
if [ "${USE_DOCKER}" = true ]; then
    gzip -dc "${BACKUP_FILE}" | docker compose -f "${COMPOSE_FILE}" exec -T db \
        psql -U "${DB_USER}" -d "${TARGET_DB}" -v ON_ERROR_STOP=1 --quiet --single-transaction
else
    gzip -dc "${BACKUP_FILE}" | psql -h "${POSTGRES_HOST:-localhost}" -p "${POSTGRES_PORT:-5432}" \
        -U "${DB_USER}" -d "${TARGET_DB}" -v ON_ERROR_STOP=1 --quiet --single-transaction
fi

echo "[3/4] Verifying restored schema and data integrity..."
TABLE_COUNT="$(exec_psql_target "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';")"
echo "  • Restored Public Tables: ${TABLE_COUNT}"

if [ "${TABLE_COUNT}" -eq 0 ]; then
    echo "ERROR: Zero tables restored! Backup verification FAILED." >&2
    exit 1
fi

INGREDIENTS_COUNT="$(exec_psql_target "SELECT count(*) FROM ingredients;" 2>/dev/null || echo 0)"
RECIPES_COUNT="$(exec_psql_target "SELECT count(*) FROM recipes;" 2>/dev/null || echo 0)"
SHELF_LIFE_COUNT="$(exec_psql_target "SELECT count(*) FROM shelf_life;" 2>/dev/null || echo 0)"
USERS_COUNT="$(exec_psql_target "SELECT count(*) FROM users;" 2>/dev/null || echo 0)"

echo "  • Ingredients: ${INGREDIENTS_COUNT}"
echo "  • Recipes:     ${RECIPES_COUNT}"
echo "  • Shelf Life:  ${SHELF_LIFE_COUNT}"
echo "  • Users:       ${USERS_COUNT}"

if [ "${INGREDIENTS_COUNT}" -eq 0 ] || [ "${RECIPES_COUNT}" -eq 0 ] || [ "${SHELF_LIFE_COUNT}" -eq 0 ]; then
    echo "ERROR: Critical catalogue tables are empty! Verification FAILED." >&2
    exit 1
fi

echo "[4/4] Verification check PASSED!"
echo "=========================================================="
echo " Database restoration and integrity verification SUCCESSFUL!"
echo " Target database '${TARGET_DB}' is fully operational."
echo "=========================================================="

