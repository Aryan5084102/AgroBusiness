#!/usr/bin/env bash
# Automated PostgreSQL backup for AgriFlow ERP.
#
# Produces a compressed, timestamped dump and (optionally) encrypts it with
# age/gpg before upload to object storage. A backup is only considered valid
# once a restore test has succeeded (see restore_db.sh).
#
# Usage:
#   DATABASE_URL=postgresql://user:pass@host:5432/agriflow \
#   BACKUP_DIR=/var/backups/agriflow ./scripts/backup_db.sh
set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL is required}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${BACKUP_DIR}/agriflow-${STAMP}.dump"

mkdir -p "${BACKUP_DIR}"

echo "[backup] dumping to ${OUT}"
# Custom format (-Fc) supports parallel, selective restore.
pg_dump --format=custom --no-owner --no-privileges --file="${OUT}" "${DATABASE_URL}"

# Optional encryption at rest. Set BACKUP_AGE_RECIPIENT to an age public key.
if [[ -n "${BACKUP_AGE_RECIPIENT:-}" ]] && command -v age >/dev/null 2>&1; then
  echo "[backup] encrypting with age"
  age -r "${BACKUP_AGE_RECIPIENT}" -o "${OUT}.age" "${OUT}"
  rm -f "${OUT}"
  OUT="${OUT}.age"
fi

echo "[backup] wrote ${OUT} ($(du -h "${OUT}" | cut -f1))"

# Prune old local backups.
find "${BACKUP_DIR}" -name 'agriflow-*.dump*' -mtime "+${RETENTION_DAYS}" -delete || true

# Upload to object storage (S3-compatible) if configured.
if [[ -n "${BACKUP_S3_BUCKET:-}" ]] && command -v aws >/dev/null 2>&1; then
  echo "[backup] uploading to s3://${BACKUP_S3_BUCKET}/"
  aws s3 cp "${OUT}" "s3://${BACKUP_S3_BUCKET}/$(basename "${OUT}")"
fi

echo "[backup] done"
