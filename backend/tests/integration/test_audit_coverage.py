"""R10 (EST-10 / SEC-17): TODA rota mutante real grava exatamente 1 AuditEvent, com ator e request_id.

Um único roteiro (lifecycle) exercita cada rota mutante da API e confere, a cada chamada:
  - exatamente 1 novo evento na trilha;
  - `actor_id` do autor real e `request_id` igual ao X-Request-ID da resposta;
  - nenhum segredo/hash de senha na carga (`changes`).
Ao final, exige que TODAS as rotas mutantes do app (menos as exclusões justificadas) tenham sido
exercitadas — uma rota nova sem cobertura de auditoria faz o teste falhar.
"""

import io
import json
import uuid
from typing import Any

from fastapi import status
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.main import create_app
from app.modules.audit.models import AuditEvent
from app.modules.cables.models import Fiber
from app.modules.connectivity.models import Terminal
from app.modules.identity.models import User
from tests.conftest import DEFAULT_TEST_PASSWORD, create_test_user
from tests.route_utils import iter_api_routes

MUTATING = {"POST", "PUT", "PATCH", "DELETE"}

# Rotas mutantes que NÃO gravam evento, com o motivo
EXCLUDED: dict[tuple[str, str], str] = {
    ("POST", "/api/v1/topology/trace"): "cálculo somente-leitura (não altera dados)",
    ("POST", "/api/v1/topology/impact"): "cálculo somente-leitura (não altera dados)",
    ("POST", "/api/v1/optical/budgets"): "cálculo somente-leitura (não altera dados)",
    ("POST", "/api/v1/optical/simulations"): "cálculo somente-leitura (não altera dados)",
    ("POST", "/api/v1/cable-segments/{segment_id}/split/preview"): "pré-visualização sem gravação",
}

POINT_A = [-46.6330, -23.5500]
POINT_B = [-46.6340, -23.5510]
POINT_C = [-46.6350, -23.5520]


def point(coords: list[float]) -> dict[str, Any]:
    return {"type": "Point", "coordinates": coords}


def png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (10, 120, 200)).save(buf, format="PNG")
    return buf.getvalue()


class Tracker:
    def __init__(self, client: TestClient, db: Session, csrf: str, actor: User) -> None:
        self.client, self.db, self.csrf, self.actor = client, db, csrf, actor
        self.exercised: set[tuple[str, str]] = set()
        self.last_event: AuditEvent | None = None

    def count(self) -> int:
        self.db.expire_all()
        return int(self.db.scalar(select(func.count(AuditEvent.id))) or 0)

    def call(
        self,
        method: str,
        template: str,
        *,
        expect: int | tuple[int, ...] = (200, 201, 202, 204),
        json_body: Any = None,
        headers: dict[str, str] | None = None,
        actor: User | None = None,
        client: TestClient | None = None,
        csrf: str | None = None,
        events: int = 1,
        **kwargs: Any,
    ) -> Any:
        path_params = {k: v for k, v in kwargs.items() if "{" + k + "}" in template}
        request_kwargs = {k: v for k, v in kwargs.items() if k not in path_params}
        url = template.format(**path_params)
        expected = (expect,) if isinstance(expect, int) else expect
        client = client or self.client
        before = self.count()
        resp = client.request(
            method,
            url,
            json=json_body,
            headers={"X-CSRF-Token": csrf or self.csrf, **(headers or {})},
            **request_kwargs,
        )
        assert resp.status_code in expected, f"{method} {url} -> {resp.status_code}: {resp.text}"
        added = self.count() - before
        assert added == events, f"{method} {template}: {added} eventos (esperado {events})"

        if events:
            event = self.db.scalars(
                select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(1)
            ).one()
            expected_actor = actor or self.actor
            assert event.actor_id == expected_actor.id, f"{template}: ator {event.actor_id}"
            assert event.request_id, f"{template}: evento sem request_id"
            assert event.request_id == resp.headers["x-request-id"], f"{template}: request_id"
            payload = json.dumps(event.changes)
            assert "argon2" not in payload and DEFAULT_TEST_PASSWORD not in payload, template
            assert "password_hash" not in payload
            self.last_event = event
            self.exercised.add((method, template))
        return resp

    def etag(self, resp: Any) -> dict[str, str]:
        return {"If-Match": resp.headers["etag"]}


def test_every_mutating_route_writes_exactly_one_audit_event(
    client: TestClient, db_session: Session
) -> None:
    admin = create_test_user(db_session, "auditor@provedor.com.br", "admin")
    csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    tracker = Tracker(client, db_session, csrf, admin)

    # ---- auth: login (evento do próprio usuário) ------------------------------------------
    tracker.call(
        "POST",
        "/api/v1/auth/login",
        json_body={"email": admin.email, "password": DEFAULT_TEST_PASSWORD},
        csrf=csrf,
    )
    assert tracker.last_event is not None and tracker.last_event.action == "auth:login_succeeded"
    tracker.csrf = client.cookies["ftth_csrf_token"]  # token rotacionado no login

    # ---- sites -----------------------------------------------------------------------------
    resp = tracker.call(
        "POST",
        "/api/v1/sites",
        json_body={
            "code": "S-AUD",
            "name": "Site Auditoria",
            "kind": "pop",
            "location": point(POINT_A),
        },
    )
    site_id = resp.json()["id"]
    assert tracker.last_event is not None and tracker.last_event.action == "site:created"
    assert tracker.last_event.entity_id == uuid.UUID(site_id)
    resp = tracker.call(
        "PATCH",
        "/api/v1/sites/{site_id}",
        site_id=site_id,
        json_body={"name": "Site Auditoria 2"},
        headers={"If-Match": '"1"'},
    )
    assert tracker.last_event.changes["name"] == {
        "old": "Site Auditoria",
        "new": "Site Auditoria 2",
    }
    spare = tracker.call(
        "POST",
        "/api/v1/sites",
        json_body={
            "code": "S-SPARE",
            "name": "Descartável",
            "kind": "cabinet",
            "location": point(POINT_B),
        },
    )
    tracker.call(
        "DELETE", "/api/v1/sites/{site_id}", site_id=spare.json()["id"], headers={"If-Match": '"1"'}
    )
    assert tracker.last_event.action == "site:deleted"

    # ---- structures (postes A/C, CEO B, CTO) -----------------------------------------------
    def new_structure(code: str, kind: str, coords: list[float]) -> str:
        r = tracker.call(
            "POST",
            "/api/v1/structures",
            json_body={"code": code, "kind": kind, "location": point(coords), "site_id": site_id},
        )
        return str(r.json()["id"])

    st_a = new_structure("POSTE-A", "pole", POINT_A)
    st_b = new_structure("CEO-B", "ceo", POINT_B)
    st_c = new_structure("POSTE-C", "pole", POINT_C)
    st_cto = new_structure("CTO-AUD", "cto", [-46.6360, -23.5530])
    st_spare = new_structure("POSTE-SPARE", "pole", [-46.7, -23.6])
    tracker.call(
        "PATCH",
        "/api/v1/structures/{structure_id}",
        structure_id=st_a,
        json_body={"notes": "poste revisado"},
        headers={"If-Match": '"1"'},
    )
    tracker.call(
        "DELETE",
        "/api/v1/structures/{structure_id}",
        structure_id=st_spare,
        headers={"If-Match": '"1"'},
    )

    # ---- devices ---------------------------------------------------------------------------
    olt = tracker.call(
        "POST",
        "/api/v1/devices",
        json_body={
            "code": "OLT-AUD",
            "kind": "olt",
            "manufacturer": "Huawei",
            "model": "MA5800",
            "site_id": site_id,
        },
    ).json()["id"]
    onu = tracker.call(
        "POST",
        "/api/v1/devices",
        json_body={
            "code": "ONU-AUD",
            "kind": "onu",
            "manufacturer": "Huawei",
            "model": "EG8145",
            "structure_id": st_cto,
        },
    ).json()["id"]
    spare_dev = tracker.call(
        "POST",
        "/api/v1/devices",
        json_body={
            "code": "SW-SPARE",
            "kind": "switch",
            "manufacturer": "X",
            "model": "Y",
            "site_id": site_id,
        },
    ).json()["id"]
    tracker.call(
        "PATCH",
        "/api/v1/devices/{device_id}",
        device_id=olt,
        json_body={"notes": "olt principal"},
        headers={"If-Match": '"1"'},
    )
    tracker.call(
        "DELETE", "/api/v1/devices/{device_id}", device_id=spare_dev, headers={"If-Match": '"1"'}
    )

    # ---- ports -----------------------------------------------------------------------------
    tracker.call(
        "POST", "/api/v1/ports", json_body={"name": "PON-1", "role": "pon", "device_id": olt}
    )
    cto_port = tracker.call(
        "POST",
        "/api/v1/ports",
        json_body={"name": "P1", "role": "client_access", "structure_id": st_cto},
    ).json()["id"]
    spare_port = tracker.call(
        "POST",
        "/api/v1/ports",
        json_body={"name": "P9", "role": "client_access", "structure_id": st_cto},
    ).json()["id"]
    tracker.call(
        "PATCH",
        "/api/v1/ports/{port_id}",
        port_id=cto_port,
        json_body={"notes": "porta revisada"},
        headers={"If-Match": '"1"'},
    )
    tracker.call(
        "DELETE", "/api/v1/ports/{port_id}", port_id=spare_port, headers={"If-Match": '"1"'}
    )

    # ---- splitters -------------------------------------------------------------------------
    splitter = tracker.call(
        "POST",
        "/api/v1/splitters",
        json_body={
            "code": "SPL-AUD",
            "structure_id": st_b,
            "ratio": "1:2",
            "output_ports_count": 2,
        },
    )
    splitter_id = splitter.json()["id"]
    splitter = tracker.call(
        "PATCH",
        "/api/v1/splitters/{splitter_id}",
        splitter_id=splitter_id,
        json_body={"notes": "splitter revisado"},
        headers=tracker.etag(splitter),
    )
    tracker.call(
        "DELETE",
        "/api/v1/splitters/{splitter_id}",
        splitter_id=splitter_id,
        headers=tracker.etag(splitter),
    )

    # ---- cables / cable-segments -----------------------------------------------------------
    cable = tracker.call(
        "POST",
        "/api/v1/cables",
        json_body={"code": "CAB-AUD", "model": "CFOA-6F", "fiber_count": 6, "tube_count": 1},
    ).json()["id"]
    spare_cable = tracker.call(
        "POST",
        "/api/v1/cables",
        json_body={"code": "CAB-SPARE", "model": "CFOA-6F", "fiber_count": 6, "tube_count": 1},
    ).json()["id"]
    tracker.call(
        "PATCH",
        "/api/v1/cables/{cable_id}",
        cable_id=cable,
        json_body={"notes": "cabo revisado"},
        headers={"If-Match": '"1"'},
    )
    tracker.call(
        "DELETE", "/api/v1/cables/{cable_id}", cable_id=spare_cable, headers={"If-Match": '"1"'}
    )
    seg = tracker.call(
        "POST",
        "/api/v1/cable-segments",
        json_body={
            "cable_id": cable,
            "origin_structure_id": st_a,
            "destination_structure_id": st_c,
            "geometry": {"type": "LineString", "coordinates": [POINT_A, POINT_B, POINT_C]},
            "slack_length_m": 20.0,
        },
    ).json()["id"]
    assert tracker.last_event.entity_id == uuid.UUID(seg)
    assert tracker.last_event.changes.get("related"), "criação do segmento afeta fibras/terminais"
    tracker.call(
        "PATCH",
        "/api/v1/cable-segments/{segment_id}",
        segment_id=seg,
        json_body={"slack_length_m": 25.0},
        headers={"If-Match": '"1"'},
    )
    fibers = db_session.scalars(select(Fiber).where(Fiber.cable_id == uuid.UUID(cable))).all()
    split = tracker.call(
        "POST",
        "/api/v1/cable-segments/{segment_id}/split",
        segment_id=seg,
        json_body={
            "access_structure_id": st_b,
            "cut_fiber_ids": [str(fibers[0].id), str(fibers[1].id)],
            "segment_1_slack_m": 5.0,
            "segment_2_slack_m": 5.0,
        },
        headers={"If-Match": '"2"'},  # divisão exige If-Match: versão do trecho após o PATCH
    ).json()
    assert tracker.last_event.action == "cable_segment:split"
    tracker.call(
        "DELETE",
        "/api/v1/cable-segments/{segment_id}",
        segment_id=split["segment_2"]["id"],
        headers={"If-Match": '"1"'},
    )

    # ---- connections (terminais preparados direto no banco) --------------------------------
    ceo = uuid.UUID(st_b)
    terms = [
        Terminal(
            kind="fiber_endpoint",
            structure_id=ceo,
            label=f"T{i}",
            occupancy="free",
            is_occupied=False,
            version=1,
        )
        for i in range(6)
    ]
    db_session.add_all(terms)
    db_session.commit()
    conn = tracker.call(
        "POST",
        "/api/v1/connections",
        json_body={
            "terminal_a_id": str(terms[0].id),
            "terminal_b_id": str(terms[1].id),
            "connection_type": "fusion_splice",
            "loss_db": 0.05,
            "structure_id": st_b,
        },
    ).json()["id"]
    tracker.call(
        "DELETE",
        "/api/v1/connections/{connection_id}",
        connection_id=conn,
        headers={"If-Match": '"1"'},
    )
    revision = client.get(f"/api/v1/structures/{st_b}/connectivity").json()["topology_revision"]
    tracker.call(
        "POST",
        "/api/v1/connections/batch",
        json_body={
            "expected_topology_revision": revision,
            "structure_id": st_b,
            "operations": [
                {
                    "action": "connect",
                    "terminal_a_id": str(terms[2].id),
                    "terminal_b_id": str(terms[3].id),
                    "connection_type": "fusion_splice",
                    "loss_db": 0.08,
                },
                {
                    "action": "reserve",
                    "terminal_a_id": str(terms[4].id),
                    "reservation_reason": "reserva de teste",
                },
            ],
        },
    )

    # ---- customers / service-links ---------------------------------------------------------
    customer = tracker.call(
        "POST",
        "/api/v1/customers",
        json_body={"code": "CLI-AUD", "name": "Cliente Auditoria", "phone": "11999990000"},
    ).json()["id"]
    tracker.call(
        "PATCH",
        "/api/v1/customers/{customer_id}",
        customer_id=customer,
        json_body={"notes": "cliente revisado"},
        headers={"If-Match": '"1"'},
    )
    link = tracker.call(
        "POST",
        "/api/v1/service-links",
        json_body={"customer_id": customer, "onu_device_id": onu, "port_id": cto_port},
    ).json()["id"]
    tracker.call(
        "PATCH",
        "/api/v1/service-links/{link_id}",
        link_id=link,
        json_body={"notes": "atendimento revisado"},
        headers={"If-Match": '"1"'},
    )
    tracker.call(
        "DELETE", "/api/v1/service-links/{link_id}", link_id=link, headers={"If-Match": '"2"'}
    )
    # (cliente com atendimento no histórico não pode ser excluído: usa um sem vínculos)
    spare_customer = tracker.call(
        "POST", "/api/v1/customers", json_body={"code": "CLI-SPARE", "name": "Sem vínculos"}
    ).json()["id"]
    tracker.call(
        "DELETE",
        "/api/v1/customers/{customer_id}",
        customer_id=spare_customer,
        headers={"If-Match": '"1"'},
    )

    # ---- measurements ----------------------------------------------------------------------
    meas = tracker.call(
        "POST",
        "/api/v1/measurements",
        json_body={"terminal_id": str(terms[5].id), "power_dbm": -20.5, "wavelength_nm": 1490},
    ).json()["id"]
    tracker.call(
        "PATCH",
        "/api/v1/measurements/{measurement_id}",
        measurement_id=meas,
        json_body={"notes": "medição revisada"},
        headers={"If-Match": '"1"'},
    )
    tracker.call(
        "DELETE",
        "/api/v1/measurements/{measurement_id}",
        measurement_id=meas,
        headers={"If-Match": '"2"'},
    )

    # ---- optical-profiles ------------------------------------------------------------------
    profile = tracker.call(
        "POST",
        "/api/v1/optical-profiles",
        json_body={
            "name": "GPON B+ auditoria",
            "wavelength_nm": 1490,
            "tx_min_dbm": 1.5,
            "tx_max_dbm": 5.0,
            "rx_sensitivity_dbm": -28.0,
            "rx_overload_dbm": -8.0,
        },
    ).json()["id"]
    tracker.call(
        "PATCH",
        "/api/v1/optical-profiles/{profile_id}",
        profile_id=profile,
        json_body={"notes": "perfil revisado"},
        headers={"If-Match": '"1"'},
    )
    tracker.call(
        "DELETE",
        "/api/v1/optical-profiles/{profile_id}",
        profile_id=profile,
        headers={"If-Match": '"2"'},
    )

    # ---- attachments -----------------------------------------------------------------------
    att = tracker.call(
        "POST",
        "/api/v1/attachments",
        data={"entity_id": site_id, "entity_type": "site"},
        files={"file": ("foto.png", io.BytesIO(png_bytes()), "image/png")},
    ).json()["id"]
    tracker.call(
        "DELETE",
        "/api/v1/attachments/{attachment_id}",
        attachment_id=att,
        headers={"If-Match": '"1"'},
    )
    tracker.call("POST", "/api/v1/attachments/reconcile-orphans", params={"dry_run": "false"})
    assert tracker.last_event.action == "storage:reconciled"

    # ---- imports / exports / jobs ----------------------------------------------------------
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": point([-46.9, -23.9]),
                "properties": {
                    "code": "POP-IMP",
                    "name": "POP Importado",
                    "type": "pop",
                    "entity_type": "site",
                },
            }
        ],
    }
    preview = tracker.call(
        "POST",
        "/api/v1/imports/preview",
        files={
            "file": (
                "rede.geojson",
                io.BytesIO(json.dumps(geojson).encode()),
                "application/geo+json",
            )
        },
    ).json()
    tracker.call(
        "POST",
        "/api/v1/imports/{import_id}/commit",
        import_id=preview["import_id"],
        json_body={"import_id": preview["import_id"], "file_hash": preview["file_hash"]},
        headers={"Idempotency-Key": f"idem-{uuid.uuid4()}"},
    )
    export_job = tracker.call(
        "POST", "/api/v1/exports", json_body={"format": "geojson", "layers": ["sites"]}
    ).json()["job_id"]
    tracker.call("POST", "/api/v1/jobs/{job_id}/cancel", job_id=export_job)

    # ---- configurações ---------------------------------------------------------------------
    tracker.call(
        "PATCH",
        "/api/v1/settings",
        json_body={"organization_name": "Operação Auditada"},
        headers={"If-Match": '"1"'},
    )

    # ---- users -----------------------------------------------------------------------------
    created = tracker.call(
        "POST",
        "/api/v1/users",
        json_body={
            "name": "Novo Usuário",
            "email": "novo@provedor.com.br",
            "password": "SenhaInicial123!",
            "role": "viewer",
        },
    )
    assert tracker.last_event.action == "user:created"
    user_id = created.json()["id"]
    upd = tracker.call(
        "PATCH",
        "/api/v1/users/{user_id}",
        user_id=user_id,
        json_body={"role": "technician"},
        headers=tracker.etag(created),
    )
    assert tracker.last_event.action == "user:role_changed"
    tracker.call("DELETE", "/api/v1/users/{user_id}", user_id=user_id, headers=tracker.etag(upd))
    assert tracker.last_event.action == "user:deactivated"

    # ---- auth: change-password e logout do próprio usuário ---------------------------------
    other = create_test_user(db_session, "rotina@provedor.com.br", "viewer")
    other_client = TestClient(create_app(), raise_server_exceptions=False)
    other_csrf = other_client.get("/api/v1/auth/csrf").json()["csrf_token"]
    tracker.call(
        "POST",
        "/api/v1/auth/login",
        client=other_client,
        actor=other,
        csrf=other_csrf,
        json_body={"email": other.email, "password": DEFAULT_TEST_PASSWORD},
    )
    other_csrf = other_client.cookies["ftth_csrf_token"]
    tracker.call(
        "POST",
        "/api/v1/auth/change-password",
        client=other_client,
        actor=other,
        csrf=other_csrf,
        json_body={"current_password": DEFAULT_TEST_PASSWORD, "new_password": "OutraSenha456!"},
    )
    assert tracker.last_event.action == "auth:password_changed"
    tracker.call("POST", "/api/v1/auth/logout", client=other_client, actor=other, csrf=other_csrf)
    assert tracker.last_event.action == "auth:logout"

    # ---- login falho também é auditado (sem a senha) ---------------------------------------
    bad_csrf = other_client.get("/api/v1/auth/csrf").json()["csrf_token"]
    before = tracker.count()
    resp = other_client.post(
        "/api/v1/auth/login",
        json={"email": other.email, "password": "senha-errada-secreta"},
        headers={"X-CSRF-Token": bad_csrf},
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert tracker.count() - before == 1
    failed = db_session.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc())).first()
    assert failed is not None and failed.action == "auth:login_failed"
    assert "senha-errada-secreta" not in json.dumps(failed.changes)

    # ---- cobertura: toda rota mutante real foi exercitada ou está excluída -----------------
    all_mutating = {
        (method, route.path)
        for route in iter_api_routes(create_app())
        for method in route.methods
        if method in MUTATING
    }
    missing = all_mutating - tracker.exercised - set(EXCLUDED)
    assert not missing, "Rotas mutantes sem cobertura de auditoria:\n" + "\n".join(
        f"{m} {p}" for m, p in sorted(missing)
    )
    stale = set(EXCLUDED) - all_mutating
    assert not stale, f"Exclusões obsoletas: {sorted(stale)}"
    # sanidade: o roteiro não deixou tudo de fora
    assert len(tracker.exercised) >= 49


def test_failed_mutation_writes_no_audit_event(client: TestClient, db_session: Session) -> None:
    """Rollback/erro de negócio não deixa evento (o evento vive na mesma transação)."""
    admin = create_test_user(db_session, "auditor2@provedor.com.br", "admin")
    csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": DEFAULT_TEST_PASSWORD},
        headers={"X-CSRF-Token": csrf},
    )
    token = client.cookies["ftth_csrf_token"]
    body = {"code": "S-DUP", "name": "Dup", "kind": "pop", "location": point(POINT_A)}
    first = client.post("/api/v1/sites", json=body, headers={"X-CSRF-Token": token})
    assert first.status_code == status.HTTP_201_CREATED

    db_session.expire_all()
    before = db_session.scalar(select(func.count(AuditEvent.id)))
    dup = client.post("/api/v1/sites", json=body, headers={"X-CSRF-Token": token})
    assert dup.status_code == status.HTTP_409_CONFLICT
    db_session.expire_all()
    assert db_session.scalar(select(func.count(AuditEvent.id))) == before


def test_audit_event_is_append_only_at_database_level(db_session: Session) -> None:
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    event = AuditEvent(
        actor_name="t", action="x:y", entity_type="site", entity_id=uuid.uuid4(), changes={}
    )
    db_session.add(event)
    db_session.commit()

    for statement in (
        "UPDATE audit_events SET action = 'adulterado'",
        "DELETE FROM audit_events",
    ):
        try:
            db_session.execute(text(statement))
            db_session.commit()
            raise AssertionError(f"{statement!r} deveria ser bloqueado pelo banco")
        except DBAPIError as err:
            db_session.rollback()
            assert "append-only" in str(err.orig)

    assert db_session.scalar(select(func.count(AuditEvent.id))) == 1
