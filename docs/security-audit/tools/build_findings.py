#!/usr/bin/env python3
"""Resolve âncoras (arquivo:linha + trecho) e escreve docs/security-audit/findings.json (fonte única)."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import extras  # noqa: E402
import findings_est  # noqa: E402
import findings_perf  # noqa: E402
import findings_sec  # noqa: E402
from anchors import AnchorError, resolve  # noqa: E402

OUT = HERE.parent / "findings.json"
SEV_ORDER = ["crítica", "alta", "média", "baixa", "informativa"]
CAT = {"SEC": "Segurança", "EST": "Estrutura", "PERF": "Performance"}


def proof_kind(proof: str) -> str:
    p = proof.lower()
    if p.startswith("medido"):
        return "medido"
    if p.startswith("reproduzido"):
        return "reproduzido"
    return "leitura"


def main() -> int:
    findings, errors = [], []
    for src in (findings_sec, findings_est, findings_perf):
        for f in src.FINDINGS:
            try:
                ev = [resolve(e) for e in f["ev"]]
            except AnchorError as exc:
                errors.append(f"{f['id']}: {exc}")
                continue
            assert f["sev"] in SEV_ORDER, f
            item = {
                "id": f["id"], "category": f["id"].split("-")[0], "subcategory": f["sub"], "severity": f["sev"],
                "title": f["title"], "conditions": f["cond"], "description": f["desc"], "exploitability": f["why"],
                "impact": f["impact"], "fix": f["fix"], "validation": f["validate"], "acceptance": f["accept"],
                "evidence": ev, "proof": f["proof"], "proof_kind": proof_kind(f["proof"]),
                "effort": f["effort"], "gain": f["gain"], "wave": f["wave"],
            }
            for k in ("trigger", "growth", "rank"):
                if k in f:
                    item[k] = f[k]
            findings.append(item)
    strengths = []
    for s in extras.STRENGTHS:
        try:
            ev = [resolve(e) for e in s["ev"]]
        except AnchorError as exc:
            errors.append(f"{s['id']}: {exc}")
            continue
        d = {"id": s["id"], "title": s["title"], "description": s["desc"], "evidence": ev}
        if "cmd" in s:
            d["command"] = s["cmd"]
        strengths.append(d)
    if errors:
        print("ERROS DE ÂNCORA:\n  " + "\n  ".join(errors))
        return 1
    ids = [f["id"] for f in findings]
    assert len(ids) == len(set(ids)), "IDs duplicados"
    known = set(ids)
    for _, _, gids in extras.ISSUE_GROUPS:
        for g in gids:
            assert g in known, f"grupo referencia id inexistente {g}"
    grouped = [g for _, _, gids in extras.ISSUE_GROUPS for g in gids]
    missing = sorted(known - set(grouped))
    dup = [k for k, v in Counter(grouped).items() if v > 1]
    assert not dup, f"achado em mais de um grupo: {dup}"
    if missing:
        print("AVISO: achados sem issue:", missing)

    sev_count = Counter(f["severity"] for f in findings)
    cat_count = Counter(f["category"] for f in findings)
    doc = {
        "meta": {
            "project": extras.PROJECT, "audit_date": extras.AUDIT_DATE, "commit": extras.COMMIT,
            "scope": "backend/ (FastAPI, 110 handlers), frontend/ (Next.js), compose.yaml, Caddyfile, Dockerfiles, CI, migrations, scripts, docs, histórico git (8 commits)",
            "totals": {"findings": len(findings), "by_severity": {s: sev_count.get(s, 0) for s in SEV_ORDER},
                      "by_category": dict(cat_count), "strengths": len(strengths), "issues": len(extras.ISSUE_GROUPS)},
        },
        "method_note": extras.METHOD_NOTE,
        "findings": findings,
        "strengths": strengths,
        "not_applicable": [{"category": a, "reason": b} for a, b in extras.NOT_APPLICABLE],
        "architecture": {"components": extras.COMPONENTS, "edges": extras.EDGES, "hotspots": extras.HOTSPOTS},
        "issue_groups": [{"n": i, "title": t, "labels": l, "ids": ids_} for i, (t, l, ids_) in enumerate(extras.ISSUE_GROUPS, 1)],
        "waves": {str(k): {"title": v[0], "desc": v[1]} for k, v in extras.WAVES.items()},
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"OK findings.json: {len(findings)} achados {dict(sev_count)} {dict(cat_count)}; {len(strengths)} pontos fortes; {len(extras.ISSUE_GROUPS)} issues")
    return 0


if __name__ == "__main__":
    sys.exit(main())
