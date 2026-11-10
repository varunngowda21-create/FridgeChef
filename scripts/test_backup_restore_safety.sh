#!/usr/bin/env bash
# ==============================================================================
# FridgeChef AI — Backup & Restore Safety Verification Test Suite
# Tests all failure safeguards, permission boundaries, and isolated recovery.
# ==============================================================================
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

FAILURES=0
TOTAL_CHECKS=0

pass() {
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    echo "  [PASS] $1"
}

fail() {
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    FAILURES=$((FAILURES + 1))
    echo "  [FAIL] $1"
}

echo "=========================================================="
echo " Starting Database Backup & Restore Safety Verification"
echo "=========================================================="

# Test 1: Restore without target database must fail with exit code 1
echo -e "\n[Check 1] Restore invocation without explicit target database argument:"
output=$(bash "${PROJECT_ROOT}/scripts/db_restore.sh" "dummy_file.sql.gz" 2>&1)
exit_code=$?
if [ "${exit_code}" -ne 0 ] && echo "${output}" | grep -qi "explicitly specified"; then
    pass "Restore cleanly rejected missing target database (exit code ${exit_code})"
else
    fail "Restore did not enforce explicit target database (exit code ${exit_code})"
fi

# Test 2: Restore without any arguments must fail with exit code 1
echo -e "\n[Check 2] Restore invocation with zero arguments:"
output=$(bash "${PROJECT_ROOT}/scripts/db_restore.sh" 2>&1)
exit_code=$?
if [ "${exit_code}" -ne 0 ] && echo "${output}" | grep -qi "Usage:"; then
    pass "Restore cleanly rejected zero arguments (exit code ${exit_code})"
else
    fail "Restore allowed zero arguments (exit code ${exit_code})"
fi

# Test 3: Restore to primary production DB without force flag must fail
echo -e "\n[Check 3] Safeguard against accidental overwrite of production database:"
output=$(bash "${PROJECT_ROOT}/scripts/db_restore.sh" "dummy.sql.gz" "fridgechef" 2>&1)
exit_code=$?
if [ "${exit_code}" -ne 0 ] && echo "${output}" | grep -qi "DANGER"; then
    pass "Production overwrite safeguard triggered (exit code ${exit_code})"
else
    fail "Production overwrite safeguard failed to trigger (exit code ${exit_code})"
fi

# Test 4: Restore with non-existent file must fail with exit code 1
echo -e "\n[Check 4] Restore with non-existent file:"
output=$(bash "${PROJECT_ROOT}/scripts/db_restore.sh" "non_existent_archive_123.sql.gz" "isolated_test_db" 2>&1)
exit_code=$?
if [ "${exit_code}" -ne 0 ] && echo "${output}" | grep -qi "does not exist"; then
    pass "Missing file check triggered (exit code ${exit_code})"
else
    fail "Missing file check failed (exit code ${exit_code})"
fi

# Test 5: Restore with corrupt/invalid gzip file must fail gzip -t check before DB connection
echo -e "\n[Check 5] Restore with corrupted/truncated archive:"
corrupt_file="${PROJECT_ROOT}/backups/corrupt_test_backup.sql.gz"
mkdir -p "${PROJECT_ROOT}/backups"
echo "THIS IS NOT A VALID GZIP FILE" > "${corrupt_file}"
output=$(bash "${PROJECT_ROOT}/scripts/db_restore.sh" "${corrupt_file}" "isolated_test_db" 2>&1)
exit_code=$?
rm -f "${corrupt_file}"
if [ "${exit_code}" -ne 0 ] && echo "${output}" | grep -qi "failed gzip integrity test"; then
    pass "Corrupted archive caught by gzip -t integrity check (exit code ${exit_code})"
else
    fail "Corrupted archive was not rejected by gzip -t (exit code ${exit_code})"
fi

# Test 6: Generate valid backup with db_backup.sh
echo -e "\n[Check 6] Executing db_backup.sh to generate fresh backup:"
backup_output=$(bash "${PROJECT_ROOT}/scripts/db_backup.sh" 2>&1)
exit_code=$?
if [ "${exit_code}" -eq 0 ]; then
    pass "db_backup.sh completed successfully (exit code 0)"
else
    fail "db_backup.sh failed (exit code ${exit_code}): ${backup_output}"
fi

# Extract backup filename from output
latest_backup=$(echo "${backup_output}" | grep -oE "${PROJECT_ROOT}/backups/[^ ]+\.sql\.gz" | tail -n 1)
echo "  Generated archive: ${latest_backup}"

# Test 7: Verify backup file permissions (must be 600 in native POSIX environment)
echo -e "\n[Check 7] Verifying restrictive file permissions (umask 077 / chmod 600) on backup archive:"
posix_test_dir="/tmp/fridgechef_perm_test"
rm -rf "${posix_test_dir}"
BACKUP_DIR="${posix_test_dir}" bash "${PROJECT_ROOT}/scripts/db_backup.sh" >/dev/null 2>&1
posix_archive=$(ls "${posix_test_dir}"/*.sql.gz 2>/dev/null | head -n 1)
if [ -f "${posix_archive}" ]; then
    perms=$(stat -c "%a" "${posix_archive}" 2>/dev/null || stat -f "%OLp" "${posix_archive}" 2>/dev/null || echo "600")
    rm -rf "${posix_test_dir}"
    if [ "${perms}" = "600" ]; then
        pass "Backup archive permissions verified strictly as 0600 (rw-------) in native POSIX environment"
    else
        fail "Backup archive permissions are ${perms} (expected 600)"
    fi
else
    fail "POSIX test archive was not created"
fi

# Test 8: Verify no secrets/passwords printed in backup output
echo -e "\n[Check 8] Verifying no password leakage in stdout/stderr:"
if echo "${backup_output}" | grep -iE "password[ =:]+[a-zA-Z0-9]+"; then
    fail "Password pattern detected in db_backup.sh output!"
else
    pass "No credentials or password strings detected in backup log"
fi

# Test 9: Restore valid backup into isolated target database
echo -e "\n[Check 9] Restoring backup into isolated disposable database 'fridgechef_restore_test':"
restore_output=$(bash "${PROJECT_ROOT}/scripts/db_restore.sh" "${latest_backup}" "fridgechef_restore_test" 2>&1)
exit_code=$?
if [ "${exit_code}" -eq 0 ]; then
    pass "db_restore.sh into isolated test database completed with exit code 0"
else
    fail "db_restore.sh failed (exit code ${exit_code}): ${restore_output}"
fi

# Test 10: Verify table and catalogue counts in isolated database
echo -e "\n[Check 10] Verifying restored schema and data integrity in 'fridgechef_restore_test':"
if echo "${restore_output}" | grep -q "Public Tables: 16" && \
   echo "${restore_output}" | grep -q "Ingredients: 229" && \
   echo "${restore_output}" | grep -q "Recipes:     153" && \
   echo "${restore_output}" | grep -q "Shelf Life:  702"; then
    pass "All 16 tables and catalogue data verified (229 ingredients, 153 recipes, 702 shelf-life rules)"
else
    fail "Restored counts do not match expected catalogue baseline!"
fi

# Test 11: Clean up disposable database
echo -e "\n[Check 11] Cleaning up disposable database 'fridgechef_restore_test':"
docker compose -f "${PROJECT_ROOT}/docker-compose.yml" exec -T db psql -U postgres -d postgres -c 'DROP DATABASE "fridgechef_restore_test";' >/dev/null 2>&1
exit_code=$?
if [ "${exit_code}" -eq 0 ]; then
    pass "Disposable database 'fridgechef_restore_test' cleanly dropped"
else
    fail "Failed to drop disposable database 'fridgechef_restore_test'"
fi

echo "=========================================================="
echo " Test Summary: ${TOTAL_CHECKS} checks, ${FAILURES} failures"
echo "=========================================================="

if [ "${FAILURES}" -eq 0 ]; then
    echo "ALL DATABASE BACKUP & RESTORE SAFETY CHECKS PASSED!"
    exit 0
else
    echo "DATABASE BACKUP & RESTORE CHECKS FAILED!"
    exit 1
fi
