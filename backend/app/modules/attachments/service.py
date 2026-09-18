import contextlib
import hashlib
import io
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.attachments.models import Attachment
from app.modules.audit.service import record_audit_event
from app.modules.cables.models import Cable
from app.modules.connectivity.models import Terminal
from app.modules.customers.models import Customer, ServiceLink
from app.modules.inventory.models import Device, Site, Structure
from app.modules.measurements.models import OpticalMeasurement
from app.schemas.attachments import AttachmentRead, AttachmentReconciliationResponse

# Assinaturas de cabeçalhos binários (magic numbers) suportados
MAGIC_SIGNATURES = {
    "image/jpeg": (b"\xff\xd8\xff", ".jpg"),
    "image/png": (b"\x89PNG\r\n\x1a\n", ".png"),
    "application/pdf": (b"%PDF", ".pdf"),
}

# Assinaturas proibidas ativas (HTML/SVG/Scripts)
DANGEROUS_SNIPPETS = [
    b"<svg",
    b"<?xml",
    b"<html",
    b"<script",
    b"<!doctype html",
    b"javascript:",
    b"<body",
    b"<iframe",
]


def sanitize_filename(filename: str) -> str:
    """Sanitiza o nome original de arquivo removendo caminhos e caracteres perigosos."""
    normalized = filename.replace("\\", "/")
    raw_name = Path(normalized).name.strip()
    clean = raw_name.replace("..", "_")
    safe_name = re.sub(r"[^\w\s\.-]", "_", clean)
    safe_name = re.sub(r"\.{2,}", "_", safe_name)
    return safe_name[:255].strip(" ._") or "unnamed_attachment"


def inspect_file_content(content: bytes) -> tuple[str, str]:
    """Inspeciona os magic bytes e valida se o formato é estritamente permitido.

    Retorna tupla (mime_type_validado, extensao_padronizada).
    Lança HTTPException 422 em caso de assinatura desconhecida ou conteúdo perigoso.
    """
    settings = get_settings()
    if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Arquivo excede o limite máximo permitido de {settings.MAX_UPLOAD_SIZE_BYTES} bytes",
        )

    if len(content) < 4:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Arquivo binário truncado ou inválido",
        )

    # Detecção de scripts ou HTML/SVG ativo
    sample_prefix = content[:1024].lower()
    for snippet in DANGEROUS_SNIPPETS:
        if snippet in sample_prefix:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Conteúdo rejeitado por segurança: SVG, scripts ou HTML não são permitidos como anexo",
            )

    # Verificação de WebP: RIFF....WEBP
    if content.startswith(b"RIFF") and len(content) >= 12 and content[8:12] == b"WEBP":
        return "image/webp", ".webp"

    # Verificação de JPEG, PNG e PDF
    for mime_type, (magic_bytes, ext) in MAGIC_SIGNATURES.items():
        if content.startswith(magic_bytes):
            return mime_type, ext

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Formato de arquivo não suportado. Formatos aceitos: JPEG, PNG, WebP e PDF.",
    )


def get_storage_directories() -> tuple[Path, Path]:
    """Obtém e assegura a existência dos diretórios físicos de originais e miniaturas."""
    settings = get_settings()
    base_dir = Path(settings.STORAGE_PATH).resolve() / "attachments"
    originals_dir = base_dir / "originals"
    thumbnails_dir = base_dir / "thumbnails"

    originals_dir.mkdir(parents=True, exist_ok=True)
    thumbnails_dir.mkdir(parents=True, exist_ok=True)

    return originals_dir, thumbnails_dir


def generate_thumbnail_image(content: bytes, mime_type: str) -> bytes | None:
    """Gera miniatura redimensionada e reencodificada de forma segura para imagens."""
    if mime_type not in ("image/jpeg", "image/png", "image/webp"):
        return None

    try:
        with Image.open(io.BytesIO(content)) as img:
            # Converte modo para RGB caso seja CMYK ou outro incompatível com WebP
            if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                thumb_img = img.convert("RGBA")
            else:
                thumb_img = img.convert("RGB")

            thumb_img.thumbnail((300, 300), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            thumb_img.save(output, format="WEBP", quality=80, method=6)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError):
        return None


def validate_entity_exists(db: Session, entity_type: str, entity_id: uuid.UUID) -> None:
    """Valida se a entidade proprietária do anexo existe no banco de dados."""
    type_clean = entity_type.lower().strip()

    entity_model_map: dict[str, Any] = {
        "site": Site,
        "pop": Site,
        "structure": Structure,
        "device": Device,
        "cable": Cable,
        "terminal": Terminal,
        "customer": Customer,
        "service_link": ServiceLink,
        "optical_measurement": OpticalMeasurement,
    }

    model = entity_model_map.get(type_clean)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Tipo de entidade '{entity_type}' não suportado para anexos",
        )

    exists = db.scalar(select(model.id).where(model.id == entity_id).limit(1))
    if not exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entidade '{entity_type}' com ID {entity_id} não encontrada",
        )


def build_attachment_read(attachment: Attachment) -> AttachmentRead:
    """Monta a representação do anexo com URLs de download autorizado."""
    download_url = f"/api/v1/attachments/{attachment.id}/download"
    thumbnail_url = (
        f"/api/v1/attachments/{attachment.id}/thumbnail" if attachment.thumbnail_path else None
    )

    return AttachmentRead(
        id=str(attachment.id),
        entity_id=str(attachment.entity_id),
        entity_type=attachment.entity_type,
        file_name=attachment.file_name,
        mime_type=attachment.content_type,
        file_size_bytes=attachment.file_size_bytes,
        download_url=download_url,
        thumbnail_url=thumbnail_url,
        caption=attachment.caption,
        checksum_sha256=attachment.checksum_sha256,
        user_id=str(attachment.user_id) if attachment.user_id else None,
        version=attachment.version,
        created_at=attachment.created_at,
    )


def save_attachment(
    db: Session,
    *,
    entity_id: uuid.UUID,
    entity_type: str,
    raw_content: bytes,
    original_filename: str,
    caption: str | None = None,
    user_id: uuid.UUID | None = None,
    user_name: str = "Sistema",
    request_id: str | None = None,
) -> AttachmentRead:
    """Processa upload, valida integridade física, salva no disco persistente e registra DB e auditoria."""
    # 1. Validar entidade existente
    validate_entity_exists(db, entity_type, entity_id)

    # 2. Inspecionar conteúdo e magic bytes
    mime_type, ext = inspect_file_content(raw_content)

    # 3. Gerar hash SHA-256 e sanitizar nome
    sha256_hash = hashlib.sha256(raw_content).hexdigest()
    safe_name = sanitize_filename(original_filename)

    # 4. Gerar UUID para isolamento de arquivos no disco (anti path traversal)
    file_id = uuid.uuid4()
    storage_filename = f"{file_id.hex}{ext}"
    originals_dir, thumbnails_dir = get_storage_directories()

    original_target_path = originals_dir / storage_filename
    original_target_path.write_bytes(raw_content)

    # 5. Gerar miniatura se imagem
    thumbnail_rel_path: str | None = None
    thumb_bytes = generate_thumbnail_image(raw_content, mime_type)
    if thumb_bytes:
        thumb_filename = f"{file_id.hex}.webp"
        thumb_target_path = thumbnails_dir / thumb_filename
        thumb_target_path.write_bytes(thumb_bytes)
        thumbnail_rel_path = f"thumbnails/{thumb_filename}"

    # 6. Gravar metadados no banco
    attachment = Attachment(
        id=file_id,
        entity_id=entity_id,
        entity_type=entity_type.lower().strip(),
        file_name=safe_name,
        content_type=mime_type,
        file_size_bytes=len(raw_content),
        storage_path=f"originals/{storage_filename}",
        thumbnail_path=thumbnail_rel_path,
        checksum_sha256=sha256_hash,
        caption=caption.strip() if caption else None,
        user_id=user_id,
    )
    db.add(attachment)

    # 7. Registrar evento de auditoria append-only na mesma transação
    record_audit_event(
        db,
        actor_id=user_id,
        actor_name=user_name,
        action="ATTACHMENT_UPLOAD",
        entity_type=entity_type,
        entity_id=entity_id,
        changes={
            "attachment_id": str(file_id),
            "file_name": safe_name,
            "content_type": mime_type,
            "file_size_bytes": len(raw_content),
            "checksum_sha256": sha256_hash,
            "caption": caption,
        },
        reason="Upload de anexo/foto documental",
        request_id=request_id,
    )

    db.commit()
    db.refresh(attachment)

    return build_attachment_read(attachment)


def get_attachment_by_id(db: Session, attachment_id: uuid.UUID) -> Attachment:
    """Busca registro de anexo no banco ou retorna 404."""
    attachment = db.scalar(select(Attachment).where(Attachment.id == attachment_id))
    if not attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Anexo com ID {attachment_id} não encontrado",
        )
    return attachment


def resolve_attachment_file_path(attachment: Attachment, is_thumbnail: bool = False) -> Path:
    """Resolve e valida caminho absoluto do arquivo no disco com proteção de path traversal."""
    settings = get_settings()
    base_dir = Path(settings.STORAGE_PATH).resolve() / "attachments"

    rel_path = attachment.thumbnail_path if is_thumbnail else attachment.storage_path
    if not rel_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Arquivo ou miniatura não disponível para este anexo",
        )

    file_path = (base_dir / rel_path).resolve()

    # Prevenção estrita de path traversal: deve estar dentro de base_dir
    if not str(file_path).startswith(str(base_dir)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso a caminho de arquivo não autorizado",
        )

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Arquivo físico persistente não encontrado no armazenamento",
        )

    return file_path


def list_attachments_paginated(
    db: Session,
    *,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Attachment], int]:
    """Lista anexos filtrados por entidade com paginação."""
    query = select(Attachment)

    if entity_type:
        query = query.where(Attachment.entity_type == entity_type.lower().strip())
    if entity_id:
        query = query.where(Attachment.entity_id == entity_id)

    from sqlalchemy import func

    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0

    query = query.order_by(Attachment.created_at.desc()).offset(offset).limit(limit)
    items = list(db.scalars(query).all())

    return items, total


def delete_attachment(
    db: Session,
    *,
    attachment_id: uuid.UUID,
    expected_version: int,
    user_id: uuid.UUID | None = None,
    user_name: str = "Sistema",
    request_id: str | None = None,
) -> None:
    """Exclui metadados e arquivos físicos de anexo com concorrência otimista e auditoria."""
    attachment = get_attachment_by_id(db, attachment_id)

    if attachment.version != expected_version:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=f"Conflito de versão: o anexo está na versão {attachment.version}, esperado {expected_version}",
        )

    # Identificar caminhos físicos antes de remover do banco
    settings = get_settings()
    base_dir = Path(settings.STORAGE_PATH).resolve() / "attachments"
    orig_path = (base_dir / attachment.storage_path).resolve()
    thumb_path = (
        (base_dir / attachment.thumbnail_path).resolve() if attachment.thumbnail_path else None
    )

    entity_id = attachment.entity_id
    entity_type = attachment.entity_type
    file_name = attachment.file_name

    # Registrar evento de auditoria
    record_audit_event(
        db,
        actor_id=user_id,
        actor_name=user_name,
        action="ATTACHMENT_DELETE",
        entity_type=entity_type,
        entity_id=entity_id,
        changes={
            "attachment_id": str(attachment_id),
            "file_name": file_name,
            "version": attachment.version,
        },
        reason="Exclusão manual de anexo",
        request_id=request_id,
    )

    db.delete(attachment)
    db.commit()

    # Remover arquivos físicos do disco
    if orig_path.exists() and orig_path.is_file():
        with contextlib.suppress(OSError):
            orig_path.unlink()

    if thumb_path and thumb_path.exists() and thumb_path.is_file():
        with contextlib.suppress(OSError):
            thumb_path.unlink()


def reconcile_storage_orphans(db: Session, dry_run: bool = False) -> AttachmentReconciliationResponse:
    """Reconcilia arquivos órfãos no disco e registros sem arquivo físico sem excluir anexos válidos."""
    originals_dir, thumbnails_dir = get_storage_directories()
    settings = get_settings()
    base_dir = Path(settings.STORAGE_PATH).resolve() / "attachments"

    # Buscar todos os caminhos cadastrados no banco
    db_attachments = db.scalars(select(Attachment)).all()
    known_relative_paths: set[str] = set()
    for a in db_attachments:
        known_relative_paths.add(a.storage_path)
        if a.thumbnail_path:
            known_relative_paths.add(a.thumbnail_path)

    total_db_records = len(db_attachments)

    # Varrer arquivos físicos em disco
    disk_files: list[Path] = []
    for directory in (originals_dir, thumbnails_dir):
        if directory.exists():
            for entry in directory.iterdir():
                if entry.is_file():
                    disk_files.append(entry)

    total_disk_files = len(disk_files)
    orphans_removed: list[str] = []
    missing_disk_files: list[str] = []

    # Detectar órfãos (arquivos em disco não cadastrados no banco)
    for f in disk_files:
        try:
            rel = str(f.relative_to(base_dir))
        except ValueError:
            continue

        if rel not in known_relative_paths:
            orphans_removed.append(rel)
            if not dry_run:
                with contextlib.suppress(OSError):
                    f.unlink()

    # Detectar registros cujos arquivos sumiram do disco
    for a in db_attachments:
        orig_file = base_dir / a.storage_path
        if not orig_file.exists():
            missing_disk_files.append(f"{a.id}: {a.storage_path}")

    return AttachmentReconciliationResponse(
        total_disk_files=total_disk_files,
        total_db_records=total_db_records,
        orphans_removed=orphans_removed,
        missing_disk_files=missing_disk_files,
    )
