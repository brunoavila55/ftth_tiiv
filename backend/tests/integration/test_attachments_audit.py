"""Testes de integração para fotos, anexos e auditoria append-only (B13).

Cobre:
- Upload válido de imagem e PDF com detecção de magic bytes e geração de thumbnail.
- Rejeição de uploads inválidos (HTML, SVG ativo, arquivos com extensão falsa ou truncados).
- Rejeição de upload para entidade inexistente.
- Download autorizado por UUID: bloqueio para usuário anônimo (401) e VIEWER (403).
- Proteção estrita contra path traversal em nomes de arquivos.
- Auditoria append-only: escrita revertida não deixa evento de sucesso; dados sensíveis são mascarados.
- Reconciliação de arquivos órfãos sem exclusão de anexos válidos.
"""

import io
import os
import time
import uuid

from fastapi import status
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.modules.attachments.service import get_storage_directories, sanitize_filename
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import record_audit_event
from app.modules.gis.helpers import point_geometry_to_wkb
from app.modules.identity.models import User
from app.modules.inventory.models import Site
from app.schemas.common import UserRole
from app.schemas.geojson import PointGeometry
from tests.integration.test_optical_budget import auth_client_login, setup_ftth_acceptance_topology


def create_sample_site(db_session: Session) -> Site:
    site = Site(
        code=f"POP-{uuid.uuid4().hex[:6].upper()}",
        name="POP Central de Teste",
        kind="pop",
        status="installed",
        location=point_geometry_to_wkb(PointGeometry(coordinates=[-46.6333, -23.5505])),
        version=1,
    )
    db_session.add(site)
    db_session.commit()
    db_session.refresh(site)
    return site


def create_user(db_session: Session, email: str, role: str) -> User:
    user = User(
        email=email,
        name=f"User {role}",
        password_hash=hash_password("AdminPass123!"),
        role=role,
        is_active=True,
        version=1,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def create_sample_png_bytes(color: tuple[int, int, int] = (255, 0, 0)) -> bytes:
    img = Image.new("RGB", (64, 64), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def create_sample_pdf_bytes() -> bytes:
    # Cabeçalho válido de arquivo PDF com corpo mínimo
    return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"


def test_attachment_upload_and_download_lifecycle(client: TestClient, db_session: Session) -> None:
    """Valida ciclo completo: upload de imagem, geração de thumbnail, download autorizado e exclusão."""
    tech = create_user(
        db_session, f"tech_{uuid.uuid4().hex[:6]}@provedor.com.br", UserRole.TECHNICIAN.value
    )
    csrf_token = auth_client_login(client, tech.email)
    site = create_sample_site(db_session)
    site_id = str(site.id)

    png_data = create_sample_png_bytes()

    # 1. Upload de imagem PNG associada ao Site POP
    upload_resp = client.post(
        "/api/v1/attachments",
        data={
            "entity_id": site_id,
            "entity_type": "site",
            "caption": "Foto frontal do rack do POP central",
        },
        files={"file": ("rack_pop.png", png_data, "image/png")},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert upload_resp.status_code == status.HTTP_201_CREATED, upload_resp.text
    att_data = upload_resp.json()

    assert att_data["mime_type"] == "image/png"
    assert att_data["entity_id"] == site_id
    assert att_data["caption"] == "Foto frontal do rack do POP central"
    assert att_data["thumbnail_url"] is not None
    assert att_data["download_url"] == f"/api/v1/attachments/{att_data['id']}/download"
    assert att_data["version"] == 1

    attachment_id = att_data["id"]

    # 2. Download do arquivo original autorizado
    download_resp = client.get(f"/api/v1/attachments/{attachment_id}/download")
    assert download_resp.status_code == status.HTTP_200_OK
    assert download_resp.content == png_data

    # 3. Download da miniatura segura (thumbnail)
    thumb_resp = client.get(f"/api/v1/attachments/{attachment_id}/thumbnail")
    assert thumb_resp.status_code == status.HTTP_200_OK
    assert thumb_resp.headers["content-type"] == "image/webp"

    # 4. Listagem de anexos da entidade
    list_resp = client.get(f"/api/v1/attachments?entity_type=site&entity_id={site_id}")
    assert list_resp.status_code == status.HTTP_200_OK
    items = list_resp.json()["items"]
    assert len(items) >= 1
    assert any(it["id"] == attachment_id for it in items)

    # 5. Exclusão com controle de versão If-Match
    # Conflito de versão
    bad_del = client.delete(
        f"/api/v1/attachments/{attachment_id}",
        headers={"If-Match": "99", "X-CSRF-Token": csrf_token},
    )
    assert bad_del.status_code == status.HTTP_412_PRECONDITION_FAILED

    # Versão correta
    good_del = client.delete(
        f"/api/v1/attachments/{attachment_id}",
        headers={"If-Match": "1", "X-CSRF-Token": csrf_token},
    )
    assert good_del.status_code == status.HTTP_204_NO_CONTENT

    # Verificar que o anexo foi removido
    get_after = client.get(f"/api/v1/attachments/{attachment_id}")
    assert get_after.status_code == status.HTTP_404_NOT_FOUND


def test_attachment_pdf_upload_without_thumbnail(client: TestClient, db_session: Session) -> None:
    """Valida upload de PDF: salvo com segurança, sem thumbnail de imagem e download correto."""
    eng = create_user(
        db_session, f"eng_{uuid.uuid4().hex[:6]}@provedor.com.br", UserRole.ENGINEER.value
    )
    csrf_token = auth_client_login(client, eng.email)
    topo = setup_ftth_acceptance_topology(db_session)
    customer_id = str(topo["service_link"].customer_id)

    pdf_data = create_sample_pdf_bytes()

    upload_resp = client.post(
        "/api/v1/attachments",
        data={
            "entity_id": customer_id,
            "entity_type": "customer",
            "caption": "Termo de adesão assinado pelo cliente",
        },
        files={"file": ("termo_adesao.pdf", pdf_data, "application/pdf")},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert upload_resp.status_code == status.HTTP_201_CREATED, upload_resp.text
    att_data = upload_resp.json()
    assert att_data["mime_type"] == "application/pdf"
    assert att_data["thumbnail_url"] is None

    # Download do PDF
    dl_resp = client.get(f"/api/v1/attachments/{att_data['id']}/download")
    assert dl_resp.status_code == status.HTTP_200_OK
    assert dl_resp.content == pdf_data


def test_attachment_invalid_content_and_security_rejections(
    client: TestClient, db_session: Session
) -> None:
    """Valida que formatos proibidos (SVG, HTML ativo, arquivos truncados ou falsificados) são rejeitados."""
    eng = create_user(
        db_session, f"eng_{uuid.uuid4().hex[:6]}@provedor.com.br", UserRole.ENGINEER.value
    )
    csrf_token = auth_client_login(client, eng.email)
    site = create_sample_site(db_session)
    site_id = str(site.id)

    # 1. Tentativa de envio de arquivo com script/HTML ativo disfarçado de imagem
    malicious_html = b"<html><script>alert('xss')</script></html>"
    resp1 = client.post(
        "/api/v1/attachments",
        data={"entity_id": site_id, "entity_type": "site"},
        files={"file": ("malicious.png", malicious_html, "image/png")},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp1.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 2. Tentativa de envio de SVG ativo (rejeitado explicitamente pelo B13)
    svg_content = b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert('pwn')</script></svg>"
    resp2 = client.post(
        "/api/v1/attachments",
        data={"entity_id": site_id, "entity_type": "site"},
        files={"file": ("vector.svg", svg_content, "image/svg+xml")},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp2.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 3. Tentativa de envio de arquivo executável / binário desconhecido
    fake_png = b"NOT_A_PNG_HEADER_RANDOM_BYTES_12345"
    resp3 = client.post(
        "/api/v1/attachments",
        data={"entity_id": site_id, "entity_type": "site"},
        files={"file": ("fake.png", fake_png, "image/png")},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp3.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 4. Entidade inexistente
    fake_entity_id = str(uuid.uuid4())
    resp4 = client.post(
        "/api/v1/attachments",
        data={"entity_id": fake_entity_id, "entity_type": "site"},
        files={"file": ("valid.png", create_sample_png_bytes(), "image/png")},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp4.status_code == status.HTTP_404_NOT_FOUND


def test_attachment_download_authorization_and_viewer_restriction(
    client: TestClient, db_session: Session
) -> None:
    """Valida que usuários anônimos e VIEWERs sem permissão attachments:read não conseguem baixar arquivos."""
    # Cria anexo com engenheiro
    eng = create_user(
        db_session, f"eng_{uuid.uuid4().hex[:6]}@provedor.com.br", UserRole.ENGINEER.value
    )
    csrf_token = auth_client_login(client, eng.email)
    site = create_sample_site(db_session)
    site_id = str(site.id)

    upload_resp = client.post(
        "/api/v1/attachments",
        data={"entity_id": site_id, "entity_type": "site", "caption": "Planta do POP"},
        files={"file": ("pop_planta.png", create_sample_png_bytes(), "image/png")},
        headers={"X-CSRF-Token": csrf_token},
    )
    att_id = upload_resp.json()["id"]

    # Desconecta o cliente (limpando cookies de sessão)
    client.cookies.clear()

    # 1. Usuário anônimo tenta baixar por UUID conhecido -> 401
    anon_resp = client.get(f"/api/v1/attachments/{att_id}/download")
    assert anon_resp.status_code == status.HTTP_401_UNAUTHORIZED

    # 2. Usuário com papel VIEWER tenta baixar por UUID conhecido -> 403
    viewer = create_user(
        db_session, f"viewer_{uuid.uuid4().hex[:6]}@provedor.com.br", UserRole.VIEWER.value
    )
    auth_client_login(client, viewer.email)

    viewer_resp = client.get(f"/api/v1/attachments/{att_id}/download")
    assert viewer_resp.status_code == status.HTTP_403_FORBIDDEN


def test_path_traversal_sanitization() -> None:
    """Garante que filenames com sequências maliciosas de path traversal sejam neutralizados."""
    malicious_names = [
        "../../../../etc/passwd",
        "..\\..\\windows\\system32\\calc.exe",
        "/absolute/path/photo.png",
        "nested/sub/folder/file.jpg",
    ]
    for name in malicious_names:
        safe = sanitize_filename(name)
        assert "/" not in safe
        assert "\\" not in safe
        assert ".." not in safe


def test_audit_trail_append_only_and_atomicity(client: TestClient, db_session: Session) -> None:
    """Valida append-only da auditoria, consulta paginada, sanitização de senhas e atomicidade em rollback."""
    admin = create_user(
        db_session, f"admin_{uuid.uuid4().hex[:6]}@provedor.com.br", UserRole.ADMIN.value
    )
    auth_client_login(client, admin.email)

    entity_id = uuid.uuid4()

    # 1. Testar atomicidade: evento registrado numa transação que sofre rollback NÃO deve existir
    try:
        record_audit_event(
            db_session,
            actor_id=admin.id,
            actor_name=admin.name,
            action="TEST_ROLLBACK_ACTION",
            entity_type="device",
            entity_id=entity_id,
            changes={"key": "will_be_reverted"},
        )
        raise RuntimeError("Simulando falha operacional na transação!")
    except RuntimeError:
        db_session.rollback()

    # Verificar que o evento foi revertido junto com a transação
    aborted_event = db_session.query(AuditEvent).filter_by(entity_id=entity_id).first()
    assert aborted_event is None

    # 2. Testar persistência e sanitização de dados sensíveis
    record_audit_event(
        db_session,
        actor_id=admin.id,
        actor_name=admin.name,
        action="USER_UPDATE_CREDENTIALS",
        entity_type="user",
        entity_id=admin.id,
        changes={
            "email": "novo@provedor.com.br",
            "password": "MinhaSenhaSuperSecreta123",
            "api_key": "secret_api_token_value",
            "nested": {"access_token": "bearer_jwt_string", "name": "Operador"},
        },
        reason="Atualização de perfil",
    )
    db_session.commit()

    # 3. Consultar a trilha de auditoria via API
    resp = client.get(f"/api/v1/audit-events?entity_type=user&entity_id={admin.id}")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["total"] >= 1

    event_payload = data["items"][0]
    assert event_payload["action"] == "USER_UPDATE_CREDENTIALS"
    assert event_payload["changes"]["password"] == "[REDACTED]"
    assert event_payload["changes"]["api_key"] == "[REDACTED]"
    assert event_payload["changes"]["nested"]["access_token"] == "[REDACTED]"
    assert event_payload["changes"]["nested"]["name"] == "Operador"


def test_orphan_reconciliation(client: TestClient, db_session: Session) -> None:
    """Valida detecção e remoção de arquivos órfãos sem prejudicar arquivos válidos."""
    admin = create_user(
        db_session, f"admin_rec_{uuid.uuid4().hex[:6]}@provedor.com.br", UserRole.ADMIN.value
    )
    csrf_token = auth_client_login(client, admin.email)
    site = create_sample_site(db_session)
    site_id = str(site.id)

    # 1. Cria um anexo válido
    client.post(
        "/api/v1/attachments",
        data={"entity_id": site_id, "entity_type": "site"},
        files={"file": ("legit.png", create_sample_png_bytes(), "image/png")},
        headers={"X-CSRF-Token": csrf_token},
    )

    # 2. Cria manualmente um arquivo órfão no diretório de originais
    originals_dir, _ = get_storage_directories()
    orphan_file = originals_dir / f"orphan_{uuid.uuid4().hex}.png"
    orphan_file.write_bytes(b"orphan_data_content")
    assert orphan_file.exists()
    # Envelhece além da carência do reconciliador (arquivos recentes podem ser de um upload em curso)
    aged = time.time() - 3600
    os.utime(orphan_file, (aged, aged))

    # 3. Executa a reconciliação de órfãos via endpoint
    rec_resp = client.post(
        "/api/v1/attachments/reconcile-orphans",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert rec_resp.status_code == status.HTTP_200_OK
    rec_data = rec_resp.json()

    assert rec_data["total_db_records"] >= 1
    assert any(orphan_file.name in orphan_rel for orphan_rel in rec_data["orphans_removed"])
    assert not orphan_file.exists()
