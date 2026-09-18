# Auditoria de segurança, estrutura e performance — FTTH Manager

> **Confidencial.** Descreve vulnerabilidades reais. Sugestão (não aplicada): adicionar `docs/security-audit/` ao `.gitignore` ou manter este diretório fora de repositório público.

| Arquivo | Conteúdo |
|---|---|
| `relatorio-auditoria-seguranca.pdf` | Relatório (A4, pt-BR): resumo executivo, mapa do sistema, pontos fortes/fracos, achados, Top 10, matriz, ondas, issues |
| `issues.md` | Todas as issues em Markdown puro (colar no GitHub) |
| `findings.json` | **Fonte única** (achados, evidências arquivo:linha + trecho, pontos fortes, N/A, arquitetura, grupos de issues) |
| `inventario-rotas.md` | Inventário dos 110 handlers com vereditos C1/C2/C3 |
| `evidencias/` | `medicoes.md` (saídas literais), `routes.json`, `pip-audit-backend.json`, `pnpm-audit-frontend.json` |
| `tools/` | Geradores e verificadores (abaixo) |

## Regenerar tudo (venv fora do repositório)

```bash
export PYTHONDONTWRITEBYTECODE=1
PY=/tmp/audit-env/venv/bin/python      # reportlab, matplotlib (+ deps do backend p/ enum_routes/gen_inventory)
$PY docs/security-audit/tools/build_findings.py      # resolve âncoras → findings.json
$PY docs/security-audit/tools/verify_fidelity.py     # confere trecho × arquivo:linha e varre segredos (exit 0 = 0 divergências)
$PY docs/security-audit/tools/gen_inventory.py       # inventario-rotas.md (usa evidencias/routes.json)
$PY docs/security-audit/tools/generate_report.py     # issues.md + PDF
```

`tools/enum_routes.py` (introspecção do app) e `tools/measure*.py` (medições em Postgres **descartável** em `127.0.0.1:55432`) estão documentados em `evidencias/medicoes.md`.
Reprodução do ambiente descartável:

```bash
docker run -d --rm --name ftth-audit-pg -e POSTGRES_USER=… -e POSTGRES_PASSWORD=… -e POSTGRES_DB=audit -p 127.0.0.1:55432:5432 postgis/postgis:16-3.4
cd backend && DATABASE_URL=postgresql+psycopg://…@127.0.0.1:55432/audit alembic upgrade head
DATABASE_URL=… python scripts/generate_synthetic_load.py --db-url "$DATABASE_URL" --structures 10000
DATABASE_URL=… PYTHONPATH=backend python docs/security-audit/tools/measure.py   # e measure2..6
docker stop ftth-audit-pg
```
