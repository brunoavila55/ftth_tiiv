#!/usr/bin/env bash
# ==============================================================================
# FTTH Manager — Script Operacional de Restauração de Backup
# ==============================================================================
set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Uso: $0 <caminho-do-arquivo-backup.tar.gz> [opções]"
    exit 1
fi

ARCHIVE="$1"
shift

echo "========================================================"
echo " [FTTH Manager] Executando Restauração de Backup"
echo " Arquivo: ${ARCHIVE}"
echo "========================================================"

if command -v uv >/dev/null 2>&1; then
    uv run --directory backend python scripts/restore.py "${ARCHIVE}" "$@"
else
    python backend/scripts/restore.py "${ARCHIVE}" "$@"
fi

echo "Restauração finalizada."
