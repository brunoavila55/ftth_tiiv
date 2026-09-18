#!/usr/bin/env bash
# ==============================================================================
# FTTH Manager — Script Operacional de Backup Consistente
# ==============================================================================
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_COUNT="${RETENTION_COUNT:-7}"

mkdir -p "${BACKUP_DIR}"

echo "========================================================"
echo " [FTTH Manager] Executando Backup Consistente (DB + Anexos)"
echo "========================================================"

# Executa o utilitário Python do backend
if command -v uv >/dev/null 2>&1; then
    uv run --directory backend python scripts/backup.py --target-dir "${BACKUP_DIR}" --retention-count "${RETENTION_COUNT}" "$@"
else
    python backend/scripts/backup.py --target-dir "${BACKUP_DIR}" --retention-count "${RETENTION_COUNT}" "$@"
fi

echo "Backup concluído com sucesso."
