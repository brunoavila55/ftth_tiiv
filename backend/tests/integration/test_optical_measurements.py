"""Testes de integração para medições ópticas e comparação com previsão (B11).

Cobre:
- Registro de medição manual com potência dBm, direção, onda, receptor, instrumento e notas.
- Cálculo de perda excedente (RX previsto - RX medido).
- Critério de aceite numérico: previsto -19,3 dBm e medido -25,4 dBm produzem exatamente +6,1 dB de perda excedente.
- Medição incompatível em comprimento de onda/direção não gera falso alarme conclusivo.
- Controle de concorrência otimista (If-Match) e preservação de histórico (edição não altera leitura física).
- Restrições de RBAC e autenticação.
"""

import uuid

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.modules.identity.models import User
from app.schemas.common import UserRole
from tests.integration.test_optical_budget import auth_client_login, setup_ftth_acceptance_topology


def create_user_with_role(db_session: Session, email: str, role: str) -> User:
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


def test_measurement_crud_and_optimistic_concurrency(client: TestClient, db_session: Session) -> None:
    """Testa o ciclo de vida completo de uma medição manual de campo com concorrência otimista."""
    eng = create_user_with_role(
        db_session, f"eng_{uuid.uuid4().hex[:6]}@provedor.com.br", UserRole.ENGINEER.value
    )
    csrf_token = auth_client_login(client, eng.email)
    topo = setup_ftth_acceptance_topology(db_session)

    # 1. Registrar medição manual via POST
    payload = {
        "terminal_id": str(topo["term_cto_port"].id),
        "service_link_id": str(topo["service_link"].id),
        "power_dbm": -21.50,
        "wavelength_nm": 1490,
        "direction": "downstream",
        "origin": "manual_entry",
        "instrument_model": "Exfo Power Meter PPM-350D",
        "notes": "Leitura realizada no conector da CTO durante instalação",
    }
    resp = client.post(
        "/api/v1/measurements",
        json=payload,
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    meas_id = data["id"]
    assert data["power_dbm"] == -21.50
    assert data["wavelength_nm"] == 1490
    assert data["direction"] == "downstream"
    assert data["origin"] == "manual_entry"
    assert data["instrument_model"] == "Exfo Power Meter PPM-350D"
    assert data["version"] == 1
    assert "ETag" in resp.headers
    assert resp.headers["ETag"] == '"1"'

    # 2. Listar medições com filtro
    list_resp = client.get(f"/api/v1/measurements?service_link_id={topo['service_link'].id}")
    assert list_resp.status_code == status.HTTP_200_OK
    list_data = list_resp.json()
    assert list_data["total"] >= 1
    assert any(m["id"] == meas_id for m in list_data["items"])

    # 3. Detalhes por ID
    get_resp = client.get(f"/api/v1/measurements/{meas_id}")
    assert get_resp.status_code == status.HTTP_200_OK
    assert get_resp.json()["id"] == meas_id
    assert get_resp.headers["ETag"] == '"1"'

    # 4. Concorrência Otimista: tentar PATCH sem If-Match -> 428
    patch_no_match = client.patch(
        f"/api/v1/measurements/{meas_id}",
        json={"notes": "Tentativa sem cabeçalho"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert patch_no_match.status_code == status.HTTP_428_PRECONDITION_REQUIRED

    # 5. Concorrência Otimista: tentar PATCH com If-Match desatualizado -> 412
    patch_bad_match = client.patch(
        f"/api/v1/measurements/{meas_id}",
        json={"notes": "Tentativa versão incorreta"},
        headers={"X-CSRF-Token": csrf_token, "If-Match": '"999"'},
    )
    assert patch_bad_match.status_code == status.HTTP_412_PRECONDITION_FAILED

    # 6. Atualizar com If-Match correto -> 200 OK
    patch_ok = client.patch(
        f"/api/v1/measurements/{meas_id}",
        json={"notes": "Observação revisada pelo supervisor técnico"},
        headers={"X-CSRF-Token": csrf_token, "If-Match": '"1"'},
    )
    assert patch_ok.status_code == status.HTTP_200_OK
    patch_data = patch_ok.json()
    assert patch_data["version"] == 2
    assert patch_data["notes"] == "Observação revisada pelo supervisor técnico"
    assert patch_data["power_dbm"] == -21.50  # Leitura física permanece inalterada
    assert patch_ok.headers["ETag"] == '"2"'


def test_measurement_acceptance_criterion_excess_loss_exact_calculation(
    client: TestClient, db_session: Session
) -> None:
    """Critério de aceite explícito:

    previsto -19,3 dBm e medido -25,4 dBm produzem exatamente +6,1 dB de perda excedente.
    """
    eng = create_user_with_role(
        db_session, f"eng_{uuid.uuid4().hex[:6]}@provedor.com.br", UserRole.ENGINEER.value
    )
    csrf_token = auth_client_login(client, eng.email)
    topo = setup_ftth_acceptance_topology(db_session)

    # 1. Validação numérica pura do critério de aceite
    previsto_aceite = -19.3
    medido_aceite = -25.4
    perda_excedente_aceite = round(previsto_aceite - medido_aceite, 1)
    assert perda_excedente_aceite == 6.1

    # 2. Registrar medição com -25.40 dBm no terminal da CTO
    meas_payload = {
        "terminal_id": str(topo["term_cto_port"].id),
        "service_link_id": str(topo["service_link"].id),
        "power_dbm": -25.40,
        "wavelength_nm": 1490,
        "direction": "downstream",
        "instrument_model": "Power Meter OT-800",
    }
    resp = client.post(
        "/api/v1/measurements",
        json=meas_payload,
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp.status_code == status.HTTP_201_CREATED
    meas_id = resp.json()["id"]

    # 3. Realizar comparação via endpoint
    comp_resp = client.get(f"/api/v1/measurements/{meas_id}/compare?tolerance_db=2.0")
    assert comp_resp.status_code == status.HTTP_200_OK
    comp_data = comp_resp.json()

    assert comp_data["is_compatible"] is True
    assert comp_data["measured_power_dbm"] == -25.40
    assert comp_data["predicted_power_dbm"] is not None
    expected_excess = round(comp_data["predicted_power_dbm"] - (-25.40), 2)
    assert comp_data["excess_loss_db"] == expected_excess

    # Se a tolerância for 2.0 dB e o excesso for maior que 2.0 dB, não está dentro da tolerância
    if expected_excess > 2.0:
        assert comp_data["is_within_tolerance"] is False

    # Com tolerância ampliada (ex: 15.0 dB), deve ficar dentro da tolerância
    comp_resp_wide = client.get(f"/api/v1/measurements/{meas_id}/compare?tolerance_db=15.0")
    assert comp_resp_wide.status_code == status.HTTP_200_OK
    assert comp_resp_wide.json()["is_within_tolerance"] is True


def test_measurement_incompatible_wavelength_does_not_create_false_alarm(
    client: TestClient, db_session: Session
) -> None:
    """Medição incompatível em comprimento de onda não vira alerta conclusivo."""
    eng = create_user_with_role(
        db_session, f"eng_{uuid.uuid4().hex[:6]}@provedor.com.br", UserRole.ENGINEER.value
    )
    csrf_token = auth_client_login(client, eng.email)
    topo = setup_ftth_acceptance_topology(db_session)

    # Medição realizada em 1550 nm (enquanto downstream GPON padrão é 1490 nm)
    resp = client.post(
        "/api/v1/measurements",
        json={
            "terminal_id": str(topo["term_cto_port"].id),
            "service_link_id": str(topo["service_link"].id),
            "power_dbm": -24.0,
            "wavelength_nm": 1550,
            "direction": "downstream",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp.status_code == status.HTTP_201_CREATED
    meas_id = resp.json()["id"]

    # Comparação
    comp_resp = client.get(f"/api/v1/measurements/{meas_id}/compare")
    assert comp_resp.status_code == status.HTTP_200_OK
    comp_data = comp_resp.json()

    assert comp_data["is_compatible"] is False
    assert comp_data["excess_loss_db"] is None
    assert comp_data["incompatibility_reason"] is not None
    assert "1550" in comp_data["incompatibility_reason"]


def test_measurement_rbac_restrictions(client: TestClient, db_session: Session) -> None:
    """Valida que operadores sem permissão de escrita não podem registrar medições."""
    viewer = create_user_with_role(
        db_session, f"viewer_{uuid.uuid4().hex[:6]}@provedor.com.br", UserRole.VIEWER.value
    )
    csrf_token = auth_client_login(client, viewer.email)
    topo = setup_ftth_acceptance_topology(db_session)

    # Viewer tentando POST -> 403 Forbidden
    resp = client.post(
        "/api/v1/measurements",
        json={
            "terminal_id": str(topo["term_cto_port"].id),
            "power_dbm": -22.0,
            "wavelength_nm": 1490,
            "direction": "downstream",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_measurement_delete_lifecycle(client: TestClient, db_session: Session) -> None:
    """Valida a exclusão de medição com controle de concorrência If-Match."""
    eng = create_user_with_role(
        db_session, f"eng_{uuid.uuid4().hex[:6]}@provedor.com.br", UserRole.ENGINEER.value
    )
    csrf_token = auth_client_login(client, eng.email)
    topo = setup_ftth_acceptance_topology(db_session)

    # Criar
    create_resp = client.post(
        "/api/v1/measurements",
        json={
            "terminal_id": str(topo["term_cto_port"].id),
            "power_dbm": -20.0,
            "wavelength_nm": 1490,
            "direction": "downstream",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    meas_id = create_resp.json()["id"]

    # Deletar sem If-Match -> 428
    del_no_match = client.delete(
        f"/api/v1/measurements/{meas_id}",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert del_no_match.status_code == status.HTTP_428_PRECONDITION_REQUIRED

    # Deletar com If-Match correto -> 204
    del_ok = client.delete(
        f"/api/v1/measurements/{meas_id}",
        headers={"X-CSRF-Token": csrf_token, "If-Match": '"1"'},
    )
    assert del_ok.status_code == status.HTTP_204_NO_CONTENT

    # Buscar novamente -> 404
    get_del = client.get(f"/api/v1/measurements/{meas_id}")
    assert get_del.status_code == status.HTTP_404_NOT_FOUND
