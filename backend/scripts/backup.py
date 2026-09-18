"""CLI para execução de backup completo (Banco de Dados + Anexos + Manifesto) do FTTH Manager."""

from __future__ import annotations

import argparse
import sys

from app.core.backup_restore import create_backup, prune_old_backups


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Utilitário de backup consistente do FTTH Manager (Banco PostGIS + Anexos)."
    )
    parser.add_argument(
        "--target-dir",
        type=str,
        default="./backups",
        help="Diretório onde o arquivo de backup compactado será salvo (padrão: ./backups)",
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="URL de conexão ao banco de dados (padrão: DATABASE_URL do ambiente)",
    )
    parser.add_argument(
        "--storage-path",
        type=str,
        default=None,
        help="Caminho do diretório de anexos/fotos (padrão: STORAGE_PATH do ambiente)",
    )
    parser.add_argument(
        "--retention-count",
        type=int,
        default=7,
        help="Quantidade de backups recentes para reter (padrão: 7)",
    )

    args = parser.parse_args()

    try:
        print("Iniciando processo de backup consistente do FTTH Manager...")
        backup_file = create_backup(
            target_dir=args.target_dir,
            db_url=args.database_url,
            storage_path=args.storage_path,
        )
        print(f"SUCESSO: Backup criado em '{backup_file.resolve()}'")

        if args.retention_count > 0:
            removed = prune_old_backups(args.target_dir, keep_count=args.retention_count)
            if removed:
                print(f"Retenção: {len(removed)} backup(s) antigo(s) removido(s).")

        return 0
    except Exception as e:
        print(f"ERRO durante o backup: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
