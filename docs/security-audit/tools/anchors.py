"""Resolução e verificação de âncoras arquivo:linha (usado por build_findings.py e verify_fidelity.py).

Uma âncora é E(file, needle, occ=None, span=1):
  - `needle` é uma substring que deve existir na linha citada;
  - `occ` escolhe a N-ésima linha (1-based) que contém `needle` quando há várias; se omitido, `needle` deve ser único;
  - `span` = nº de linhas consecutivas a exibir como trecho.
Segredos: literais de string em linhas que citam nomes sensíveis são mascarados (4 primeiros caracteres + "…").
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

SENSITIVE_LINE = re.compile(r"(secret|password|passwd|token|api[_-]?key|credential|AdminPass|hash_password)", re.I)
STRING_LITERAL = re.compile(r"""(["'])([^"'\n]{5,}?)\1""")
# valores após `:-`/`=` em atribuições de ambiente (compose/.env)
ENV_DEFAULT = re.compile(r"(:-|=)([A-Za-z0-9_\-!@#$%^&*.]{5,})(?=[}\s]|$)")


def mask_secrets(line: str) -> str:
    """Mascara valores potencialmente secretos: mantém 4 primeiros caracteres + '…'."""
    if not SENSITIVE_LINE.search(line):
        return line

    def _lit(m: re.Match[str]) -> str:
        q, body = m.group(1), m.group(2)
        # não mascara nomes de campo/config curtos ou textos descritivos
        if re.fullmatch(r"[A-Za-z_]+", body) and len(body) < 24:
            return m.group(0)
        if " " in body and len(body) > 30:
            return m.group(0)
        if re.fullmatch(r"[a-z0-9_\-/.:]+\s*", body) and ("_" not in body and "-" not in body):
            return m.group(0)
        return f"{q}{body[:4]}…{q}"

    out = STRING_LITERAL.sub(_lit, line)

    def _env(m: re.Match[str]) -> str:
        return f"{m.group(1)}{m.group(2)[:4]}…"

    if ("${" in line or re.match(r"\s*[A-Z_]+=", line)) and not out.count("…"):
        out = ENV_DEFAULT.sub(_env, out)
    return out


@dataclass(frozen=True)
class E:
    file: str
    needle: str
    occ: int | None = None
    span: int = 1
    note: str = ""


class AnchorError(Exception):
    pass


def _lines(file: str) -> list[str]:
    p = ROOT / file
    if not p.exists():
        raise AnchorError(f"arquivo inexistente: {file}")
    return p.read_text(encoding="utf-8", errors="replace").splitlines()


def resolve(e: E) -> dict:
    lines = _lines(e.file)
    hits = [i for i, ln in enumerate(lines, 1) if e.needle in ln]
    if not hits:
        raise AnchorError(f"needle não encontrado em {e.file}: {e.needle!r}")
    if e.occ is None:
        if len(hits) > 1:
            raise AnchorError(f"needle ambíguo em {e.file} (linhas {hits}): {e.needle!r} — informe occ=")
        start = hits[0]
    else:
        if e.occ > len(hits):
            raise AnchorError(f"occ={e.occ} > {len(hits)} em {e.file}: {e.needle!r}")
        start = hits[e.occ - 1]
    end = min(start + e.span - 1, len(lines))
    snippet = "\n".join(mask_secrets(lines[i - 1].rstrip()) for i in range(start, end + 1))
    return {
        "file": e.file,
        "line": start,
        "line_end": end,
        "needle": mask_secrets(e.needle),
        "snippet": snippet,
        "note": e.note,
    }


def verify(ev: dict) -> str | None:
    """Retorna None se ok; senão mensagem de divergência."""
    try:
        lines = _lines(ev["file"])
    except AnchorError as exc:
        return str(exc)
    a, b = ev["line"], ev["line_end"]
    if not (1 <= a <= b <= len(lines)):
        return f"{ev['file']}:{a}-{b} fora do arquivo ({len(lines)} linhas)"
    actual = "\n".join(mask_secrets(lines[i - 1].rstrip()) for i in range(a, b + 1))
    if actual != ev["snippet"]:
        return f"{ev['file']}:{a}-{b} trecho divergente.\n   esperado: {ev['snippet']!r}\n   real:     {actual!r}"
    # o needle (mascarado) deve aparecer na primeira linha do trecho
    first = mask_secrets(lines[a - 1].rstrip())
    if ev["needle"] not in first:
        return f"{ev['file']}:{a} needle {ev['needle']!r} ausente na linha"
    return None
