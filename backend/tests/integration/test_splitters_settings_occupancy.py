import uuid

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.connectivity.models import Connection, Terminal, TerminalReservation
from app.modules.customers.models import Customer, ServiceLink
from app.modules.inventory.models import Device
from app.modules.topology.models import NetworkTopologyState
from tests.conftest import create_test_user, login_test_client


def _create_structure(client: TestClient, csrf: str, code: str = "CTO-SPL-01") -> str:
    response = client.post(
        "/api/v1/structures",
        json={
            "code": code,
            "kind": "cto",
            "location": {"type": "Point", "coordinates": [-46.6333, -23.5505]},
            "capacity": 16,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return str(response.json()["id"])


def _losses(count: int, base: float = 10.5) -> list[dict[str, float | int]]:
    return [
        {
            "port_number": number,
            "loss_1310_db": base + number / 100,
            "loss_1490_db": base + number / 100,
            "loss_1550_db": base + number / 100,
        }
        for number in range(1, count + 1)
    ]


def test_splitter_crud_creates_optical_terminals_and_updates_topology(
    client: TestClient, db_session: Session
) -> None:
    create_test_user(db_session, "splitter-admin@provedor.com.br", "admin")
    csrf = login_test_client(client, "splitter-admin@provedor.com.br")
    structure_id = _create_structure(client, csrf)
    revision_before = db_session.get(NetworkTopologyState, 1)
    assert revision_before is not None
    old_revision = revision_before.topology_revision

    create_response = client.post(
        "/api/v1/splitters",
        json={
            "code": "spl-cto-01",
            "structure_id": structure_id,
            "ratio": "1:8",
            "output_ports_count": 8,
            "ports": _losses(8),
            "notes": "Splitter principal",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert create_response.status_code == status.HTTP_201_CREATED, create_response.text
    created = create_response.json()
    splitter_id = created["id"]
    assert created["code"] == "SPL-CTO-01"
    assert created["structure_id"] == structure_id
    assert created["output_ports_count"] == 8
    assert len(created["ports"]) == 9
    assert created["ports"][0]["is_input"] is True
    assert create_response.headers["etag"] == '"1"'

    db_session.expire_all()
    assert (
        db_session.scalar(
            select(func.count(Terminal.id)).where(Terminal.entity_id == uuid.UUID(splitter_id))
        )
        == 9
    )
    revision_after = db_session.get(NetworkTopologyState, 1)
    assert revision_after is not None and revision_after.topology_revision == old_revision + 1

    list_response = client.get(f"/api/v1/splitters?structure_id={structure_id}")
    assert list_response.status_code == status.HTTP_200_OK
    assert list_response.json()["total"] == 1

    duplicate = client.post(
        "/api/v1/splitters",
        json={
            "code": "SPL-CTO-01",
            "structure_id": structure_id,
            "ratio": "1:2",
            "output_ports_count": 2,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert duplicate.status_code == status.HTTP_409_CONFLICT
    assert duplicate.json()["code"] == "code_already_exists"

    update_response = client.patch(
        f"/api/v1/splitters/{splitter_id}",
        json={"notes": "Perdas aferidas", "ports": _losses(8, 11.0)},
        headers={"X-CSRF-Token": csrf, "If-Match": '"1"'},
    )
    assert update_response.status_code == status.HTTP_200_OK, update_response.text
    assert update_response.json()["version"] == 2
    assert update_response.json()["ports"][1]["loss_1490_db"] == 11.01
    assert update_response.headers["etag"] == '"2"'

    stale_response = client.patch(
        f"/api/v1/splitters/{splitter_id}",
        json={"notes": "versão antiga"},
        headers={"X-CSRF-Token": csrf, "If-Match": '"1"'},
    )
    assert stale_response.status_code == status.HTTP_412_PRECONDITION_FAILED

    delete_response = client.delete(
        f"/api/v1/splitters/{splitter_id}",
        headers={"X-CSRF-Token": csrf, "If-Match": '"2"'},
    )
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT, delete_response.text
    db_session.expire_all()
    assert (
        db_session.scalar(
            select(func.count(Terminal.id)).where(Terminal.entity_id == uuid.UUID(splitter_id))
        )
        == 0
    )

    device_response = client.post(
        "/api/v1/devices",
        json={
            "code": "DIO-SPL-01",
            "kind": "dio",
            "manufacturer": "FiberHome",
            "model": "DIO-24",
            "structure_id": structure_id,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert device_response.status_code == status.HTTP_201_CREATED
    device_splitter = client.post(
        "/api/v1/splitters",
        json={
            "code": "SPL-DIO-01",
            "device_id": device_response.json()["id"],
            "ratio": "1:2",
            "output_ports_count": 2,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert device_splitter.status_code == status.HTTP_201_CREATED, device_splitter.text
    assert device_splitter.json()["device_id"] == device_response.json()["id"]
    assert device_splitter.json()["structure_id"] == structure_id
    other_structure_id = _create_structure(client, csrf, "CTO-SPL-02")
    move_device = client.patch(
        f"/api/v1/devices/{device_response.json()['id']}",
        json={"structure_id": other_structure_id},
        headers={"X-CSRF-Token": csrf, "If-Match": '"1"'},
    )
    assert move_device.status_code == status.HTTP_409_CONFLICT
    assert move_device.json()["code"] == "device_has_splitters"


def test_app_settings_are_persistent_versioned_and_validate_timezone(
    client: TestClient, db_session: Session
) -> None:
    create_test_user(db_session, "settings-admin@provedor.com.br", "admin")
    csrf = login_test_client(client, "settings-admin@provedor.com.br")

    initial = client.get("/api/v1/settings")
    assert initial.status_code == status.HTTP_200_OK
    assert initial.headers["etag"] == '"1"'
    assert initial.json()["organization_name"] == "Operação FTTH"
    assert initial.json()["default_map_center"] == [-53.0, -30.0]
    assert initial.json()["default_map_zoom"] == 7

    missing_if_match = client.patch(
        "/api/v1/settings",
        json={"organization_name": "Rede Regional"},
        headers={"X-CSRF-Token": csrf},
    )
    assert missing_if_match.status_code == status.HTTP_428_PRECONDITION_REQUIRED

    invalid_timezone = client.patch(
        "/api/v1/settings",
        json={"timezone": "Marte/Olympus_Mons"},
        headers={"X-CSRF-Token": csrf, "If-Match": '"1"'},
    )
    assert invalid_timezone.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert invalid_timezone.json()["code"] == "invalid_timezone"

    updated = client.patch(
        "/api/v1/settings",
        json={
            "organization_name": "Rede Regional",
            "timezone": "America/Fortaleza",
            "default_map_center": [-38.5267, -3.7319],
            "default_map_zoom": 16,
            "excess_loss_tolerance_db": 1.5,
        },
        headers={"X-CSRF-Token": csrf, "If-Match": '"1"'},
    )
    assert updated.status_code == status.HTTP_200_OK, updated.text
    assert updated.headers["etag"] == '"2"'
    assert updated.json()["version"] == 2

    persisted = client.get("/api/v1/settings")
    assert persisted.json()["organization_name"] == "Rede Regional"
    assert persisted.json()["default_map_center"] == [-38.5267, -3.7319]


def test_structure_occupancy_reports_connected_reserved_damaged_and_free_ports(
    client: TestClient, db_session: Session
) -> None:
    create_test_user(db_session, "occupancy-admin@provedor.com.br", "admin")
    csrf = login_test_client(client, "occupancy-admin@provedor.com.br")
    structure_id = _create_structure(client, csrf, "CTO-OCC-01")

    port_ids: list[uuid.UUID] = []
    for number, notes in ((1, None), (2, None), (3, "Porta danificada"), (4, None)):
        response = client.post(
            "/api/v1/ports",
            json={
                "name": f"Porta {number:02d}",
                "role": "client_access",
                "structure_id": structure_id,
                "notes": notes,
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == status.HTTP_201_CREATED
        port_ids.append(uuid.UUID(response.json()["id"]))

    structure_uuid = uuid.UUID(structure_id)
    terminals = [
        Terminal(
            kind="port_front",
            structure_id=structure_uuid,
            label=f"Porta {number:02d}",
            entity_type="port",
            entity_id=port_id,
            occupancy="free",
            version=1,
        )
        for number, port_id in enumerate(port_ids[:3], start=1)
    ]
    peer = Terminal(
        kind="fiber_end",
        structure_id=structure_uuid,
        label="Fibra de entrada",
        entity_type="test",
        entity_id=uuid.uuid4(),
        occupancy="connected",
        version=1,
    )
    db_session.add_all([*terminals, peer])
    db_session.flush()
    db_session.add(
        Connection(
            terminal_a_id=terminals[0].id,
            terminal_b_id=peer.id,
            connection_type="fusion",
            loss_db=0.1,
            structure_id=structure_uuid,
            is_active=True,
            version=1,
        )
    )
    db_session.add(
        TerminalReservation(
            terminal_id=terminals[1].id,
            reason="Instalação agendada",
            is_active=True,
            version=1,
        )
    )
    customer = Customer(code="CLI-OCC-01", name="Cliente Ocupação", version=1)
    onu = Device(
        code="ONU-OCC-01",
        kind="onu",
        manufacturer="FiberHome",
        model="ONU-1GE",
        structure_id=structure_uuid,
        status="installed",
        condition="ok",
        version=1,
    )
    db_session.add_all([customer, onu])
    db_session.flush()
    db_session.add(
        ServiceLink(
            customer_id=customer.id,
            onu_device_id=onu.id,
            port_id=port_ids[3],
            status="active",
            version=1,
        )
    )
    db_session.commit()

    response = client.get(f"/api/v1/structures/{structure_id}/occupancy")
    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json() == {
        "structure_id": structure_id,
        "code": "CTO-OCC-01",
        "kind": "cto",
        "total_ports": 4,
        "connected_ports": 2,
        "reserved_ports": 1,
        "free_ports": 0,
        "damaged_ports": 1,
    }
