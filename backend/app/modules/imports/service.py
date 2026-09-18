import csv
import io
import json
import os
import uuid
import zipfile
from datetime import UTC, datetime, timedelta
from typing import Any

import defusedxml.ElementTree as ET
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.cables.models import Cable
from app.modules.identity.models import User
from app.modules.imports.models import AsyncJob, ImportPreview
from app.modules.inventory.models import Site, Structure
from app.schemas.imports_exports import (
    ImportCommitRequest,
    ImportCommitResponse,
    ImportFormat,
    ImportPreviewItem,
    ImportPreviewResponse,
)

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def get_storage_path() -> str:
    settings = get_settings()
    base_dir = os.path.join(getattr(settings, "STORAGE_DIR", "storage"), "imports")
    os.makedirs(base_dir, exist_ok=True)
    return base_dir


def sanitize_coord(val: Any) -> float:
    try:
        return float(str(val).replace(",", ".").strip())
    except (ValueError, TypeError) as err:
        raise ValueError(f"Coordenada inválida: {val}") from err


def parse_geojson(
    content: bytes,
) -> tuple[list[dict[str, Any]], list[ImportPreviewItem]]:
    try:
        text_data = content.decode("utf-8")
        data = json.loads(text_data)
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Arquivo GeoJSON com codificação inválida. Utilize UTF-8.",
        ) from None
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Sintaxe JSON inválida na linha {e.lineno}, coluna {e.colno}: {e.msg}",
        ) from e

    if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Estrutura GeoJSON inválida. Esperado objeto raiz com 'type': 'FeatureCollection'.",
        )

    features = data.get("features", [])
    parsed_items: list[dict[str, Any]] = []
    preview_items: list[ImportPreviewItem] = []

    for idx, feat in enumerate(features, start=1):
        geom = feat.get("geometry") or {}
        props = feat.get("properties") or {}
        geom_type = geom.get("type")
        coords = geom.get("coordinates")

        code = props.get("code") or props.get("codigo") or props.get("id") or props.get("name")
        if code:
            code = str(code).strip()

        entity_type = props.get("entity_type") or props.get("tipo")
        if not entity_type:
            if geom_type == "LineString":
                entity_type = "cable"
            elif geom_type == "Point":
                entity_type = (
                    "site" if props.get("type") in ("pop", "cabinet", "datacenter") else "structure"
                )
            else:
                entity_type = "unknown"
        entity_type = str(entity_type).lower()

        # Validações
        validation_status = "valid"
        error_msg: str | None = None

        if not code:
            validation_status = "error"
            error_msg = "Propriedade obrigatória 'code' ausente"
        elif geom_type not in ("Point", "LineString"):
            validation_status = "error"
            error_msg = f"Geometria '{geom_type}' não suportada. Use Point ou LineString."
        elif geom_type == "Point":
            try:
                if not coords or not isinstance(coords, (list, tuple)) or len(coords) < 2:
                    validation_status = "error"
                    error_msg = "Coordenadas Point ausentes ou incompletas"
                else:
                    lon, lat = sanitize_coord(coords[0]), sanitize_coord(coords[1])
                    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                        validation_status = "error"
                        error_msg = f"Coordenadas fora dos limites geodésicos: lat={lat}, lon={lon}"
            except Exception:
                validation_status = "error"
                error_msg = "Coordenadas Point inválidas"
        elif geom_type == "LineString":
            try:
                if not isinstance(coords, list) or len(coords) < 2:
                    validation_status = "error"
                    error_msg = "LineString deve conter pelo menos 2 pontos"
                else:
                    for pt in coords:
                        lon, lat = sanitize_coord(pt[0]), sanitize_coord(pt[1])
                        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                            validation_status = "error"
                            error_msg = (
                                f"Coordenadas fora dos limites geodésicos: lat={lat}, lon={lon}"
                            )
                            break
            except Exception:
                validation_status = "error"
                error_msg = "Coordenadas LineString inválidas"

        item_data = {
            "line_number": idx,
            "entity_type": entity_type,
            "code": code,
            "name": str(props.get("name") or code or f"Item {idx}"),
            "geom_type": geom_type,
            "coords": coords,
            "props": props,
            "validation_status": validation_status,
            "error_msg": error_msg,
        }
        parsed_items.append(item_data)
        preview_items.append(
            ImportPreviewItem(
                line_number=idx,
                entity_code=code,
                entity_type=entity_type,
                validation_status=validation_status,
                message=error_msg,
            )
        )

    return parsed_items, preview_items


def parse_kml(
    content: bytes,
) -> tuple[list[dict[str, Any]], list[ImportPreviewItem]]:
    # Suporte a KMZ (arquivo zip contendo doc.kml)
    if content.startswith(b"PK"):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                # Proteção contra zip bombs
                total_uncompressed = sum(info.file_size for info in z.infolist())
                if total_uncompressed > 50 * 1024 * 1024:  # 50 MB
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Arquivo KMZ excede o limite máximo descompactado de 50 MB.",
                    )
                kml_names = [n for n in z.namelist() if n.lower().endswith(".kml")]
                if not kml_names:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Arquivo KMZ não contém nenhum arquivo .kml válido.",
                    )
                # Bloqueio de path traversal
                target_kml = kml_names[0]
                if ".." in target_kml or target_kml.startswith("/"):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Nome de arquivo malicioso detectado dentro do KMZ.",
                    )
                content = z.read(target_kml)
        except zipfile.BadZipFile:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Arquivo KMZ corrompido ou formato zip inválido.",
            ) from None

    try:
        root = ET.fromstring(content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Sintaxe XML/KML inválida ou entidades proibidas (XXE): {e}",
        ) from e

    # Namespaces KML
    ns = {"kml": "http://www.opengis.net/kml/2.2"}
    placemarks = root.findall(".//kml:Placemark", ns)
    if not placemarks:
        # Tentar sem namespace
        placemarks = root.findall(".//Placemark")

    parsed_items: list[dict[str, Any]] = []
    preview_items: list[ImportPreviewItem] = []

    for idx, pm in enumerate(placemarks, start=1):
        name_elem = pm.find("kml:name", ns) if "kml" in ns else pm.find("name")
        name = name_elem.text.strip() if name_elem is not None and name_elem.text else f"KML_{idx}"
        code = name

        point_elem = pm.find(".//kml:Point", ns) if "kml" in ns else pm.find(".//Point")
        line_elem = pm.find(".//kml:LineString", ns) if "kml" in ns else pm.find(".//LineString")

        validation_status = "valid"
        error_msg: str | None = None
        geom_type = None
        coords: Any = None
        entity_type = "structure"

        if point_elem is not None:
            geom_type = "Point"
            coords_elem = (
                point_elem.find("kml:coordinates", ns)
                if "kml" in ns
                else point_elem.find("coordinates")
            )
            if coords_elem is not None and coords_elem.text:
                parts = coords_elem.text.strip().split(",")
                try:
                    lon, lat = sanitize_coord(parts[0]), sanitize_coord(parts[1])
                    coords = [lon, lat]
                    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                        validation_status = "error"
                        error_msg = f"Coordenadas fora dos limites geodésicos: lat={lat}, lon={lon}"
                except Exception:
                    validation_status = "error"
                    error_msg = "Coordenadas KML Point inválidas"
            else:
                validation_status = "error"
                error_msg = "Ponto KML sem tag coordinates"
        elif line_elem is not None:
            geom_type = "LineString"
            entity_type = "cable"
            coords_elem = (
                line_elem.find("kml:coordinates", ns)
                if "kml" in ns
                else line_elem.find("coordinates")
            )
            if coords_elem is not None and coords_elem.text:
                raw_pts = coords_elem.text.strip().split()
                coords = []
                try:
                    for pt_str in raw_pts:
                        p_parts = pt_str.split(",")
                        lon, lat = sanitize_coord(p_parts[0]), sanitize_coord(p_parts[1])
                        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                            validation_status = "error"
                            error_msg = (
                                f"Coordenadas fora dos limites geodésicos: lat={lat}, lon={lon}"
                            )
                            break
                        coords.append([lon, lat])
                    if len(coords) < 2 and validation_status == "valid":
                        validation_status = "error"
                        error_msg = "LineString KML deve conter pelo menos 2 pontos"
                except Exception:
                    validation_status = "error"
                    error_msg = "Coordenadas LineString KML inválidas"
            else:
                validation_status = "error"
                error_msg = "Linha KML sem tag coordinates"
        else:
            validation_status = "error"
            error_msg = "Placemark sem geometria Point ou LineString suportada"

        item_data = {
            "line_number": idx,
            "entity_type": entity_type,
            "code": code,
            "name": name,
            "geom_type": geom_type,
            "coords": coords,
            "props": {"name": name},
            "validation_status": validation_status,
            "error_msg": error_msg,
        }
        parsed_items.append(item_data)
        preview_items.append(
            ImportPreviewItem(
                line_number=idx,
                entity_code=code,
                entity_type=entity_type,
                validation_status=validation_status,
                message=error_msg,
            )
        )

    return parsed_items, preview_items


def parse_csv(
    content: bytes,
) -> tuple[list[dict[str, Any]], list[ImportPreviewItem]]:
    try:
        text_data = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text_data = content.decode("latin-1")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Codificação de arquivo CSV desconhecida. Utilize UTF-8.",
            ) from None

    # Detecção de delimitador
    sample = text_data[:2048]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","

    reader = csv.DictReader(io.StringIO(text_data), delimiter=delimiter)
    if not reader.fieldnames:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Arquivo CSV vazio ou sem cabeçalhos.",
        )

    # Normalizar cabeçalhos para minúsculas
    field_map = {f: f.strip().lower() for f in reader.fieldnames}

    parsed_items: list[dict[str, Any]] = []
    preview_items: list[ImportPreviewItem] = []

    for idx, row in enumerate(reader, start=2):  # linha 1 é o cabeçalho
        clean_row = {field_map[k]: (v.strip() if v else "") for k, v in row.items() if k}

        # Verificação de segurança contra formula injection
        has_formula = False
        for val in clean_row.values():
            if not val:
                continue
            if val.startswith(("=", "@", "\t", "\r")):
                has_formula = True
                break
            if val.startswith(("+", "-")):
                try:
                    float(val.replace(",", "."))
                except ValueError:
                    has_formula = True
                    break

        validation_status = "valid"
        error_msg: str | None = None

        if has_formula:
            validation_status = "error"
            error_msg = f"Possível injeção de fórmula de planilha detectada na linha {idx}"

        code = clean_row.get("code") or clean_row.get("codigo") or clean_row.get("id")
        name = clean_row.get("name") or clean_row.get("nome") or code or f"CSV_{idx}"

        entity_type = clean_row.get("entity_type") or clean_row.get("tipo")
        if not entity_type:
            if "fiber_count" in clean_row or "fibras" in clean_row:
                entity_type = "cable"
            elif "site_type" in clean_row or "tipo_site" in clean_row:
                entity_type = "site"
            else:
                entity_type = "structure"
        entity_type = entity_type.lower()

        coords: Any = None
        geom_type: str | None = None

        if entity_type in ("site", "structure"):
            geom_type = "Point"
            lat_str = clean_row.get("latitude") or clean_row.get("lat")
            lon_str = clean_row.get("longitude") or clean_row.get("lon") or clean_row.get("lng")
            if not lat_str or not lon_str:
                if validation_status == "valid":
                    validation_status = "error"
                    error_msg = f"Linha {idx} sem latitude/longitude obrigatórias"
            else:
                try:
                    lat = sanitize_coord(lat_str)
                    lon = sanitize_coord(lon_str)
                    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                        validation_status = "error"
                        error_msg = f"Coordenadas fora dos limites: lat={lat}, lon={lon}"
                    else:
                        coords = [lon, lat]
                except Exception:
                    validation_status = "error"
                    error_msg = f"Valores de coordenadas inválidos na linha {idx}"
        elif entity_type == "cable":
            geom_type = "LineString"
            # Coordenadas em CSV de cabos podem vir em campo 'coordinates' no formato "lon,lat;lon,lat"
            coords_str = clean_row.get("coordinates") or clean_row.get("coordenadas")
            if coords_str:
                try:
                    pts = []
                    for pt_str in coords_str.split(";"):
                        p_parts = pt_str.split(",")
                        lon, lat = sanitize_coord(p_parts[0]), sanitize_coord(p_parts[1])
                        pts.append([lon, lat])
                    if len(pts) < 2:
                        validation_status = "error"
                        error_msg = "Cabo deve ter pelo menos 2 pontos"
                    else:
                        coords = pts
                except Exception:
                    validation_status = "error"
                    error_msg = "Coordenadas do cabo inválidas"
            else:
                # Linha fictícia padrão se não informado
                coords = [[-46.6333, -23.5505], [-46.6334, -23.5506]]

        if not code and validation_status == "valid":
            validation_status = "error"
            error_msg = f"Coluna 'code' obrigatória ausente na linha {idx}"

        item_data = {
            "line_number": idx,
            "entity_type": entity_type,
            "code": code,
            "name": name,
            "geom_type": geom_type,
            "coords": coords,
            "props": clean_row,
            "validation_status": validation_status,
            "error_msg": error_msg,
        }
        parsed_items.append(item_data)
        preview_items.append(
            ImportPreviewItem(
                line_number=idx,
                entity_code=code,
                entity_type=entity_type,
                validation_status=validation_status,
                message=error_msg,
            )
        )

    return parsed_items, preview_items


def create_import_preview(
    db: Session,
    content: bytes,
    filename: str,
    user: User | None = None,
) -> ImportPreviewResponse:
    max_bytes = get_settings().MAX_IMPORT_SIZE_BYTES
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Arquivo de importação excede o tamanho máximo permitido de {max_bytes} bytes.",
        )

    import hashlib

    file_hash = hashlib.sha256(content).hexdigest()

    lower_name = filename.lower()
    if lower_name.endswith(".geojson") or lower_name.endswith(".json"):
        fmt = ImportFormat.GEOJSON
        parsed_items, preview_items = parse_geojson(content)
    elif lower_name.endswith(".kml") or lower_name.endswith(".kmz"):
        fmt = ImportFormat.KML
        parsed_items, preview_items = parse_kml(content)
    elif lower_name.endswith(".csv"):
        fmt = ImportFormat.CSV
        parsed_items, preview_items = parse_csv(content)
    else:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Formato de arquivo não suportado. Utilize .geojson, .kml, .kmz ou .csv.",
        )

    # Detecção de colisões contra o banco de dados
    valid_codes = [
        it["code"] for it in parsed_items if it["code"] and it["validation_status"] == "valid"
    ]

    existing_site_codes = (
        set(db.scalars(select(Site.code).where(Site.code.in_(valid_codes))).all())
        if valid_codes
        else set()
    )

    existing_struct_codes = (
        set(db.scalars(select(Structure.code).where(Structure.code.in_(valid_codes))).all())
        if valid_codes
        else set()
    )

    existing_cable_codes = (
        set(db.scalars(select(Cable.code).where(Cable.code.in_(valid_codes))).all())
        if valid_codes
        else set()
    )

    existing_all_codes = existing_site_codes | existing_struct_codes | existing_cable_codes

    collision_count = 0
    error_count = 0
    valid_count = 0

    for idx, it in enumerate(parsed_items):
        if it["validation_status"] == "error":
            error_count += 1
        elif it["code"] in existing_all_codes:
            it["validation_status"] = "collision"
            it["error_msg"] = f"Código '{it['code']}' já cadastrado no banco de dados"
            preview_items[idx].validation_status = "collision"
            preview_items[idx].message = it["error_msg"]
            collision_count += 1
        else:
            valid_count += 1

    # Salvar arquivo no armazenamento temporário de importações
    storage_dir = get_storage_path()
    storage_filename = f"{file_hash}_{filename}"
    file_storage_path = os.path.join(storage_dir, storage_filename)
    with open(file_storage_path, "wb") as f:
        f.write(content)

    # Metadados e rascunho com retenção de 24 horas
    preview = ImportPreview(
        file_hash=file_hash,
        format=fmt.value,
        total_records=len(parsed_items),
        valid_records=valid_count,
        error_records=error_count,
        collision_records=collision_count,
        sample_items=[item.model_dump() for item in preview_items[:50]],
        file_storage_path=file_storage_path,
        expires_at=datetime.now(UTC) + timedelta(hours=24),
        user_id=user.id if user else None,
    )
    db.add(preview)
    db.commit()
    db.refresh(preview)

    return ImportPreviewResponse(
        import_id=str(preview.id),
        file_hash=preview.file_hash,
        format=fmt,
        total_records=preview.total_records,
        valid_records=preview.valid_records,
        error_records=preview.error_records,
        collision_records=preview.collision_records,
        sample_preview=preview_items[:50],
    )


def get_preview_by_id(db: Session, import_id: str) -> ImportPreviewResponse:
    try:
        uid = uuid.UUID(import_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prévia de importação '{import_id}' não encontrada.",
        ) from None

    preview = db.get(ImportPreview, uid)
    if not preview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prévia de importação '{import_id}' não encontrada.",
        )

    if preview.expires_at < datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="A prévia de importação expirou (validade de 24 horas ultrapassada). Solicite uma nova prévia.",
        )

    return ImportPreviewResponse(
        import_id=str(preview.id),
        file_hash=preview.file_hash,
        format=ImportFormat(preview.format),
        total_records=preview.total_records,
        valid_records=preview.valid_records,
        error_records=preview.error_records,
        collision_records=preview.collision_records,
        sample_preview=[ImportPreviewItem(**it) for it in preview.sample_items],
    )


def commit_import_job(
    db: Session,
    import_id: str,
    payload: ImportCommitRequest,
    idempotency_key: str,
    user: User | None = None,
) -> ImportCommitResponse:
    # 1. Resposta idempotente estrita: se a chave já existe, retorna o mesmo job
    existing_job = db.scalar(select(AsyncJob).where(AsyncJob.idempotency_key == idempotency_key))
    if existing_job:
        return ImportCommitResponse(
            job_id=str(existing_job.id),
            message="Importação já registrada anteriormente para esta chave de idempotência.",
        )

    # 2. Validar prévia e integridade do hash
    try:
        uid = uuid.UUID(import_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prévia de importação '{import_id}' não encontrada.",
        ) from None

    preview = db.get(ImportPreview, uid)
    if not preview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prévia de importação '{import_id}' não encontrada.",
        )

    if preview.expires_at < datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="A prévia de importação expirou. Envie o arquivo novamente para gerar nova prévia.",
        )

    if preview.file_hash != payload.file_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O hash do arquivo enviado não corresponde ao arquivo da prévia aprovada.",
        )

    # 3. All-or-Nothing: não permite commit se houver erros ou colisões
    if preview.error_records > 0 or preview.collision_records > 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"O arquivo contém {preview.error_records} erros e {preview.collision_records} colisões. "
                "No modo All-or-Nothing, correções no arquivo são obrigatórias antes da gravação."
            ),
        )

    # 4. Criar job assíncrono na fila PostgreSQL
    job = AsyncJob(
        type="import_commit",
        status="queued",
        idempotency_key=idempotency_key,
        payload={
            "import_id": str(preview.id),
            "file_hash": preview.file_hash,
            "format": preview.format,
            "file_storage_path": preview.file_storage_path,
        },
        progress_percentage=0,
        user_id=user.id if user else None,
    )
    db.add(job)
    preview.committed_job = job
    db.commit()
    db.refresh(job)

    return ImportCommitResponse(
        job_id=str(job.id),
        message="Importação colocada na fila com sucesso",
    )
