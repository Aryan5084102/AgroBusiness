#!/usr/bin/env bash
# Restore an AgriFlow ERP backup into a (usually throwaway) database and verify.
# A backup is not trusted until this restore test passes.
#
# Usage:
#   TARGET_DATABASE_URL=postgresql://user:pass@host:5432/agriflow_restore \
#   ./scripts/restore_db.sh ./backups/agriflow-20260101T000000Z.dump
set -euo pipefail

: "${TARGET_DATABASE_URL:?TARGET_DATABASE_URL is required}"
DUMP="${1:?path to .dump file required}"

if [[ "${DUMP}" == *.age ]]; then
  : "${BACKUP_AGE_IDENTITY:?BACKUP_AGE_IDENTITY (age private key file) required for encrypted backup}"
  echo "[restore] decrypting"
  DEC="${DUMP%.age}"
  age -d -i "${BACKUP_AGE_IDENTITY}" -o "${DEC}" "${DUMP}"
  DUMP="${DEC}"
fi

echo "[restore] restoring ${DUMP} -> ${TARGET_DATABASE_URL}"
pg_restore --clean --if-exists --no-owner --no-privileges \
  --dbname="${TARGET_DATABASE_URL}" "${DUMP}"

echo "[restore] verifying row counts on key tables"
psql "${TARGET_DATABASE_URL}" -c "SELECT 'organizations' AS t, count(*) FROM organizations
  UNION ALL SELECT 'sales_invoices', count(*) FROM sales_invoices
  UNION ALL SELECT 'stock_movements', count(*) FROM stock_movements;"

echo "[restore] OK — restore test passed"
