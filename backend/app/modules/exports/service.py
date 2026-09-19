import csv
import json
import uuid
from collections.abc import Iterator
from typing import Any, TextIO, cast
from xml.sax.saxutils import escape as xml_escape

from fastapi import HTTPException, status
from geoalchemy2.shape import to_shape
from shapely import to_geojson
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.storage_backend import get_storage_backend
from app.modules.audit.service import record_audit_event
from app.modules.cables.models import CableSegment
from app.modules.customers.models import Customer
from app.modules.identity.models import User
from app.modules.imports.models import AsyncJob
from app.modules.inventory.models import Site, Structure
from app.modules.jobs.errors import JobValidationError
from app.schemas.imports_exports import ExportRequest, ExportResponse

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def is_formula_injection(val: str) -> bool:
    if not val:
        return False
    if val.startswith(("=", "@", "\t", "\r")):
        return True
    if val.startswith(("+", "-")):
        try:
            float(val.replace(",", "."))
            return False
        except ValueError:
            return True
    return False


def neutralize_csv_value(value: Any) -> str:
    if value is None:
        return ""
    str_val = str(value)
    if is_formula_injection(str_val):
        return f"'{str_val}"
    return str_val


def create_export_request(
    db: Session,
    payload: ExportRequest,
    user: User | None = None,
) -> ExportResponse:
    # Validação de permissões para camada de clientes (LGPD restrito a Admin)
    if "customers" in payload.layers and (not user or user.role != "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissão insuficiente para exportar dados pessoais de clientes (LGPD).",
        )

    job_type = f"export_{payload.format.value}"
    idempotency_key = f"export-{uuid.uuid4()}"

    job = AsyncJob(
        type=job_type,
        status="queued",
        idempotency_key=idempotency_key,
        payload={
            "format": payload.format.value,
            "layers": payload.layers,
            # quem pediu: o download revalida o papel (camada de clientes exige admin)
            "requested_by": str(user.id) if user else None,
            "requested_by_role": user.role if user else None,
        },
        progress_percentage=0,
        user_id=user.id if user else None,
    )
    db.add(job)
    db.flush()
    record_audit_event(
        db,
        actor_id=user.id if user else None,
        actor_name=user.name if user else "Sistema",
        action="export_requested",
        entity_type="async_job",
        entity_id=job.id,
        changes={"format": payload.format.value, "layers": payload.layers},
    )
    db.commit()
    db.refresh(job)

    return ExportResponse(
        job_id=str(job.id),
        message="Solicitação de exportação registrada com sucesso",
    )


# Linhas por página do cursor de servidor: memória proporcional a esta página, não à camada inteira
YIELD_PER = 1000

STRUCTURE_LAYERS = ("structures", "poles", "ctos", "ceos")


def _stream(db: Session, statement: Any) -> Iterator[Any]:
    """Itera o resultado com cursor de servidor (`yield_per`) sem carregar a camada toda."""
    return db.execute(statement.execution_options(yield_per=YIELD_PER)).scalars()


def _wants_structures(layers: list[str]) -> bool:
    return any(name in layers for name in STRUCTURE_LAYERS)


def _structure_in_geojson(kind: str, layers: list[str]) -> bool:
    if kind == "pole":
        return "poles" in layers or "structures" in layers
    if kind == "cto":
        return "ctos" in layers or "structures" in layers
    if kind == "ceo":
        return "ceos" in layers or "structures" in layers
    return True  # demais tipos (manhole, pedestal...) entram com qualquer camada de estrutura


def iter_geojson_features(db: Session, layers: list[str]) -> Iterator[dict[str, Any]]:
    if "sites" in layers:
        for s in _stream(db, select(Site)):
            yield {
                "type": "Feature",
                "id": str(s.id),
                "geometry": json.loads(to_geojson(to_shape(s.location))),
                "properties": {
                    "layer": "sites",
                    "code": s.code,
                    "name": s.name,
                    "kind": s.kind,
                    "status": s.status,
                },
            }

    if _wants_structures(layers):
        for st in _stream(db, select(Structure)):
            if not _structure_in_geojson(st.kind, layers):
                continue
            yield {
                "type": "Feature",
                "id": str(st.id),
                "geometry": json.loads(to_geojson(to_shape(st.location))),
                "properties": {
                    "layer": "structures",
                    "code": st.code,
                    "kind": st.kind,
                    "status": st.status,
                },
            }

    if "cables" in layers:
        for seg in _stream(db, select(CableSegment)):
            yield {
                "type": "Feature",
                "id": str(seg.id),
                "geometry": json.loads(to_geojson(to_shape(seg.geometry))),
                "properties": {
                    "layer": "cables",
                    "cable_id": str(seg.cable_id),
                    "effective_length_m": seg.effective_length_m,
                    "status": seg.status,
                },
            }

    if "customers" in layers:
        for c in _stream(db, select(Customer)):
            yield {
                "type": "Feature",
                "id": str(c.id),
                "geometry": None,
                "properties": {
                    "layer": "customers",
                    "code": c.code,
                    "name": c.name,
                    "phone": c.phone,
                    "address": c.address,
                },
            }


def write_geojson_export(db: Session, layers: list[str], out: TextIO) -> None:
    """Escreve um FeatureCollection incrementalmente (uma feature por vez)."""
    out.write('{"type":"FeatureCollection","features":[')
    first = True
    for feature in iter_geojson_features(db, layers):
        if not first:
            out.write(",")
        out.write(json.dumps(feature, ensure_ascii=False, separators=(",", ":")))
        first = False
    out.write("]}")


def write_kml_export(db: Session, layers: list[str], out: TextIO) -> None:
    def esc(value: Any) -> str:
        return xml_escape(str(value))

    out.write("<?xml version='1.0' encoding='utf-8'?>\n")
    out.write(
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>FTTH Manager Export</name>'
    )

    if "sites" in layers:
        out.write("<Folder><name>Sites</name>")
        for s in _stream(db, select(Site)):
            geom = to_shape(s.location)
            out.write(
                f"<Placemark><name>{esc(f'{s.code} - {s.name}')}</name>"
                f"<Point><coordinates>{geom.x},{geom.y},0</coordinates></Point></Placemark>"
            )
        out.write("</Folder>")

    if _wants_structures(layers):
        out.write("<Folder><name>Estruturas</name>")
        for st in _stream(db, select(Structure)):
            geom = to_shape(st.location)
            out.write(
                f"<Placemark><name>{esc(f'{st.code} ({st.kind})')}</name>"
                f"<Point><coordinates>{geom.x},{geom.y},0</coordinates></Point></Placemark>"
            )
        out.write("</Folder>")

    if "cables" in layers:
        out.write("<Folder><name>Cabos</name>")
        for seg in _stream(db, select(CableSegment)):
            geom = to_shape(seg.geometry)
            coords = " ".join(f"{x},{y},0" for x, y in geom.coords)
            out.write(
                f"<Placemark><name>{esc(f'Cabo {seg.cable_id}')}</name>"
                f"<LineString><coordinates>{coords}</coordinates></LineString></Placemark>"
            )
        out.write("</Folder>")

    out.write("</Document></kml>")


def write_csv_export(db: Session, layers: list[str], out: TextIO) -> None:
    writer = csv.writer(out, delimiter=",")
    writer.writerow(
        ["layer", "id", "code", "name", "kind", "status", "latitude", "longitude", "length_m"]
    )

    if "sites" in layers:
        for s in _stream(db, select(Site)):
            geom = to_shape(s.location)
            writer.writerow(
                [
                    neutralize_csv_value("sites"),
                    neutralize_csv_value(s.id),
                    neutralize_csv_value(s.code),
                    neutralize_csv_value(s.name),
                    neutralize_csv_value(s.kind),
                    neutralize_csv_value(s.status),
                    neutralize_csv_value(geom.y),
                    neutralize_csv_value(geom.x),
                    "",
                ]
            )

    if _wants_structures(layers):
        for st in _stream(db, select(Structure)):
            geom = to_shape(st.location)
            writer.writerow(
                [
                    neutralize_csv_value("structures"),
                    neutralize_csv_value(st.id),
                    neutralize_csv_value(st.code),
                    neutralize_csv_value(st.code),
                    neutralize_csv_value(st.kind),
                    neutralize_csv_value(st.status),
                    neutralize_csv_value(geom.y),
                    neutralize_csv_value(geom.x),
                    "",
                ]
            )

    if "cables" in layers:
        for seg in _stream(db, select(CableSegment)):
            geom = to_shape(seg.geometry)
            first_pt = geom.coords[0]
            writer.writerow(
                [
                    neutralize_csv_value("cables"),
                    neutralize_csv_value(seg.id),
                    neutralize_csv_value(f"CABLE-{seg.cable_id}"),
                    neutralize_csv_value(f"Cabo {seg.cable_id}"),
                    neutralize_csv_value("fiber_cable"),
                    neutralize_csv_value(seg.status),
                    neutralize_csv_value(first_pt[1]),
                    neutralize_csv_value(first_pt[0]),
                    neutralize_csv_value(seg.effective_length_m),
                ]
            )

    if "customers" in layers:
        for c in _stream(db, select(Customer)):
            writer.writerow(
                [
                    neutralize_csv_value("customers"),
                    neutralize_csv_value(c.id),
                    neutralize_csv_value(c.code),
                    neutralize_csv_value(c.name),
                    neutralize_csv_value("customer"),
                    neutralize_csv_value("active"),
                    "",
                    "",
                    "",
                ]
            )


def execute_export_job(db: Session, job: AsyncJob) -> str:
    payload = job.payload or {}
    fmt_str = payload.get("format", "geojson")
    layers = payload.get("layers", ["sites", "structures", "cables"])

    ext = fmt_str.lower()
    stored_path = f"exports/{job.id}.{ext}"  # gravado relativo à raiz do storage

    writers = {
        "geojson": write_geojson_export,
        "kml": write_kml_export,
        "csv": write_csv_export,
    }
    writer = writers.get(fmt_str)
    if writer is None:
        raise JobValidationError(f"Formato de exportação desconhecido: {fmt_str}")
    # Escrita incremental (memória limitada); só o arquivo final concluído é referenciado pelo job
    with get_storage_backend().save_stream(stored_path, mode="w", newline="") as out:
        writer(db, layers, cast(TextIO, out))

    return stored_path
