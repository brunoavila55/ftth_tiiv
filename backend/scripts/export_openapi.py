#!/usr/bin/env python3
"""Exportador determinístico de schema OpenAPI para contracts/openapi.json."""

import json
import sys
from pathlib import Path

from app.main import create_app


def export_openapi() -> int:
    app = create_app()
    openapi_schema = app.openapi()

    # Caminho do contrato compartilhado na raiz do repositório
    backend_dir = Path(__file__).resolve().parent.parent
    repo_root = backend_dir.parent
    contracts_dir = repo_root / "contracts"
    contracts_dir.mkdir(parents=True, exist_ok=True)
    target_file = contracts_dir / "openapi.json"

    # Serialização determinística com indentação fixa e ordenação de chaves
    content = json.dumps(openapi_schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

    target_file.write_text(content, encoding="utf-8")

    paths_count = len(openapi_schema.get("paths", {}))
    schemas_count = len(openapi_schema.get("components", {}).get("schemas", {}))
    file_size_kb = round(len(content.encode("utf-8")) / 1024, 2)

    print(f"[+] Contrato OpenAPI exportado com sucesso para: {target_file}")
    print(f"[+] Rotas mapeadas (paths): {paths_count}")
    print(f"[+] Schemas definidos: {schemas_count}")
    print(f"[+] Tamanho do arquivo: {file_size_kb} KB")
    return 0


if __name__ == "__main__":
    sys.exit(export_openapi())
