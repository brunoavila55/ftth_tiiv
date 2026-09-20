"""R04 (SEC-03 / SEC-04): dados pessoais de clientes exigem `customers:read|write`.

- viewer/technician não acessam /customers, /service-links (nem via cto-occupancy);
- anexos de cliente/vínculo exigem customers:read (e :write para enviar/excluir);
- a trilha de auditoria não revela phone/email/address a quem não tem customers:read;
- toda permissão declarada na matriz é exigida por ao menos uma rota.
"""

import io
import uuid

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.permissions import ROLE_PERMISSIONS
from app.main import create_app
from app.modules.attachments.models import Attachment
from app.modules.audit.models import AuditEvent
from app.modules.customers.models import Customer
from app.modules.inventory.models import Site
from tests.conftest import create_test_user, login_test_client
from tests.route_utils import iter_api_routes, required_permissions

RANDOM_ID = "00000000-0000-4000-8000-000000000001"

CUSTOMER_ROUTES: list[tuple[str, str]] = [
    ("GET", "/api/v1/customers"),
    ("POST", "/api/v1/customers"),
    ("GET", f"/api/v1/customers/{RANDOM_ID}"),
    ("PATCH", f"/api/v1/customers/{RANDOM_ID}"),
    ("DELETE", f"/api/v1/customers/{RANDOM_ID}"),
    ("GET", "/api/v1/service-links"),
    ("POST", "/api/v1/service-links"),
    ("GET", f"/api/v1/service-links/{RANDOM_ID}"),
    ("PATCH", f"/api/v1/service-links/{RANDOM_ID}"),
    ("DELETE", f"/api/v1/service-links/{RANDOM_ID}"),
]


def _login(client: TestClient, db: Session, role: str) -> str:
    email = f"{role}_{uuid.uuid4().hex[:6]}@provedor.com.br"
    create_test_user(db, email, role)
    return login_test_client(client, email)


def _call(client: TestClient, method: str, url: str, csrf: str) -> int:
    kwargs: dict[str, object] = {"headers": {"X-CSRF-Token": csrf, "If-Match": "1"}}
    if method in ("POST", "PATCH"):
        kwargs["json"] = {}
    return client.request(method, url, **kwargs).status_code  # type: ignore[arg-type]


@pytest.mark.parametrize("role", ["viewer", "technician"])
def test_customer_and_service_link_routes_forbidden_without_customers_permission(
    client: TestClient, db_session: Session, role: str
) -> None:
    csrf = _login(client, db_session, role)
    for method, url in CUSTOMER_ROUTES:
        code = _call(client, method, url, csrf)
        assert code == status.HTTP_403_FORBIDDEN, f"{role} {method} {url} -> {code}"


def test_engineer_keeps_access_to_customers(client: TestClient, db_session: Session) -> None:
    csrf = _login(client, db_session, "engineer")
    assert _call(client, "GET", "/api/v1/customers", csrf) == status.HTTP_200_OK
    assert _call(client, "GET", "/api/v1/service-links", csrf) == status.HTTP_200_OK


def _seed_customer_and_site_attachments(db: Session) -> tuple[Attachment, Attachment, Attachment]:
    customer = Customer(code="CLI-PII-1", name="Fulano de Tal", phone="11999990000", version=1)
    site = Site(
        code="SITE-PII", name="Site", kind="pop", status="installed", location="POINT(-46 -23)"
    )
    db.add_all([customer, site])
    db.commit()

    def att(entity_type: str, entity_id: uuid.UUID) -> Attachment:
        return Attachment(
            entity_type=entity_type,
            entity_id=entity_id,
            file_name="f.pdf",
            content_type="application/pdf",
            file_size_bytes=10,
            storage_path="x/f.pdf",
            checksum_sha256="0" * 64,
            version=1,
        )

    a_cust = att("customer", customer.id)
    a_link = att("service_link", uuid.uuid4())
    a_site = att("site", site.id)
    db.add_all([a_cust, a_link, a_site])
    db.commit()
    for a in (a_cust, a_link, a_site):
        db.refresh(a)
    return a_cust, a_link, a_site


def test_technician_cannot_access_customer_attachments(
    client: TestClient, db_session: Session
) -> None:
    a_cust, a_link, a_site = _seed_customer_and_site_attachments(db_session)
    csrf = _login(client, db_session, "technician")

    # Listagem: itens de cliente/vínculo nunca aparecem; os demais sim
    listing = client.get("/api/v1/attachments")
    assert listing.status_code == status.HTTP_200_OK
    ids = {item["id"] for item in listing.json()["items"]}
    assert str(a_site.id) in ids
    assert str(a_cust.id) not in ids and str(a_link.id) not in ids
    assert listing.json()["total"] == 1

    # Filtro explícito por tipo protegido → 403
    for et in ("customer", "service_link"):
        assert client.get(f"/api/v1/attachments?entity_type={et}").status_code == 403

    for att in (a_cust, a_link):
        for suffix in ("", "/download", "/thumbnail"):
            resp = client.get(f"/api/v1/attachments/{att.id}{suffix}")
            assert resp.status_code == status.HTTP_403_FORBIDDEN, (att.entity_type, suffix)

    # Anexo de site continua acessível (metadados)
    assert client.get(f"/api/v1/attachments/{a_site.id}").status_code == status.HTTP_200_OK

    # Upload e exclusão de anexo de cliente exigem customers:write
    up = client.post(
        "/api/v1/attachments",
        data={"entity_id": str(a_cust.entity_id), "entity_type": "customer"},
        files={"file": ("a.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        headers={"X-CSRF-Token": csrf},
    )
    assert up.status_code == status.HTTP_403_FORBIDDEN
    dele = client.delete(
        f"/api/v1/attachments/{a_cust.id}", headers={"X-CSRF-Token": csrf, "If-Match": "1"}
    )
    assert dele.status_code == status.HTTP_403_FORBIDDEN


def test_engineer_can_access_customer_attachments(client: TestClient, db_session: Session) -> None:
    a_cust, a_link, a_site = _seed_customer_and_site_attachments(db_session)
    _login(client, db_session, "engineer")

    listing = client.get("/api/v1/attachments")
    assert listing.json()["total"] == 3
    assert client.get(f"/api/v1/attachments/{a_cust.id}").status_code == status.HTTP_200_OK
    assert client.get(f"/api/v1/attachments/{a_link.id}").status_code == status.HTTP_200_OK


PII = {"phone": "11999990000", "email": "fulano@example.com", "address": "Rua das Flores, 10"}


def _seed_audit_events(db: Session) -> None:
    db.add(
        AuditEvent(
            actor_name="Eng",
            action="customer:updated",
            entity_type="customer",
            entity_id=uuid.uuid4(),
            changes={
                **PII,
                "name": "Fulana Sigilosa",
                "notes": "endereço alternativo para entrega",
                "nested": {"before": {"phone": PII["phone"]}},
            },
        )
    )
    db.add(
        AuditEvent(
            actor_name="Eng",
            action="service_link:updated",
            entity_type="service_link",
            entity_id=uuid.uuid4(),
            changes={"address": PII["address"], "status": "active"},
        )
    )
    db.add(
        AuditEvent(
            actor_name="Eng",
            action="site:updated",
            entity_type="site",
            entity_id=uuid.uuid4(),
            changes={"name": "Site Central", "notes": "manutenção preventiva"},
        )
    )
    db.commit()


def test_audit_events_mask_pii_for_users_without_customers_read(
    client: TestClient, db_session: Session
) -> None:
    """name/notes só identificam pessoa em eventos de customer/service_link: mascarados aí, mas
    preservados em outras entidades (ex.: nome/notas de um site) — não é dado pessoal."""
    _seed_audit_events(db_session)
    _login(client, db_session, "technician")
    resp = client.get("/api/v1/audit-events")
    assert resp.status_code == status.HTTP_200_OK
    body = resp.text
    for value in PII.values():
        assert value not in body
    assert "Fulana Sigilosa" not in body
    assert "endereço alternativo para entrega" not in body
    items = resp.json()["items"]
    cust_evt = next(i for i in items if i["entity_type"] == "customer")
    assert cust_evt["changes"]["phone"] == "[REDACTED]"
    assert cust_evt["changes"]["name"] == "[REDACTED]"
    assert cust_evt["changes"]["notes"] == "[REDACTED]"
    assert cust_evt["changes"]["nested"]["before"]["phone"] == "[REDACTED]"
    link_evt = next(i for i in items if i["entity_type"] == "service_link")
    assert link_evt["changes"] == {"address": "[REDACTED]", "status": "active"}
    site_evt = next(i for i in items if i["entity_type"] == "site")
    assert site_evt["changes"] == {"name": "Site Central", "notes": "manutenção preventiva"}


def test_audit_events_show_pii_to_customers_readers(
    client: TestClient, db_session: Session
) -> None:
    _seed_audit_events(db_session)
    _login(client, db_session, "engineer")
    resp = client.get("/api/v1/audit-events")
    assert PII["phone"] in resp.text and PII["address"] in resp.text
    assert "Fulana Sigilosa" in resp.text


@pytest.mark.parametrize(
    ("role", "sees_customer"), [("viewer", False), ("technician", False), ("engineer", True)]
)
def test_cto_occupancy_hides_customer_data_without_customers_read(
    client: TestClient, db_session: Session, role: str, sees_customer: bool
) -> None:
    from datetime import UTC, datetime

    from app.modules.customers.models import ServiceLink
    from tests.integration.test_customers_service_links import (
        create_test_cto,
        create_test_onu,
        create_test_ports,
    )

    cto = create_test_cto(db_session, "CTO-PII-01")
    ports = create_test_ports(db_session, cto, 2)
    onu = create_test_onu(db_session, "ONU-PII-01", cto)
    customer = Customer(
        code="CLI-PII-9", name="Fulana Sigilosa", phone=PII["phone"], email=PII["email"], version=1
    )
    db_session.add(customer)
    db_session.commit()
    db_session.add(
        ServiceLink(
            customer_id=customer.id,
            onu_device_id=onu.id,
            port_id=ports[0].id,
            status="active",
            activated_at=datetime.now(UTC),
            notes="contrato com anotação pessoal",
            version=1,
        )
    )
    db_session.commit()

    _login(client, db_session, role)
    resp = client.get(f"/api/v1/structures/{cto.id}/cto-occupancy")
    assert resp.status_code == status.HTTP_200_OK
    occupied = next(p for p in resp.json()["ports"] if p["status"] == "customer_connected")
    if sees_customer:
        assert occupied["customer"]["name"] == "Fulana Sigilosa"
    else:
        assert occupied["customer"] is None
        assert occupied["service_link"]["notes"] is None
        for value in ("Fulana Sigilosa", PII["phone"], PII["email"], "CLI-PII-9"):
            assert value not in resp.text


def test_every_declared_permission_is_required_by_some_route() -> None:
    declared = set().union(*ROLE_PERMISSIONS.values())
    used: set[str] = set()
    for route in iter_api_routes(create_app()):
        used |= required_permissions(route.dependant)

    unused = declared - used
    assert not unused, f"Permissões declaradas mas nunca exigidas por rota: {sorted(unused)}"
