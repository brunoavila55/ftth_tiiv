"""ORÁCULO (R22): cópia literal dos geradores de exportação anteriores ao streaming.

Usada só pelos testes de caracterização (mesmo conteúdo, nova implementação em fluxo)."""

import csv
import io
import json
import os
import uuid
import xml.etree.ElementTree as ET
from typing import Any

from fastapi import HTTPException, status
from geoalchemy2.shape import to_shape
from shapely import to_geojson
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.audit.service import record_audit_event
from app.modules.cables.models import CableSegment
from app.modules.customers.models import Customer
from app.modules.identity.models import User
from app.modules.imports.models import AsyncJob
from app.modules.inventory.models import Site, Structure
from app.modules.jobs.errors import JobValidationError
from app.schemas.imports_exports import ExportRequest, ExportResponse

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def get_export_storage_path() -> str:
    """Diretório absoluto/efetivo de exportações: `<STORAGE_PATH>/exports`.

    Cópia independente do `core.storage_backend` de produção — este arquivo é um oráculo
    (comportamento antigo, pré-streaming) e não deve depender da implementação atual.
    """
    from pathlib import Path

    path = Path(get_settings().STORAGE_PATH) / "exports"
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


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


def generate_geojson_export(db: Session, layers: list[str]) -> dict[str, Any]:
    features: list[dict[str, Any]] = []

    if "sites" in layers:
        sites = db.scalars(select(Site)).all()
        for s in sites:
            geom = to_shape(s.location)
            features.append(
                {
                    "type": "Feature",
                    "id": str(s.id),
                    "geometry": json.loads(to_geojson(geom)),
                    "properties": {
                        "layer": "sites",
                        "code": s.code,
                        "name": s.name,
                        "kind": s.kind,
                        "status": s.status,
                    },
                }
            )

    if "structures" in layers or "poles" in layers or "ctos" in layers or "ceos" in layers:
        structs = db.scalars(select(Structure)).all()
        for st in structs:
            if st.kind == "pole" and "poles" not in layers and "structures" not in layers:
                continue
            if st.kind == "cto" and "ctos" not in layers and "structures" not in layers:
                continue
            if st.kind == "ceo" and "ceos" not in layers and "structures" not in layers:
                continue

            geom = to_shape(st.location)
            features.append(
                {
                    "type": "Feature",
                    "id": str(st.id),
                    "geometry": json.loads(to_geojson(geom)),
                    "properties": {
                        "layer": "structures",
                        "code": st.code,
                        "kind": st.kind,
                        "status": st.status,
                    },
                }
            )

    if "cables" in layers:
        segments = db.scalars(select(CableSegment)).all()
        for seg in segments:
            geom = to_shape(seg.geometry)
            features.append(
                {
                    "type": "Feature",
                    "id": str(seg.id),
                    "geometry": json.loads(to_geojson(geom)),
                    "properties": {
                        "layer": "cables",
                        "cable_id": str(seg.cable_id),
                        "effective_length_m": seg.effective_length_m,
                        "status": seg.status,
                    },
                }
            )

    if "customers" in layers:
        customers = db.scalars(select(Customer)).all()
        for c in customers:
            features.append(
                {
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
            )

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def generate_kml_export(db: Session, layers: list[str]) -> str:
    kml = ET.Element("kml", xmlns="http://www.opengis.net/kml/2.2")
    doc = ET.SubElement(kml, "Document")
    doc_name = ET.SubElement(doc, "name")
    doc_name.text = "FTTH Manager Export"

    if "sites" in layers:
        folder = ET.SubElement(doc, "Folder")
        f_name = ET.SubElement(folder, "name")
        f_name.text = "Sites"
        sites = db.scalars(select(Site)).all()
        for s in sites:
            geom = to_shape(s.location)
            pm = ET.SubElement(folder, "Placemark")
            pm_name = ET.SubElement(pm, "name")
            pm_name.text = f"{s.code} - {s.name}"
            point = ET.SubElement(pm, "Point")
            coords = ET.SubElement(point, "coordinates")
            coords.text = f"{geom.x},{geom.y},0"

    if "structures" in layers or "poles" in layers or "ctos" in layers or "ceos" in layers:
        folder = ET.SubElement(doc, "Folder")
        f_name = ET.SubElement(folder, "name")
        f_name.text = "Estruturas"
        structs = db.scalars(select(Structure)).all()
        for st in structs:
            geom = to_shape(st.location)
            pm = ET.SubElement(folder, "Placemark")
            pm_name = ET.SubElement(pm, "name")
            pm_name.text = f"{st.code} ({st.kind})"
            point = ET.SubElement(pm, "Point")
            coords = ET.SubElement(point, "coordinates")
            coords.text = f"{geom.x},{geom.y},0"

    if "cables" in layers:
        folder = ET.SubElement(doc, "Folder")
        f_name = ET.SubElement(folder, "name")
        f_name.text = "Cabos"
        segments = db.scalars(select(CableSegment)).all()
        for seg in segments:
            geom = to_shape(seg.geometry)
            pm = ET.SubElement(folder, "Placemark")
            pm_name = ET.SubElement(pm, "name")
            pm_name.text = f"Cabo {seg.cable_id}"
            ls = ET.SubElement(pm, "LineString")
            coords = ET.SubElement(ls, "coordinates")
            coords.text = " ".join(f"{x},{y},0" for x, y in geom.coords)

    raw_bytes: bytes = ET.tostring(kml, encoding="utf-8", xml_declaration=True)
    return raw_bytes.decode("utf-8")


def generate_csv_export(db: Session, layers: list[str]) -> str:
    output = io.StringIO()
    writer = csv.writer(output, delimiter=",")
    writer.writerow(
        [
            "layer",
            "id",
            "code",
            "name",
            "kind",
            "status",
            "latitude",
            "longitude",
            "length_m",
        ]
    )

    if "sites" in layers:
        sites = db.scalars(select(Site)).all()
        for s in sites:
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

    if "structures" in layers or "poles" in layers or "ctos" in layers or "ceos" in layers:
        structs = db.scalars(select(Structure)).all()
        for st in structs:
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
        segments = db.scalars(select(CableSegment)).all()
        for seg in segments:
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
        customers = db.scalars(select(Customer)).all()
        for c in customers:
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

    return output.getvalue()


def execute_export_job(db: Session, job: AsyncJob) -> str:
    payload = job.payload or {}
    fmt_str = payload.get("format", "geojson")
    layers = payload.get("layers", ["sites", "structures", "cables"])

    storage_dir = get_export_storage_path()
    ext = fmt_str.lower()
    stored_path = f"exports/{job.id}.{ext}"  # gravado relativo à raiz do storage
    file_path = os.path.join(storage_dir, f"{job.id}.{ext}")

    if fmt_str == "geojson":
        geojson_data = generate_geojson_export(db, layers)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(geojson_data, f, ensure_ascii=False, indent=2)
    elif fmt_str == "kml":
        kml_str = generate_kml_export(db, layers)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(kml_str)
    elif fmt_str == "csv":
        csv_str = generate_csv_export(db, layers)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(csv_str)
    else:
        raise JobValidationError(f"Formato de exportação desconhecido: {fmt_str}")

    return stored_path
