#!/usr/bin/env bash
# ==============================================================================
# FridgeChef AI — Staging TLS / SSL Certificate Provisioning Script
# PRD Reference: Section 12.5, Section 15.1, Section 15.3
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CERTS_DIR="${PROJECT_ROOT}/certs"
WEBROOT_DIR="${PROJECT_ROOT}/certbot-webroot"
DOMAIN="${1:-staging.fridgechef.com}"
SECOND_ARG="${2:-admin@fridgechef.com}"

# Determine operational mode: 'selfsigned' or standard ACME certificate issuance
IS_SELFSIGNED_REQUEST=false
if [ "${SECOND_ARG}" = "selfsigned" ] || [ "${SECOND_ARG}" = "--self-signed" ] || [ "${ALLOW_SELF_SIGNED:-false}" = "true" ]; then
    IS_SELFSIGNED_REQUEST=true
    EMAIL="admin@fridgechef.com"
else
    EMAIL="${SECOND_ARG}"
fi

echo "=========================================================="
echo " FridgeChef AI — Staging TLS Certificate Setup"
echo " Target Domain: ${DOMAIN}"
echo " Mode:          $(if [ "${IS_SELFSIGNED_REQUEST}" = true ]; then echo "Local Testing Self-Signed"; else echo "Public Let's Encrypt / ACME"; fi)"
if [ "${IS_SELFSIGNED_REQUEST}" = false ]; then
    echo " Admin Email:   ${EMAIL}"
fi
echo " Certs Dir:     ${CERTS_DIR}"
echo " Webroot Dir:   ${WEBROOT_DIR}"
echo "=========================================================="

mkdir -p "${CERTS_DIR}"
chmod 700 "${CERTS_DIR}"
mkdir -p "${WEBROOT_DIR}"

if [ "${IS_SELFSIGNED_REQUEST}" = true ]; then
    echo "[Self-Signed Mode] Generating self-signed certificate strictly for local development/rehearsal..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "${CERTS_DIR}/privkey.pem" \
        -out "${CERTS_DIR}/fullchain.pem" \
        -subj "/C=US/ST=State/L=City/O=FridgeChef/OU=Staging/CN=${DOMAIN}"
    chmod 600 "${CERTS_DIR}/privkey.pem"
    chmod 644 "${CERTS_DIR}/fullchain.pem"
    echo "[SUCCESS] Self-signed certificate generated in ${CERTS_DIR}."
    echo "WARNING: Self-signed certificates are strictly prohibited for public staging deployments."
    exit 0
fi

# Public Let's Encrypt / Certbot Provisioning Flow
if ! command -v certbot &>/dev/null; then
    echo "ERROR: 'certbot' CLI is not installed on this host!" >&2
    echo "Public staging requires a valid TLS certificate from an authentic CA." >&2
    echo "Public staging refuses to silently fallback to a self-signed certificate." >&2
    echo "Install certbot (e.g. 'apt-get install certbot' or 'brew install certbot') or run with 'selfsigned' strictly for offline rehearsal." >&2
    exit 1
fi

echo "[ACME] Verifying DNS resolution for '${DOMAIN}'..."
if ! host "${DOMAIN}" &>/dev/null && ! ping -c 1 -W 2 "${DOMAIN}" &>/dev/null; then
    echo "ERROR: Domain '${DOMAIN}' does not resolve to an active IP address." >&2
    echo "Public staging refuses to silently generate a self-signed certificate when public TLS is requested." >&2
    echo "Action required: Configure public DNS A-record pointing '${DOMAIN}' to this host's IP address." >&2
    echo "For offline rehearsal only, re-run with: bash scripts/setup_staging_ssl.sh ${DOMAIN} selfsigned" >&2
    exit 1
fi

echo "[ACME] Requesting Let's Encrypt certificate via HTTP-01 challenge..."
# If Nginx is running, use webroot mode; otherwise standalone mode
if docker ps --filter "name=fridgechef.*web" --format "{{.Status}}" 2>/dev/null | grep -qi "up"; then
    echo "Detected running Nginx web container; using ACME webroot challenge (-w ${WEBROOT_DIR})..."
    certbot certonly --webroot -w "${WEBROOT_DIR}" -d "${DOMAIN}" -m "${EMAIL}" --agree-tos --non-interactive
else
    echo "Nginx container not running on port 80; using standalone challenge..."
    certbot certonly --standalone -d "${DOMAIN}" -m "${EMAIL}" --agree-tos --non-interactive
fi

if [ -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]; then
    cp "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" "${CERTS_DIR}/fullchain.pem"
    cp "/etc/letsencrypt/live/${DOMAIN}/privkey.pem" "${CERTS_DIR}/privkey.pem"
    chmod 600 "${CERTS_DIR}/privkey.pem"
    chmod 644 "${CERTS_DIR}/fullchain.pem"
    echo "[SUCCESS] Valid Let's Encrypt certificate installed into ${CERTS_DIR}."
    
    # Reload Nginx if container is running
    if docker ps --filter "name=fridgechef.*web" --format "{{.Status}}" 2>/dev/null | grep -qi "up"; then
        echo "Reloading Nginx web container to apply new certificate..."
        docker compose -f "${PROJECT_ROOT}/docker-compose.staging.yml" exec web nginx -s reload 2>/dev/null || true
    fi
else
    echo "ERROR: Certbot completed but expected certificate files not found at /etc/letsencrypt/live/${DOMAIN}/" >&2
    exit 1
fi

echo "=========================================================="
echo " Public TLS Certificate Setup Complete!"
echo " Certificate: ${CERTS_DIR}/fullchain.pem"
echo " Private Key: ${CERTS_DIR}/privkey.pem"
echo ""
echo " NOTE: Certificate renewal is an external cron responsibility."
echo " Recommended Cron Setup for automated renewal:"
echo " 0 3 * * * certbot renew --webroot -w ${WEBROOT_DIR} --post-hook 'docker compose -f ${PROJECT_ROOT}/docker-compose.staging.yml exec web nginx -s reload' >> /var/log/certbot_renew.log 2>&1"
echo "=========================================================="

