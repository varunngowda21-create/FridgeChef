#!/usr/bin/env bash
# ==============================================================================
# FridgeChef AI — Staging Health & Operational Monitor
# Checks API, Frontend, Database, Containers, Disk, Backups, and TLS Certificate.
# ==============================================================================
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BASE_URL="${1:-http://127.0.0.1:80}"
WARNINGS=0
ERRORS=0

echo "=========================================================="
echo " FridgeChef AI — Staging Operational Health Monitor"
echo " Target URL: ${BASE_URL}"
echo " Timestamp:  $(date -u +"%Y-%m-%d %H:%M:%SZ")"
echo "=========================================================="

report_ok() {
    echo "  [OK] $1"
}

report_warn() {
    WARNINGS=$((WARNINGS + 1))
    echo "  [WARN] $1"
}

report_err() {
    ERRORS=$((ERRORS + 1))
    echo "  [CRITICAL] $1"
}

# 1. API Health Check & Latency (Polls up to 10 seconds for container readiness)
echo -e "\n[1/7] Probing API Health Endpoint (/api/health)..."
api_healthy=false
http_response=""
for attempt in $(seq 1 10); do
    http_response=$(curl -s -w "\n%{http_code}\n%{time_total}" -m 5 "${BASE_URL}/api/health" 2>/dev/null || echo "FAILED")
    if echo "${http_response}" | grep -q "healthy"; then
        api_healthy=true
        break
    fi
    sleep 1
done

if [ "${api_healthy}" = true ]; then
    status_code=$(echo "${http_response}" | tail -n 2 | head -n 1)
    total_time=$(echo "${http_response}" | tail -n 1)
    report_ok "API is healthy (HTTP ${status_code}, response time: ${total_time}s)"
else
    report_err "API health check failed or timed out after 10s: ${http_response}"
fi

# 2. Frontend App Shell Check
echo -e "\n[2/7] Probing Frontend App Shell (/)..."
frontend_response=$(curl -s -w "\n%{http_code}" -m 10 "${BASE_URL}/" 2>/dev/null || echo "FAILED")
status_code=$(echo "${frontend_response}" | tail -n 1)
if [ "${status_code}" = "200" ] && echo "${frontend_response}" | grep -q 'id="root"'; then
    report_ok "Frontend SPA app shell loaded successfully (HTTP 200, root container present)"
else
    report_err "Frontend app shell failed (Status: ${status_code})"
fi

# 3. Database Connectivity Check
echo -e "\n[3/7] Probing PostgreSQL Database Connectivity..."
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.staging.yml"
if [ ! -f "${COMPOSE_FILE}" ] || ! docker compose -f "${COMPOSE_FILE}" ps db 2>/dev/null | grep -q "Up"; then
    COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.yml"
fi

if docker compose -f "${COMPOSE_FILE}" ps db 2>/dev/null | grep -q "Up"; then
    db_user="${POSTGRES_USER:-postgres}"
    db_name="${POSTGRES_DB:-fridgechef}"
    db_status=$(docker compose -f "${COMPOSE_FILE}" exec -T db pg_isready -U "${db_user}" -d "${db_name}" 2>&1 || echo "ERROR")
    if echo "${db_status}" | grep -q "accepting connections"; then
        report_ok "PostgreSQL container is running and accepting connections in $(basename "${COMPOSE_FILE}")"
    else
        report_err "PostgreSQL is not accepting connections: ${db_status}"
    fi
else
    report_err "PostgreSQL database container is NOT running (checked $(basename "${COMPOSE_FILE}"))"
fi

# 4. Container Status & Restart Health
echo -e "\n[4/7] Inspecting Container Lifecycle & Restarts..."
if command -v docker &>/dev/null; then
    containers=$(docker ps -a --filter "name=fridgechef" --format "{{.Names}}: {{.Status}}" 2>/dev/null || true)
    if [ -n "${containers}" ]; then
        while IFS= read -r line; do
            [ -z "${line}" ] && continue
            if echo "${line}" | grep -qiE "restarting|dead|exited"; then
                report_err "Container abnormal state: ${line}"
            else
                report_ok "Container healthy: ${line}"
            fi
        done <<< "${containers}"
    else
        report_err "No fridgechef containers detected on host"
    fi
else
    report_err "Docker binary not found on PATH"
fi

# 5. Disk & Storage Capacity
echo -e "\n[5/7] Checking Host Disk & Storage Capacity..."
DISK_WARN_THRESHOLD="${DISK_WARN_THRESHOLD:-85}"
DISK_CRIT_THRESHOLD="${DISK_CRIT_THRESHOLD:-95}"
disk_usage=$(df -h "${PROJECT_ROOT}" | awk 'NR==2 {print $5}' | tr -d '%')
if [ -n "${disk_usage}" ]; then
    if [ "${disk_usage}" -ge "${DISK_CRIT_THRESHOLD}" ]; then
        report_err "Disk usage is critically high: ${disk_usage}% on ${PROJECT_ROOT} (threshold: ${DISK_CRIT_THRESHOLD}%)"
    elif [ "${disk_usage}" -ge "${DISK_WARN_THRESHOLD}" ]; then
        report_warn "Disk usage is elevated: ${disk_usage}% on ${PROJECT_ROOT} (warning threshold: ${DISK_WARN_THRESHOLD}%)"
    else
        report_ok "Disk capacity normal (${disk_usage}% used on host partition)"
    fi
fi

# 6. Backup Freshness & Integrity Check
echo -e "\n[6/7] Checking Backup Freshness & Integrity..."
backup_dir="${PROJECT_ROOT}/backups"
if [ -d "${backup_dir}" ]; then
    latest_backup=$(ls -t "${backup_dir}"/fridgechef_backup_*.sql.gz 2>/dev/null | head -n 1)
    if [ -n "${latest_backup}" ] && [ -f "${latest_backup}" ]; then
        # Check archive age (< 26 hours)
        file_mod_time=$(stat -c %Y "${latest_backup}" 2>/dev/null || stat -f %m "${latest_backup}" 2>/dev/null || echo 0)
        current_time=$(date +%s)
        age_hours=$(( (current_time - file_mod_time) / 3600 ))
        
        # Verify gzip integrity
        if gzip -t "${latest_backup}" 2>/dev/null; then
            if [ "${age_hours}" -le 26 ]; then
                report_ok "Latest backup is fresh (${age_hours}h old, integrity verified): $(basename "${latest_backup}")"
            else
                report_warn "Latest backup is older than 26 hours (${age_hours}h old): $(basename "${latest_backup}")"
            fi
        else
            report_err "Latest backup archive is CORRUPTED: $(basename "${latest_backup}")"
        fi
    else
        report_warn "No database backup archives found in ${backup_dir}"
    fi
else
    report_warn "Backup directory ${backup_dir} does not exist"
fi

# 7. TLS Certificate Expiry Check
echo -e "\n[7/7] Checking TLS / SSL Certificate Expiration..."
cert_file="${PROJECT_ROOT}/certs/fullchain.pem"
if [ -f "${cert_file}" ]; then
    expiry_date=$(openssl x509 -enddate -noout -in "${cert_file}" 2>/dev/null | cut -d= -f2)
    if [ -n "${expiry_date}" ]; then
        expiry_epoch=$(date -d "${expiry_date}" +%s 2>/dev/null || date -j -f "%b %d %T %Y %Z" "${expiry_date}" +%s 2>/dev/null || echo 0)
        now_epoch=$(date +%s)
        days_remaining=$(( (expiry_epoch - now_epoch) / 86400 ))
        
        if [ "${days_remaining}" -lt 7 ]; then
            report_err "TLS certificate expires critically soon (${days_remaining} days remaining: ${expiry_date})"
        elif [ "${days_remaining}" -lt 14 ]; then
            report_warn "TLS certificate expires soon (${days_remaining} days remaining: ${expiry_date})"
        else
            report_ok "TLS certificate valid (${days_remaining} days remaining until ${expiry_date})"
        fi
    fi
else
    report_warn "TLS certificate fullchain.pem not found in ${PROJECT_ROOT}/certs (required if terminating TLS directly on Nginx host)"
fi

echo "=========================================================="
echo " Monitor Summary: ${ERRORS} Errors, ${WARNINGS} Warnings"
echo "=========================================================="

if [ "${ERRORS}" -gt 0 ]; then
    echo "STATUS: CRITICAL — Service requires immediate operator intervention."
    exit 1
elif [ "${WARNINGS}" -gt 0 ]; then
    echo "STATUS: DEGRADED — Service operational with warnings."
    exit 0
else
    echo "STATUS: HEALTHY — All operational health metrics optimal."
    exit 0
fi
