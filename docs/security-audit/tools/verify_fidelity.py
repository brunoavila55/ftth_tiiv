#!/usr/bin/env python3
"""Verificação de fidelidade: cada trecho citado em findings.json existe de fato em arquivo:linha.

Também varre os artefatos gerados em busca de segredos em claro (lista de literais conhecidos do projeto).
Uso: python docs/security-audit/tools/verify_fidelity.py   (exit 0 = 0 divergências)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from anchors import verify  # noqa: E402

ROOT = HERE.parent
def collect_known_secrets() -> list[str]:
    """Extrai do próprio projeto os defaults/segredos reais (sem repeti-los neste arquivo)."""
    repo = ROOT.parents[1]
    found: set[str] = set()

    def read(rel: str) -> list[str]:
        p = repo / rel
        return p.read_text(encoding="utf-8", errors="replace").splitlines() if p.exists() else []

    # (1) defaults de campos sensíveis em config.py (mesma linha ou linha seguinte `default="..."`)
    lines = read("backend/app/core/config.py")
    for i, ln in enumerate(lines):
        ctx = " ".join(lines[max(0, i - 2): i + 1])
        if re.search(r"(SECRET|TOKEN|PASSWORD|KEY)\w*\s*:", ctx):
            for m in re.finditer(r"""["']([^"'\s]{8,})["']""", ln):
                found.add(m.group(1))
    # (2) defaults `${VAR:-valor}` em compose/.env para variáveis sensíveis; (3) `NOME=valor` no .env.example
    for rel in ("compose.yaml", ".env.example", "frontend/.env.example"):
        for ln in read(rel):
            if re.search(r"(SECRET|PASSWORD|TOKEN|KEY)", ln):
                for m in re.finditer(r"(?:SECRET|PASSWORD|TOKEN|KEY)\w*:-([^}\s]{6,})}", ln):
                    found.add(m.group(1))
                m = re.match(r"^\s*[A-Z_]*(SECRET|PASSWORD|TOKEN|KEY)[A-Z_]*\s*=\s*(\S{8,})\s*$", ln)
                if m:
                    found.add(m.group(2))
    # (4) senhas em URLs de banco e em hash_password("...") nos scripts/seed
    for rel in ("compose.yaml", ".env.example", "backend/scripts/seed_demo.py", "backend/scripts/benchmark_endpoints.py",
                "backend/scripts/generate_synthetic_load.py", "backend/app/core/config.py"):
        for ln in read(rel):
            for m in re.finditer(r"://[^:/\s\"'${}]+:([^@\s/\"'${}]{6,})@", ln):
                found.add(m.group(1))
            for m in re.finditer(r"""hash_password\(\s*["']([^"']{6,})["']""", ln):
                found.add(m.group(1))
    return sorted(v for v in found if len(v) >= 6)


def main() -> int:
    doc = json.loads((ROOT / "findings.json").read_text(encoding="utf-8"))
    known = collect_known_secrets()
    bad: list[str] = []
    n_ev = 0
    for f in doc["findings"]:
        if not f["evidence"]:
            bad.append(f"{f['id']}: sem evidência arquivo:linha")
        for ev in f["evidence"]:
            n_ev += 1
            msg = verify(ev)
            if msg:
                bad.append(f"{f['id']}: {msg}")
    for s in doc["strengths"]:
        if not s["evidence"] and "command" not in s:
            bad.append(f"{s['id']}: ponto forte sem evidência")
        for ev in s["evidence"]:
            n_ev += 1
            msg = verify(ev)
            if msg:
                bad.append(f"{s['id']}: {msg}")
    # totais coerentes
    tot = doc["meta"]["totals"]
    if sum(tot["by_severity"].values()) != tot["findings"] != len(doc["findings"]):
        bad.append("totais por severidade não batem com a lista de achados")
    # segredos em claro nos artefatos (JSON, issues, relatório-fonte)
    for name in ("findings.json", "issues.md", "inventario-rotas.md", "README.md", "evidencias/medicoes.md"):
        p = ROOT / name
        if p.exists():
            txt = p.read_text(encoding="utf-8")
            for lit in known:
                if lit in txt:
                    bad.append(f"segredo em claro em {name}: {lit[:4]}…")
    for p in (ROOT / "tools").glob("*.py"):
        if p.name in ("verify_fidelity.py",):
            continue
        txt = p.read_text(encoding="utf-8")
        for lit in known:
            if lit in txt:
                bad.append(f"segredo em claro em tools/{p.name}: {lit[:4]}…")
    import shutil, subprocess
    pdf = ROOT / "relatorio-auditoria-seguranca.pdf"
    if pdf.exists() and shutil.which("pdftotext"):
        txt = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True).stdout
        for lit in known:
            if lit in txt:
                bad.append(f"segredo em claro no PDF: {lit[:4]}…")
    print(f"literais de segredo conhecidos verificados: {len(known)}")
    print(f"achados={len(doc['findings'])} pontos_fortes={len(doc['strengths'])} evidências verificadas={n_ev}")
    if bad:
        print(f"DIVERGÊNCIAS: {len(bad)}")
        for b in bad:
            print(" -", b)
        return 1
    print("DIVERGÊNCIAS: 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
