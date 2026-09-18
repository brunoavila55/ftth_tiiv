#!/usr/bin/env python3
"""Regenera `issues.md` e `relatorio-auditoria-seguranca.pdf` a partir de `findings.json` (fonte única).

Requer (venv FORA do repositório): reportlab, matplotlib.
  /tmp/audit-env/venv/bin/python docs/security-audit/tools/generate_report.py
"""
from __future__ import annotations

import html
import json
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402,F401
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_CENTER  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    BaseDocTemplate, CondPageBreak, Frame, Image, KeepTogether, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TMP = Path("/tmp/audit-env/charts")
TMP.mkdir(parents=True, exist_ok=True)
DOC = json.loads((ROOT / "findings.json").read_text(encoding="utf-8"))
F = {f["id"]: f for f in DOC["findings"]}

REPORT_NAME = "Relatório de Auditoria de Segurança, Estrutura e Performance"
PROJECT = DOC["meta"]["project"]
SEV = ["crítica", "alta", "média", "baixa", "informativa"]
SEV_COLOR = {"crítica": "#B91C1C", "alta": "#EA580C", "média": "#D97706", "baixa": "#2563EB", "informativa": "#6B7280"}
OK_COLOR = "#059669"
CAT_NAME = {"SEC": "Segurança (SEC)", "EST": "Estrutura (EST)", "PERF": "Performance (PERF)"}
EFFORT = {1: "baixo", 2: "médio", 3: "alto"}
GAIN = {1: "baixo", 2: "médio", 3: "alto"}

# Agrupamento por subcategoria para o gráfico de barras (mapeia P1/P2/P3)
SUBGROUP = {
    "SEC": OrderedDict([
        ("AuthN/AuthZ e dados pessoais", ["SEC-01", "SEC-03", "SEC-04", "SEC-06", "SEC-07", "SEC-08", "SEC-13", "SEC-14"]),
        ("Segredos e configuração", ["SEC-02", "SEC-05", "SEC-12"]),
        ("Transporte, headers, CSRF", ["SEC-09", "SEC-11", "SEC-18"]),
        ("Integridade (backup/restore)", ["SEC-10"]),
        ("Dependências", ["SEC-15"]),
        ("Cadeias de exploração", ["SEC-16", "SEC-17"]),
    ]),
    "EST": OrderedDict([
        ("A Autorização/arquitetura", ["EST-02", "EST-20"]),
        ("B Camadas/acoplamento", ["EST-21"]),
        ("C Consistência de dados", ["EST-03", "EST-04", "EST-05", "EST-06", "EST-09", "EST-19"]),
        ("D Resiliência/escala", ["EST-01", "EST-07", "EST-14"]),
        ("E Abuso e limites", ["EST-11"]),
        ("F Plataforma/validação", ["EST-12"]),
        ("G Configuração/deploy", ["EST-08", "EST-15", "EST-16", "EST-17"]),
        ("H Observabilidade", ["EST-10", "EST-13", "EST-18"]),
    ]),
    "PERF": OrderedDict([
        ("A Banco (N+1/índices)", ["PERF-01", "PERF-02", "PERF-03", "PERF-06", "PERF-07", "PERF-10", "PERF-14"]),
        ("B Volume/memória", ["PERF-05", "PERF-08"]),
        ("C Caminho da requisição", ["PERF-13"]),
        ("D Conexões/concorrência", ["PERF-04", "PERF-09", "PERF-12"]),
        ("F Crescimento/retenção", ["PERF-11"]),
    ]),
}

WEAK_POINTS = [
    ("Autorização é opt-in por rota e não há teste de matriz papel×rota",
     "9 handlers ficaram públicos sem intenção, `customers:*` nunca é exigido e anexos/auditoria ignoram a permissão da entidade.", ["SEC-01", "SEC-03", "SEC-04", "EST-02"]),
    ("Entrega/operação quebrada em pontos críticos",
     "Worker não inicia, build do frontend falha, importação descarta a geometria dos cabos e grava fora do volume configurado.", ["EST-01", "EST-15", "EST-05", "EST-08"]),
    ("Sem defesas de abuso nem tetos de recurso",
     "Um único request pode esgotar memória (`fiber_count`, imagem grande) e um anônimo satura o processo (dashboard N+1).", ["EST-11", "SEC-16", "PERF-04", "PERF-12"]),
    ("Integridade sob concorrência sem atomicidade",
     "If-Match é check-then-act, divisão de segmento sem lock, lease de job nunca renovada, uploads gravados antes do commit.", ["EST-03", "EST-04", "EST-07", "EST-09"]),
    ("Rastreabilidade insuficiente",
     "Auditoria cobre 4 módulos; exportações de PII, papéis e login não geram evento; métricas por processo com cardinalidade ilimitada.", ["EST-10", "SEC-13", "SEC-17", "EST-13"]),
    ("Configuração, segredos e supply chain",
     "Defaults públicos aceitos em produção, token de métricas efetivo é o default, CSP permissivo/sem TLS e CI sem scanners.", ["SEC-02", "SEC-05", "SEC-11", "SEC-15", "EST-16"]),
    ("N+1 e índices ausentes nos caminhos de leitura pesados",
     "Dashboard (2.514 queries), impacto/rastreio (62 queries por vínculo) e busca em `terminals` sem índice.", ["PERF-01", "PERF-02", "PERF-03", "PERF-14"]),
]

# Comandos de medição (antes/depois) para issues de PERFORMANCE
MEASURE_CMD = {
    "PERF-01": "DATABASE_URL=postgresql+psycopg://USUARIO:SENHA@127.0.0.1:55432/audit PYTHONPATH=backend python docs/security-audit/tools/measure.py   # contador de statements + tempo do dashboard (antes: 2.514 statements, 1,0–1,5 s)\nDATABASE_URL=… python docs/security-audit/tools/measure5.py   # 20 requisições concorrentes (antes: wall 16,9 s)",
    "PERF-02": "DATABASE_URL=… PYTHONPATH=backend python docs/security-audit/tools/measure2.py   # POST /topology/impact: statements e tempo (antes: 62 statements/vínculo)",
    "PERF-03": "psql … -c \"EXPLAIN (ANALYZE) SELECT * FROM terminals WHERE entity_type='port' AND entity_id='<uuid>'\"   # antes: Parallel Seq Scan, 12–14 ms; depois: Index Scan",
    "PERF-04": "PYTHONPATH=backend python docs/security-audit/tools/measure4.py   # RSS pico e tempo do thumbnail (antes: +339 MiB, 0,67 s; bomb 14000×14000 → exceção)",
    "PERF-05": "PYTHONASYNCIODEBUG=1 uvicorn app.main:app & curl -w '%{time_total}\\n' -F file=@grande.geojson -H 'X-CSRF-Token: …' -b cookies.txt http://127.0.0.1:8000/api/v1/imports/preview   # medir tempo e `ps -o rss`; em paralelo `curl /health/live`",
    "PERF-06": "DATABASE_URL=… PYTHONPATH=backend python docs/security-audit/tools/measure.py   # EXPLAIN (ANALYZE) das buscas ILIKE (antes: Seq Scan 4,6 ms @10k)",
    "PERF-07": "DATABASE_URL=… PYTHONPATH=backend python docs/security-audit/tools/measure.py   # EXPLAIN de ORDER BY created_at DESC OFFSET 9000 (antes: Sort 5,9 ms)",
    "PERF-08": "/usr/bin/time -v python -c \"from app.modules.exports.service import generate_geojson_export …\"   # RSS pico antes/depois com o dataset sintético",
    "PERF-09": "psql -c \"SELECT pid, wait_event_type, wait_event, query FROM pg_stat_activity WHERE wait_event_type='Lock'\"   # durante dois splits paralelos",
    "PERF-10": "Contador de statements (event before_cursor_execute) em GET /api/v1/auth/me   # por leitura, antes: 2 (não medido); alvo: 1",
    "PERF-11": "psql -c \"SELECT relname, n_live_tup FROM pg_stat_user_tables WHERE relname IN ('login_attempts','user_sessions','audit_events')\"   # semanas depois",
    "PERF-12": "DATABASE_URL=… PYTHONPATH=backend python docs/security-audit/tools/measure5.py   # readiness sob carga (antes: pico 1,1 s; wall 16,9 s)",
    "PERF-13": "for i in $(seq 20); do curl -s -o /dev/null -w '%{time_total}\\n' http://127.0.0.1:8000/health/ready; done   # com e sem carga",
    "PERF-14": "Contador de statements em POST /api/v1/topology/trace com terminal OLT de fan-out alto (dataset sintético + splitters em cascata)",
}


# ------------------------------------------------------------------ utilidades de texto
def esc(t: str) -> str:
    return html.escape(t, quote=False)


def md(t: str) -> str:
    """Markdown mínimo (**negrito**, `código`) → markup do reportlab."""
    t = esc(t)
    t = re.sub(r"`([^`]+)`", r'<font name="DejaVuMono" size="7.6" backColor="#EEF2F7">\1</font>', t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
    return t


def short(t: str, n: int = 230) -> str:
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) <= n:
        return t
    head = t[:n]
    k = max(head.rfind(". "), head.rfind("; "))
    if k > n * 0.55:
        return head[: k + 1]
    return head.rsplit(" ", 1)[0] + "…"


def ref_html(e: dict) -> str:
    """Caminho em duas linhas (diretório / arquivo:linha) para não quebrar o número da linha."""
    d, _, fn = e["file"].rpartition("/")
    loc = f"{fn}:{e['line']}" + (f"-{e['line_end']}" if e["line_end"] != e["line"] else "")
    return (esc(d + "/") + "<br/>" if d else "") + f"<b>{esc(loc)}</b>"


def sev_key(f: dict) -> tuple:
    return (SEV.index(f["severity"]), f["id"])


def evid_ref(e: dict) -> str:
    return f"{e['file']}:{e['line']}" + (f"-{e['line_end']}" if e["line_end"] != e["line"] else "")


# ------------------------------------------------------------------ issues.md
def build_issues() -> list[dict]:
    issues = []
    for g in DOC["issue_groups"]:
        fs = [F[i] for i in g["ids"]]
        worst = min(fs, key=lambda f: SEV.index(f["severity"]))["severity"]
        cat = {"[Segurança]": "security", "[Arquitetura]": "architecture", "[Performance]": "performance"}[g["title"].split("]")[0] + "]"]
        labels = [cat, f"severity:{worst}"]
        L: list[str] = []
        a = L.append
        a(f"Título: {g['title']}")
        a(f"Labels sugeridas: {', '.join(labels)}")
        a(f"Achados cobertos: {', '.join(g['ids'])}")
        a("")
        a("## Descrição do problema e por que é explorável / degrada o sistema")
        for f in fs:
            a(f"### {f['id']} — {f['title']} (severidade: {f['severity']})")
            a(f"{f['description']}")
            a(f"- **Por que é explorável / degrada:** {f['exploitability']}")
            a(f"- **Condições de ocorrência:** {f['conditions']}")
            if f["category"] == "PERF":
                a(f"- **Gatilho de escala:** {f['trigger']}")
                a(f"- **Ordem de crescimento:** {f['growth']}")
            a(f"- **Prova:** {f['proof']}")
            a("")
        a("## Evidência")
        for f in fs:
            for e in f["evidence"]:
                a(f"**{f['id']}** `{evid_ref(e)}`" + (f" — {e['note']}" if e.get("note") else ""))
                a("```")
                a(e["snippet"])
                a("```")
        a("")
        a("## Impacto")
        for f in fs:
            a(f"- **{f['id']}:** {f['impact']}")
        a("")
        a("## Sugestão de correção")
        for f in fs:
            a(f"- **{f['id']}:** {f['fix']}")
        a("")
        a("## Como validar")
        for f in fs:
            a(f"- **{f['id']}:** {f['validation']}")
            if f["category"] == "PERF":
                a("  - Comando de medição (executar **antes** e **depois** da correção; em banco descartável):")
                a("    ```")
                for ln in MEASURE_CMD.get(f["id"], "n/d").split("\n"):
                    a("    " + ln)
                a("    ```")
        a("")
        a("## Critérios de aceite")
        for f in fs:
            for c in f["acceptance"]:
                a(f"- [ ] {f['id']}: {c}")
        a("- [ ] Existe ao menos um teste automatizado que **falha antes** da correção e **passa depois** (indicado acima), executado no CI.")
        a("- [ ] Nenhum segredo em claro em logs, respostas ou testes adicionados.")
        issues.append({"n": g["n"], "title": g["title"], "labels": labels, "ids": g["ids"], "text": "\n".join(L)})
    return issues


def write_issues_md(issues: list[dict]) -> None:
    out = ["# Issues para o GitHub — " + PROJECT, "",
           "> Gerado por `tools/generate_report.py` a partir de `findings.json`. **Documento confidencial**: descreve vulnerabilidades reais; não publique em repositório público. "
           "Copie cada bloco entre `--- ISSUE n ---` e `--- FIM ISSUE n ---` para uma issue (Markdown). Segredos estão mascarados (4 caracteres + `…`).", ""]
    for it in issues:
        out += [f"--- ISSUE {it['n']} ---", it["text"], f"--- FIM ISSUE {it['n']} ---", ""]
    (ROOT / "issues.md").write_text("\n".join(out), encoding="utf-8")


# ------------------------------------------------------------------ gráficos
def fig_donut() -> Path:
    cnt = Counter(f["severity"] for f in DOC["findings"])
    fig, ax = plt.subplots(figsize=(5.2, 3.6), dpi=200)
    vals = [cnt.get(s, 0) for s in SEV]
    nz = [(s, v) for s, v in zip(SEV, vals) if v]
    wedges, _ = ax.pie([v for _, v in nz], colors=[SEV_COLOR[s] for s, _ in nz], startangle=90, counterclock=False,
                       wedgeprops=dict(width=0.38, edgecolor="white", linewidth=1.5))
    ax.text(0, 0.08, str(sum(vals)), ha="center", va="center", fontsize=22, fontweight="bold", color="#111827")
    ax.text(0, -0.22, "achados", ha="center", va="center", fontsize=9, color="#6B7280")
    for w, (s, v) in zip(wedges, nz):
        ang = (w.theta2 + w.theta1) / 2
        import math
        x, y = 0.81 * math.cos(math.radians(ang)), 0.81 * math.sin(math.radians(ang))
        ax.text(x, y, str(v), ha="center", va="center", fontsize=10, color="white", fontweight="bold")
    handles = [plt.Line2D([0], [0], marker="o", ls="", color=SEV_COLOR[s], markersize=8, label=f"{s.capitalize()}: {cnt.get(s, 0)}") for s in SEV]
    handles.append(plt.Line2D([0], [0], marker="o", ls="", color=OK_COLOR, markersize=8, label=f"Ponto forte: {len(DOC['strengths'])} (fora do donut)"))
    ax.legend(handles=handles, loc="center left", bbox_to_anchor=(1.0, 0.5), frameon=False, fontsize=8)
    ax.set_title("Achados por severidade", fontsize=10, fontweight="bold", loc="left")
    fig.tight_layout()
    p = TMP / "donut.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    return p


def fig_bars() -> Path:
    labels, stacks = [], []
    for cat in ("SEC", "EST", "PERF"):
        for g, ids in SUBGROUP[cat].items():
            labels.append(f"{cat} · {g}")
            stacks.append(Counter(F[i]["severity"] for i in ids))
    # total por categoria
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.6, 4.6), dpi=200, gridspec_kw={"width_ratios": [1, 2.2]})
    cats = ["SEC", "EST", "PERF"]
    bottoms = [0, 0, 0]
    for s in SEV:
        vals = [sum(1 for f in DOC["findings"] if f["category"] == c and f["severity"] == s) for c in cats]
        ax1.bar(cats, vals, bottom=bottoms, color=SEV_COLOR[s], label=s.capitalize(), width=0.6)
        for i, v in enumerate(vals):
            if v:
                ax1.text(i, bottoms[i] + v / 2, str(v), ha="center", va="center", color="white", fontsize=8, fontweight="bold")
        bottoms = [b + v for b, v in zip(bottoms, vals)]
    for i, b in enumerate(bottoms):
        ax1.text(i, b + 0.4, str(b), ha="center", fontsize=9, fontweight="bold")
    ax1.set_ylim(0, max(bottoms) + 4)
    ax1.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    ax1.set_title("Por categoria", fontsize=10, fontweight="bold", loc="left", pad=10)
    ax1.spines[["top", "right"]].set_visible(False)
    ax1.set_ylabel("achados", fontsize=8)
    ax1.tick_params(labelsize=8)
    y = list(range(len(labels)))[::-1]
    left = [0] * len(labels)
    for s in SEV:
        vals = [st.get(s, 0) for st in stacks]
        ax2.barh(y, vals, left=left, color=SEV_COLOR[s], height=0.65)
        left = [a + b for a, b in zip(left, vals)]
    for yy, total in zip(y, left):
        ax2.text(total + 0.1, yy, str(total), va="center", fontsize=7.5)
    ax2.set_yticks(y)
    ax2.set_yticklabels(labels, fontsize=7)
    ax2.set_title("Por subcategoria", fontsize=10, fontweight="bold", loc="left")
    ax2.spines[["top", "right"]].set_visible(False)
    ax2.tick_params(axis="x", labelsize=8)
    h, l = ax1.get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=5, frameon=False, fontsize=8)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    p = TMP / "bars.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    return p


def fig_arch() -> Path:
    W, Hh = 3.6, 1.55
    pos = {"browser": (0.3, 6.6), "tiles": (0.3, 1.0), "caddy": (5.0, 3.85), "frontend": (10.0, 6.6), "backend": (10.0, 3.85),
           "worker": (10.0, 1.0), "migrate": (5.0, 1.0), "db": (15.4, 5.6), "storage": (15.4, 1.0)}
    style = {"client": ("#EFF6FF", "#1D4ED8"), "edge": ("#FEF3C7", "#B45309"), "app": ("#F0FDF4", "#15803D"),
             "data": ("#F5F3FF", "#6D28D9"), "ext": ("#F3F4F6", "#4B5563"), "job": ("#F3F4F6", "#4B5563")}
    fig, ax = plt.subplots(figsize=(11.2, 6.4), dpi=200)
    ax.set_xlim(0, 19.6)
    ax.set_ylim(0, 8.9)
    ax.axis("off")
    boxes = {}
    for c in DOC["architecture"]["components"]:
        x, y = pos[c["id"]]
        face, edge = style[c["kind"]]
        ax.add_patch(FancyBboxPatch((x, y), W, Hh, boxstyle="round,pad=0.02,rounding_size=0.15", fc=face, ec=edge, lw=1.4, ls="--" if c["kind"] == "ext" else "-"))
        ax.text(x + W / 2, y + Hh * 0.64, c["label"], ha="center", va="center", fontsize=6.9, fontweight="bold", color="#111827")
        hs = DOC["architecture"]["hotspots"].get(c["id"], [])
        if hs:
            ax.text(x + W / 2, y + 0.24, " ".join(hs[:4]) + (" …" if len(hs) > 4 else ""), ha="center", va="center", fontsize=5.2, color="#B91C1C")
            ax.add_patch(plt.Circle((x + W - 0.05, y + Hh - 0.05), 0.27, fc="#B91C1C", ec="white", lw=1.2, zorder=5))
            ax.text(x + W - 0.05, y + Hh - 0.05, str(len(hs)), ha="center", va="center", fontsize=8, color="white", fontweight="bold", zorder=6)
        if c["singleton"]:
            ax.add_patch(plt.Circle((x + 0.05, y + Hh - 0.05), 0.24, fc="#374151", ec="white", lw=1.2, zorder=5))
            ax.text(x + 0.05, y + Hh - 0.05, "S", ha="center", va="center", fontsize=8, color="white", fontweight="bold", zorder=6)
        boxes[c["id"]] = (x, y, W, Hh)

    def pt(a: str, side: str, frac: float = 0.5):
        x, y, w, h = boxes[a]
        return {"r": (x + w, y + h * frac), "l": (x, y + h * frac), "t": (x + w * frac, y + h), "b": (x + w * frac, y)}[side]
    # (origem, lado, destino, lado, fração da posição do rótulo, deslocamento y do rótulo, frações de ancoragem)
    routes = [
        ("browser", "r", "caddy", "t", 0.5, 0.0, (0.5, 0.3), "HTTP"),
        ("caddy", "r", "frontend", "l", 0.55, 0.0, (0.75, 0.5), "/*"),
        ("caddy", "r", "backend", "l", 0.5, 0.18, (0.4, 0.5), "/api/*, /health/*"),
        ("backend", "r", "db", "l", 0.45, 0.0, (0.85, 0.35), "SQLAlchemy pool 10+20"),
        ("worker", "r", "db", "b", 0.22, 0.0, (0.85, 0.3), "claim (SKIP LOCKED)"),
        ("backend", "r", "storage", "t", 0.32, 0.0, (0.15, 0.2), "anexos"),
        ("worker", "r", "storage", "l", 0.5, 0.22, (0.35, 0.45), "imports/exports"),
        ("browser", "b", "tiles", "t", 0.5, 0.0, (0.5, 0.5), "HTTPS (navegador)"),
    ]
    for a, sa, b, sb, t, dy, (fa, fb), lab in routes:
        p0, p1 = pt(a, sa, fa), pt(b, sb, fb)
        ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=9, lw=1.1, color="#4B5563", shrinkA=1, shrinkB=1))
        lx, ly = p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t + dy
        ax.text(lx, ly, lab, fontsize=5.8, ha="center", va="center", color="#374151", bbox=dict(fc="white", ec="none", pad=0.6, alpha=0.95), zorder=7)
    ax.text(0.3, 8.65, "Fluxo de dados e hotspots", fontsize=10, fontweight="bold")
    ax.text(0.3, 0.25, "S = singleton (sem redundância)    ●n = nº de achados no componente (IDs em vermelho)    tracejado = dependência externa", fontsize=6.6, color="#374151")
    p = TMP / "arch.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    return p


# ------------------------------------------------------------------ PDF
def register_fonts() -> None:
    d = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    pdfmetrics.registerFont(TTFont("DejaVu", str(d / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(d / "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Oblique", str(d / "DejaVuSans-Oblique.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-BoldOblique", str(d / "DejaVuSans-BoldOblique.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVuMono", str(d / "DejaVuSansMono.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVuMono-Bold", str(d / "DejaVuSansMono-Bold.ttf")))
    pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold", italic="DejaVu-Oblique", boldItalic="DejaVu-BoldOblique")
    pdfmetrics.registerFontFamily("DejaVuMono", normal="DejaVuMono", bold="DejaVuMono-Bold", italic="DejaVuMono", boldItalic="DejaVuMono-Bold")


class NumberedCanvas(canvas.Canvas):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._saved = []

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved)
        for st in self._saved:
            self.__dict__.update(st)
            self._decorate(total)
            super().showPage()
        super().save()

    def _decorate(self, total: int) -> None:
        w, h = A4
        self.saveState()
        self.setFont("DejaVu", 7.2)
        self.setFillColor(colors.HexColor("#374151"))
        self.drawString(2 * cm, h - 1.25 * cm, f"{REPORT_NAME} — {PROJECT}")
        self.drawRightString(w - 2 * cm, h - 1.25 * cm, "CONFIDENCIAL")
        self.setStrokeColor(colors.HexColor("#D1D5DB"))
        self.setLineWidth(0.5)
        self.line(2 * cm, h - 1.42 * cm, w - 2 * cm, h - 1.42 * cm)
        self.line(2 * cm, 1.45 * cm, w - 2 * cm, 1.45 * cm)
        self.drawString(2 * cm, 1.0 * cm, f"{REPORT_NAME}")
        self.drawRightString(w - 2 * cm, 1.0 * cm, f"Página {self._pageNumber} de {total}")
        self.restoreState()


class Doc(BaseDocTemplate):
    def afterFlowable(self, fl):
        if isinstance(fl, Paragraph) and getattr(fl, "_toc", None):
            lvl, text, in_toc = fl._toc
            key = f"h{lvl}_{abs(hash(text))}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, level=lvl, closed=(lvl > 0))
            if in_toc:
                self.notify("TOCEntry", (lvl, text, self.page, key))


def styles() -> dict[str, ParagraphStyle]:
    base = dict(fontName="DejaVu", fontSize=8.8, leading=12.2, textColor=colors.HexColor("#111827"))
    S = {
        "body": ParagraphStyle("body", **base),
        "small": ParagraphStyle("small", **{**base, "fontSize": 7.4, "leading": 9.6}),
        "cell": ParagraphStyle("cell", **{**base, "fontSize": 7.3, "leading": 9.4}),
        "cellpath": ParagraphStyle("cellpath", fontName="DejaVuMono", fontSize=6.3, leading=8.0, wordWrap="CJK", textColor=colors.HexColor("#1F2937")),
        "chip": ParagraphStyle("chip", fontName="DejaVu-Bold", fontSize=7, leading=9, alignment=TA_CENTER, textColor=colors.white),
        "h1": ParagraphStyle("h1", fontName="DejaVu-Bold", fontSize=15, leading=19, spaceBefore=4, spaceAfter=7, textColor=colors.HexColor("#111827")),
        "h2": ParagraphStyle("h2", fontName="DejaVu-Bold", fontSize=11, leading=14, spaceBefore=9, spaceAfter=4, textColor=colors.HexColor("#1F2937")),
        "h3": ParagraphStyle("h3", fontName="DejaVu-Bold", fontSize=9.3, leading=12, spaceBefore=6, spaceAfter=2, textColor=colors.HexColor("#1F2937")),
        "smallk": ParagraphStyle("smallk", fontName="DejaVu", fontSize=7.4, leading=9.6, spaceAfter=3, textColor=colors.HexColor("#111827")),
        "mono": ParagraphStyle("mono", fontName="DejaVuMono", fontSize=6.4, leading=8.1, wordWrap="CJK", textColor=colors.HexColor("#111827")),
        "monoh": ParagraphStyle("monoh", fontName="DejaVuMono-Bold", fontSize=7.4, leading=9.6, wordWrap="CJK", spaceBefore=2, textColor=colors.HexColor("#111827")),
        "title": ParagraphStyle("title", fontName="DejaVu-Bold", fontSize=22, leading=28, textColor=colors.HexColor("#111827")),
        "subtitle": ParagraphStyle("subtitle", fontName="DejaVu", fontSize=11.5, leading=16, textColor=colors.HexColor("#374151")),
        "toc1": ParagraphStyle("toc1", fontName="DejaVu-Bold", fontSize=8.8, leading=13, leftIndent=0),
        "toc2": ParagraphStyle("toc2", fontName="DejaVu", fontSize=8, leading=11.5, leftIndent=14),
    }
    return S


def chip(sev: str, S: dict) -> Paragraph:
    return Paragraph(sev.upper(), S["chip"])


def H(text: str, lvl: int, S: dict, toc: bool = True) -> Paragraph:
    p = Paragraph(md(text), S[f"h{lvl + 1}"])
    p._toc = (lvl, re.sub(r"`", "", text), toc)
    return p


def mono_block(text: str, S: dict) -> Paragraph:
    lines = []
    for ln in text.split("\n"):
        e = esc(ln)
        e = re.sub(r"^( +)", lambda m: "&nbsp;" * len(m.group(1)), e)
        e = e.replace("  ", "&nbsp;&nbsp;")
        lines.append(e)
    return Paragraph("<br/>".join(lines), S["mono"])


def build_pdf(issues: list[dict]) -> int:
    register_fonts()
    S = styles()
    donut, bars, arch = fig_donut(), fig_bars(), fig_arch()
    out = ROOT / "relatorio-auditoria-seguranca.pdf"
    doc = Doc(str(out), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2.0 * cm, bottomMargin=2.0 * cm,
              title=f"{REPORT_NAME} — {PROJECT}", author="Auditoria (somente leitura)", subject="Confidencial",
              pageCompression=1)
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame])])
    Wd = doc.width
    st: list = []
    tot = DOC["meta"]["totals"]
    cnt = Counter(f["severity"] for f in DOC["findings"])

    # ---------- a) Capa
    st += [Spacer(1, 2.2 * cm), Paragraph("Relatório de Auditoria de Segurança, Estrutura e Performance", S["title"]),
           Spacer(1, 0.25 * cm), Paragraph(f"— {esc(PROJECT)}", ParagraphStyle("t2", parent=S["title"], fontSize=16, leading=22, textColor=colors.HexColor("#374151"))),
           Spacer(1, 0.8 * cm)]
    meta_rows = [
        ["Data da auditoria", DOC["meta"]["audit_date"]],
        ["Versão auditada", DOC["meta"]["commit"]],
        ["Escopo auditado", DOC["meta"]["scope"]],
        ["Modo de trabalho", "Somente leitura no projeto. Medições apenas em PostgreSQL/PostGIS descartável local. Nenhum exploit executado; nada foi rodado contra produção."],
        ["Resultado", f"{tot['findings']} achados — " + ", ".join(f"{cnt.get(s, 0)} {p}" for s, p in zip(SEV[:4], ("críticos", "altos", "médios", "baixos"))) + f" — e {tot['strengths']} pontos fortes verificados. Nenhum achado crítico."],
    ]
    t = Table([[Paragraph(f"<b>{esc(a)}</b>", S["cell"]), Paragraph(md(b), S["cell"])] for a, b in meta_rows], colWidths=[3.6 * cm, Wd - 3.6 * cm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#E5E7EB")),
                           ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    st += [t, Spacer(1, 0.6 * cm), Paragraph("Nota metodológica — como cada categoria foi mapeada para a stack", S["h3"])]
    mt = Table([[Paragraph(f"<b>{esc(a)}</b>", S["cell"]), Paragraph(md(b), S["cell"])] for a, b in DOC["method_note"]], colWidths=[3.6 * cm, Wd - 3.6 * cm])
    mt.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#E5E7EB")),
                            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F9FAFB"))]))
    st += [mt, Spacer(1, 0.5 * cm)]
    conf = Table([[Paragraph("<b>AVISO DE CONFIDENCIALIDADE.</b> " + md("Este documento descreve vulnerabilidades reais e trechos de código do sistema. "
                             "Destina-se exclusivamente à equipe responsável pelo projeto. Não o publique em repositório público nem o encaminhe a terceiros sem autorização. "
                             "Segredos foram mascarados (4 primeiros caracteres + …). Sugere-se manter `docs/security-audit/` fora do controle de versão público (adicionar ao `.gitignore`)."), S["cell"])]], colWidths=[Wd])
    conf.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#B91C1C")), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEF2F2")),
                              ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    st += [conf, PageBreak()]

    # ---------- sumário
    toc = TableOfContents()
    toc.levelStyles = [S["toc1"], S["toc2"]]
    st += [Paragraph("Sumário", S["h1"]), toc, PageBreak()]

    # ---------- b) Resumo executivo
    st += [H("1. Resumo executivo", 0, S)]
    st.append(Paragraph(
        md(f"Foram verificados **{tot['findings']} achados** no código real (arquivo, linha e trecho conferidos por script de fidelidade): "
           f"**{cnt.get('alta', 0)} altos**, **{cnt.get('média', 0)} médios** e **{cnt.get('baixa', 0)} baixos**; nenhum crítico e nenhum informativo. "
           f"Há {tot['strengths']} controles corretos documentados. Por categoria: {tot['by_category'].get('SEC', 0)} de segurança, "
           f"{tot['by_category'].get('EST', 0)} estruturais e {tot['by_category'].get('PERF', 0)} de performance. A aplicação é de **organização única** (sem tenant): "
           "o principal risco de segurança não é o vazamento entre clientes, e sim a **autorização por rota** — endpoints públicos sem intenção e permissões declaradas mas nunca aplicadas."), S["body"]))
    st.append(Spacer(1, 0.25 * cm))
    # tabela de totais
    head = ["Severidade"] + [CAT_NAME[c].split(" ")[0] for c in ("SEC", "EST", "PERF")] + ["Total"]
    rows = [[Paragraph(f"<b>{h}</b>", S["cell"]) for h in head]]
    for s in SEV:
        r = [chip(s, S)]
        for c in ("SEC", "EST", "PERF"):
            r.append(Paragraph(str(sum(1 for f in DOC["findings"] if f["category"] == c and f["severity"] == s)), S["cell"]))
        r.append(Paragraph(f"<b>{cnt.get(s, 0)}</b>", S["cell"]))
        rows.append(r)
    rows.append([Paragraph("<b>Total</b>", S["cell"])] + [Paragraph(f"<b>{tot['by_category'].get(c, 0)}</b>", S["cell"]) for c in ("SEC", "EST", "PERF")] + [Paragraph(f"<b>{tot['findings']}</b>", S["cell"])])
    rows.append([Paragraph("Pontos fortes", S["cell"]), "", "", "", Paragraph(f"<b>{tot['strengths']}</b>", S["cell"])])
    tt = Table(rows, colWidths=[3.2 * cm, 2.6 * cm, 2.6 * cm, 2.6 * cm, 2.6 * cm], hAlign="LEFT")
    style = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
             ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#ECFDF5")), ("TEXTCOLOR", (0, -1), (-1, -1), colors.HexColor(OK_COLOR))]
    for i, s in enumerate(SEV, 1):
        style.append(("BACKGROUND", (0, i), (0, i), colors.HexColor(SEV_COLOR[s])))
    tt.setStyle(TableStyle(style))
    st += [tt, Spacer(1, 0.3 * cm)]
    st.append(Image(str(donut), width=8.0 * cm, height=8.0 * cm * 0.62, hAlign="LEFT"))
    st.append(Spacer(1, 0.15 * cm))
    st.append(Image(str(bars), width=Wd * 0.94, height=Wd * 0.94 * 0.475))
    st.append(Spacer(1, 0.2 * cm))
    st.append(Paragraph("Três conclusões para decisão", S["h3"]))
    for txt in [
        "**Fechar hoje (Onda 1):** endpoints anônimos (`/search`, `/dashboard/summary`), `customers:*` não aplicado, token de métricas padrão, worker que não inicia, build do frontend, teto de `fiber_count` e do upload de imagem. São correções de horas a poucos dias.",
        "**Autorização precisa virar padrão, não opt-in:** dependência global de autenticação + teste que percorre todas as rotas + teste de matriz papel×rota evita que a classe de erro volte (EST-02, SEC-03).",
        "**Performance está no caminho de leitura pesado:** o dashboard (2.514 queries com 10 mil estruturas), o impacto/rastreio (62 queries por vínculo) e o upload de imagem (+339 MiB) foram **medidos**; o restante está rotulado 'verificado por leitura, não medido'.",
    ]:
        st.append(Paragraph("• " + md(txt), ParagraphStyle("b", parent=S["body"], leftIndent=10, firstLineIndent=-8, spaceAfter=2)))
    st.append(PageBreak())

    # ---------- c) Mapa do sistema
    st += [H("2. Mapa do sistema", 0, S), Image(str(arch), width=Wd * 0.82, height=Wd * 0.82 * 0.585)]
    st.append(Paragraph("Componentes, fronteiras e dependências", S["h3"]))
    comp_rows = [[Paragraph("<b>Componente</b>", S["cell"]), Paragraph("<b>Singleton?</b>", S["cell"]), Paragraph("<b>Dependências / observações</b>", S["cell"])]]
    obs = {
        "browser": "Next.js (CSR), TanStack Query; sessão em cookie HttpOnly; busca tiles diretamente em OSM/CARTO (CSP).",
        "caddy": "Proxy único em `:80` (`auto_https off`); encaminha `/api/*`, `/health/*` ao backend e o resto ao Next.js. Aplica CSP/headers.",
        "frontend": "Next.js standalone `:3000`; rewrite `/api/v1` só usado sem Caddy. Imagem não builda (EST-15).",
        "backend": "FastAPI + SQLAlchemy síncrono; 1 processo uvicorn; pool 10+20; métricas e `lru_cache` em memória do processo.",
        "worker": "Consumidor de `async_jobs` (`SKIP LOCKED`); hoje crash-loop (EST-01); limpeza periódica de previews.",
        "db": "PostgreSQL 16 + PostGIS; única instância; rede `internal`; senha default do compose (SEC-05). Fonte da verdade de sessões, rate limit e fila.",
        "storage": "Volume Docker local compartilhado por backend e worker; anexos, previews e exports; sem retenção de exports (PERF-11).",
        "tiles": "Serviços externos consultados pelo navegador; única integração de terceiros. O backend não faz chamadas HTTP de saída.",
        "migrate": "Serviço one-shot `alembic upgrade head` antes do backend (sem corrida entre réplicas).",
    }
    for c in DOC["architecture"]["components"]:
        comp_rows.append([Paragraph(esc(c["label"].replace("\n", " ")), S["cell"]), Paragraph("sim (SPOF)" if c["singleton"] else "não", S["cell"]), Paragraph(md(obs[c["id"]]), S["cell"])])
    ct = Table(comp_rows, colWidths=[4.4 * cm, 2.0 * cm, Wd - 6.4 * cm], repeatRows=1)
    ct.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D1D5DB")), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    st += [ct, Spacer(1, 0.2 * cm)]
    st.append(Paragraph("Isolamento de tenant, autenticação e superfície", S["h3"]))
    for txt in [
        "**Tenant:** não existe. Nenhuma das 28 tabelas tem `tenant_id`/`org_id`/`owner_id` (justificativa: organização única; o controle é RBAC global). Detalhes na seção “Categorias não aplicáveis”.",
        "**AuthN:** sessão opaca (`core/dependencies.py:117-142` → `identity/service.py:119-157`). **AuthZ:** `require_permission` (`core/dependencies.py:181-195`) + matriz (`core/permissions.py:4-80`). **CSRF:** `core/dependencies.py:67-114`.",
        "**Superfície:** 110 handlers (contagem por introspecção de `app`, ver `inventario-rotas.md`): 89 com `require_permission`, 7 públicos por design, 9 sem auth por engano/stub, 2 com auth opcional, 3 com sessão de qualquer papel.",
        "**Singletons / estado local:** Caddy, backend, worker, PostgreSQL e volume de arquivos são únicos; métricas/`lru_cache` locais ao processo; sessões, rate limit de login e fila estão no banco (escalam).",
        "**Modelo de dados (P0.5):** 28 tabelas em 10 migrações reversíveis; FKs `RESTRICT`, índices únicos parciais para atendimento ativo, GiST nas geometrias; ausência de índice em `terminals(entity_type, entity_id)` (PERF-03) e de trigram (PERF-06).",
    ]:
        st.append(Paragraph("• " + md(txt), ParagraphStyle("b2", parent=S["body"], leftIndent=10, firstLineIndent=-8, spaceAfter=2)))
    st.append(PageBreak())

    # ---------- d) Pontos fortes e fracos
    st.append(H("3. Pontos fortes verificados", 0, S))
    st.append(Paragraph("Cada item abaixo foi conferido no código (arquivo:linha). Evidências completas com trechos em `findings.json`.", S["small"]))
    srows = [[Paragraph("<b>ID</b>", S["cell"]), Paragraph("<b>Controle correto</b>", S["cell"]), Paragraph("<b>Evidência (arquivo:linha)</b>", S["cell"])]]
    for s in DOC["strengths"]:
        refs = "<br/>".join(ref_html(e) for e in s["evidence"][:3]) or esc(s.get("command", ""))
        srows.append([Paragraph(s["id"], ParagraphStyle("okid", parent=S["chip"], fontSize=6.6)), Paragraph(f"<b>{md(s['title'])}</b><br/>{md(s['description'])}", S["cell"]), Paragraph(refs, S["cellpath"])])
    stt = Table(srows, colWidths=[1.6 * cm, 8.9 * cm, Wd - 10.5 * cm], repeatRows=1)
    stt.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D1D5DB")), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ECFDF5")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                             ("BACKGROUND", (0, 1), (0, -1), colors.HexColor(OK_COLOR)), ("TEXTCOLOR", (0, 1), (0, -1), colors.white)]))
    st += [stt, Spacer(1, 0.3 * cm)]
    st += [CondPageBreak(9.5 * cm), H("4. Pontos fracos (riscos centrais)", 0, S)]
    wrows = []
    for i, (t1, t2, ids) in enumerate(WEAK_POINTS, 1):
        wrows.append([Paragraph(f"<b>{i}</b>", S["cell"]), Paragraph(f"<b>{esc(t1)}</b><br/>{md(t2)}", S["cell"]), Paragraph(esc(", ".join(ids)), S["cellpath"])])
    wt = Table(wrows, colWidths=[0.8 * cm, 11.4 * cm, Wd - 12.2 * cm])
    wt.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D1D5DB")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#FEF2F2"))]))
    st += [wt, Spacer(1, 0.3 * cm)]
    st.append(H("5. Categorias não aplicáveis à stack", 0, S))
    na = [[Paragraph("<b>Categoria</b>", S["cell"]), Paragraph("<b>Por quê</b>", S["cell"])]]
    for x in DOC["not_applicable"]:
        na.append([Paragraph(md(x["category"]), S["cell"]), Paragraph(md(x["reason"]), S["cell"])])
    nt = Table(na, colWidths=[4.6 * cm, Wd - 4.6 * cm], repeatRows=1)
    nt.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D1D5DB")), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    st += [nt, PageBreak()]

    # ---------- e) Achados por categoria
    st.append(H("6. Achados detalhados por categoria", 0, S))
    st.append(Paragraph(md("Tabelas: Severidade | Arquivo:linha | Descrição (PERF inclui gatilho de escala). O texto completo de cada achado — evidência com trecho, impacto, correção, validação e critérios de aceite — está na seção “Issues para o GitHub” (e em `issues.md`). Rótulos de prova: medido, reproduzido ou leitura (verificado por leitura, não medido)."), S["small"]))
    for cat in ("SEC", "EST", "PERF"):
        st.append(H(f"6.{['SEC', 'EST', 'PERF'].index(cat) + 1} {CAT_NAME[cat]}", 1, S))
        fs = sorted([f for f in DOC["findings"] if f["category"] == cat], key=sev_key)
        rows = [[Paragraph("<b>Severid.</b>", S["cell"]), Paragraph("<b>Arquivo:linha</b>", S["cell"]), Paragraph("<b>Descrição</b>", S["cell"])]]
        styl = [("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D1D5DB")), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")), ("VALIGN", (0, 0), (-1, -1), "TOP")]
        for i, f in enumerate(fs, 1):
            refs = "<br/>".join(ref_html(e) for e in f["evidence"][:3]) + (f"<br/><font color='#6B7280'>(+{len(f['evidence']) - 3} âncoras em findings.json)</font>" if len(f["evidence"]) > 3 else "")
            d = f"<b>{f['id']} — {md(f['title'])}</b><br/>{md(short(f['description'], 330))}"
            d += f"<br/><i>Condições:</i> {md(short(f['conditions'], 190))}"
            if cat == "PERF":
                d += f"<br/><i>Gatilho de escala:</i> {md(short(f['trigger'], 200))}"
            kind = {"medido": "medido", "reproduzido": "reproduzido", "leitura": "verificado por leitura, não medido"}[f["proof_kind"]]
            d += f"<br/><font color='#6B7280'>Prova: {kind}</font>"
            rows.append([chip(f["severity"], S), Paragraph(refs, S["cellpath"]), Paragraph(d, S["cell"])])
            styl.append(("BACKGROUND", (0, i), (0, i), colors.HexColor(SEV_COLOR[f["severity"]])))
            styl.append(("VALIGN", (0, i), (0, i), "MIDDLE"))
        tb = Table(rows, colWidths=[1.9 * cm, 5.0 * cm, Wd - 6.9 * cm], repeatRows=1)
        tb.setStyle(TableStyle(styl))
        st += [tb, Spacer(1, 0.25 * cm)]
    st.append(PageBreak())

    # ---------- f) Top 10 + matriz
    st.append(H("7. Top 10 gargalos de performance", 0, S))
    st.append(Paragraph("Ordenados por impacto × probabilidade (rank definido pela combinação de severidade, frequência de uso do caminho e evidência medida).", S["small"]))
    top = sorted([f for f in DOC["findings"] if f["category"] == "PERF"], key=lambda f: f["rank"])[:10]
    rows = [[Paragraph(f"<b>{h}</b>", S["cell"]) for h in ("#", "Severid.", "Gargalo", "Gatilho de escala", "Crescimento", "Prova")]]
    styl = [("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D1D5DB")), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")), ("VALIGN", (0, 0), (-1, -1), "TOP")]
    for i, f in enumerate(top, 1):
        kind = {"medido": "medido", "reproduzido": "reproduzido", "leitura": "por leitura, não medido"}[f["proof_kind"]]
        rows.append([Paragraph(f"<b>{i}</b>", S["cell"]), chip(f["severity"], S), Paragraph(f"<b>{f['id']}</b> {md(f['title'])}", S["cell"]),
                     Paragraph(md(short(f["trigger"], 170)), S["cell"]), Paragraph(md(f["growth"]), S["cell"]), Paragraph(kind, S["cell"])])
        styl.append(("BACKGROUND", (1, i), (1, i), colors.HexColor(SEV_COLOR[f["severity"]])))
        styl.append(("VALIGN", (1, i), (1, i), "MIDDLE"))
    tt2 = Table(rows, colWidths=[0.8 * cm, 1.9 * cm, 5.2 * cm, 4.1 * cm, 2.9 * cm, Wd - 14.9 * cm], repeatRows=1)
    tt2.setStyle(TableStyle(styl))
    st += [tt2, Spacer(1, 0.4 * cm)]

    mat_head = [H("8. Matriz esforço × impacto (todos os achados)", 0, S),
                Paragraph("Colunas: esforço de correção (baixo → alto). Linhas: ganho de risco/desempenho (alto → baixo). Chips coloridos pela severidade.", S["smallk"])]
    grid = {(e, g): [] for e in (1, 2, 3) for g in (1, 2, 3)}
    for f in sorted(DOC["findings"], key=sev_key):
        grid[(f["effort"], f["gain"])].append(f)
    hdr = [Paragraph("", S["cell"])] + [Paragraph(f"<b>Esforço {EFFORT[e]}</b>", S["cell"]) for e in (1, 2, 3)]
    mrows = [hdr]
    quad = {(1, 3): "Ganhos rápidos", (2, 3): "Projetos prioritários", (3, 3): "Investimentos estratégicos", (1, 2): "Fazer junto", (2, 2): "Planejar", (3, 2): "Avaliar", (1, 1): "Preencher", (2, 1): "Backlog", (3, 1): "Evitar/rever"}
    for g in (3, 2, 1):
        row = [Paragraph(f"<b>Impacto {GAIN[g]}</b>", S["cell"])]
        for e in (1, 2, 3):
            chips = " ".join(f'<font backColor="{SEV_COLOR[f["severity"]]}" color="white" size="6.4">&nbsp;{f["id"]}&nbsp;</font>' for f in grid[(e, g)])
            row.append(Paragraph(f"<font size='6.6' color='#6B7280'><b>{quad[(e, g)]}</b> ({len(grid[(e, g)])})</font><br/>{chips}", ParagraphStyle("m", parent=S["cell"], leading=11.5)))
        mrows.append(row)
    mtab = Table(mrows, colWidths=[2.2 * cm] + [(Wd - 2.2 * cm) / 3] * 3)
    mstyle = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")), ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#F3F4F6")),
              ("BACKGROUND", (1, 1), (1, 1), colors.HexColor("#ECFDF5")), ("BACKGROUND", (2, 1), (2, 1), colors.HexColor("#F0FDF4"))]
    mtab.setStyle(TableStyle(mstyle))
    st += [KeepTogether(mat_head + [mtab]), PageBreak()]

    # ---------- g) Recomendações
    st.append(H("9. Recomendações priorizadas", 0, S))
    for w in ("1", "2", "3", "4"):
        meta = DOC["waves"][w]
        st.append(H(meta["title"], 1, S))
        st.append(Paragraph(esc(meta["desc"]), S["smallk"]))
        fs = sorted([f for f in DOC["findings"] if f["wave"] == int(w)], key=sev_key)
        rows = []
        styl = [("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E5E7EB")), ("VALIGN", (0, 0), (-1, -1), "TOP")]
        for i, f in enumerate(fs):
            rows.append([chip(f["severity"], S), Paragraph(f"<b>{f['id']}</b>", S["cell"]), Paragraph(f"{md(f['title'])}<br/><font color='#6B7280'>Esforço {EFFORT[f['effort']]} · impacto {GAIN[f['gain']]} — {md(short(f['fix'], 260))}</font>", S["cell"])])
            styl.append(("BACKGROUND", (0, i), (0, i), colors.HexColor(SEV_COLOR[f["severity"]])))
            styl.append(("VALIGN", (0, i), (0, i), "MIDDLE"))
        if rows:
            rt = Table(rows, colWidths=[1.8 * cm, 1.9 * cm, Wd - 3.7 * cm], repeatRows=0)
            rt.setStyle(TableStyle(styl))
            st += [rt, Spacer(1, 0.2 * cm)]
    st.append(H("10. Limitações do trabalho", 0, S))
    for txt in [
        "**Não executado:** build real do frontend e da stack `docker compose` completa; restauração de backup; concorrência real de PATCH/split; carga sustentada em hardware de produção; testes de penetração.",
        "**Medições** foram feitas in-process (TestClient) contra PostgreSQL/PostGIS descartável com o dataset sintético do repositório (10.001 estruturas, 103.200 fibras, 1 cliente): informam ordem de grandeza e proporções, não capacidade de produção. Extrapolações estão marcadas como tal.",
        "**Não verificável sem acesso à operação:** configuração real de produção (variáveis, TLS, LB à frente, política de rede), conteúdo do banco, logs reais e se o repositório é público (afeta a severidade dos defaults de segredo).",
        "`pnpm audit`/`pip-audit` refletem as bases de advisories no dia da execução (18/09/2026, rede disponível). O frontend não foi buildado para inspeção do bundle; foi varrido o `.next` já existente.",
    ]:
        st.append(Paragraph("• " + md(txt), ParagraphStyle("b3", parent=S["body"], leftIndent=10, firstLineIndent=-8, spaceAfter=2)))
    st.append(PageBreak())

    # ---------- h) Issues
    st.append(H("11. ISSUES PARA O GITHUB", 0, S))
    st.append(Paragraph(f"{len(issues)} issues (achados triviais e relacionados agrupados). O mesmo conteúdo está em `issues.md` (Markdown puro — use-o para colar no GitHub; copiar deste PDF quebra linhas). "
                        "Cada bloco contém: título, labels, descrição, evidência (arquivo:linha + trecho), impacto, correção, como validar (PERF: comando antes/depois) e critérios de aceite.", S["small"]))
    for it in issues:
        st.append(H(f"Issue {it['n']} — {it['title']}", 1, S, toc=False))
        st.append(Paragraph(f"--- ISSUE {it['n']} ---", S["monoh"]))
        st.append(mono_block(it["text"], S))
        st.append(Paragraph(f"--- FIM ISSUE {it['n']} ---", S["monoh"]))
        st.append(Spacer(1, 0.25 * cm))

    story: list = []
    for fl in st:
        if isinstance(fl, Paragraph) and getattr(fl, "_toc", None):
            story.append(CondPageBreak(3.8 * cm))
        story.append(fl)
    doc.multiBuild(story, canvasmaker=NumberedCanvas)
    return doc.page


def main() -> int:
    issues = build_issues()
    write_issues_md(issues)
    n = build_pdf(issues)
    print(f"OK: issues.md ({len(issues)} issues); PDF páginas={n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
