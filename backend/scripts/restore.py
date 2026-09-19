"""CLI para restauração de backup completo (Banco de Dados + Anexos) do FTTH Manager."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.core.backup_restore import restore_backup


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Utilitário de restauração de backup consistente do FTTH Manager."
    )
    parser.add_argument(
        "archive",
        type=str,
        help="Caminho do arquivo de backup .tar.gz a ser restaurado",
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="URL do banco de dados de destino (padrão: DATABASE_URL do ambiente)",
    )
    parser.add_argument(
        "--storage-path",
        type=str,
        default=None,
        help="Diretório de destino dos anexos/fotos (padrão: STORAGE_PATH do ambiente)",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Ignora a conferência dos hashes SHA256 (NÃO recomendado). A assinatura do manifesto é SEMPRE verificada.",
    )

    args = parser.parse_args()

    archive_path = Path(args.archive)
    if not archive_path.exists():
        print(f"ERRO: Arquivo de backup não encontrado: {archive_path}", file=sys.stderr)
        return 1

    try:
        print(f"Iniciando processo de restauração a partir de '{archive_path.name}'...")
        manifest = restore_backup(
            archive_path=archive_path,
            target_db_url=args.database_url,
            target_storage_path=args.storage_path,
            verify_checksums=not args.no_verify,
        )
        print("SUCESSO: Restauração concluída!")
        print(f"  Backup ID: {manifest.backup_id}")
        print(f"  Data original: {manifest.created_at}")
        print(f"  Schema: {manifest.schema_version}")
        print(f"  Topologia rev: #{manifest.topology_revision}")
        print(f"  Anexos restaurados: {manifest.attachments_count} arquivo(s)")
        return 0
    except Exception as e:
        print(f"ERRO durante a restauração: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
