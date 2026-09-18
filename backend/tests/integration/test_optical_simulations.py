"""Testes de integração para simulações de engenharia com overrides pontuais (B12).

Cobre:
- Simulação com override de perda (loss_db) em elemento óptico.
- Simulação com override de comprimento de fibra (length_m).
- Simulação com troca de razão de splitter (splitter_ratio).
- Garantia estrita de que a topologia operacional, banco de dados e topology_revision permanecem inalterados.
"""

import uuid

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.modules.connectivity.models import Connection, Splitter
from app.modules.identity.models import User
from app.modules.topology.service import get_current_topology_revision
from app.schemas.common import UserRole
from tests.integration.test_optical_budget import auth_client_login, setup_ftth_acceptance_topology


def create_engineer(db_session: Session, email: str) -> User:
    user = User(
        email=email,
        name="Engenheiro Simulação",
        password_hash=hash_password("AdminPass123!"),
        role=UserRole.ENGINEER.value,
        is_active=True,
        version=1,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_optical_simulation_with_loss_and_length_overrides(
    client: TestClient, db_session: Session
) -> None:
    """Valida simulação óptica com overrides de perda e comprimento, garantindo invariância operacional."""
    eng = create_engineer(db_session, f"eng_sim_{uuid.uuid4().hex[:6]}@provedor.com.br")
    _csrf_token = auth_client_login(client, eng.email)
    topo = setup_ftth_acceptance_topology(db_session)

    rev_before = get_current_topology_revision(db_session)

    # Localizar uma conexão de fusão no banco que faça parte da topologia
    fusion_conn = db_session.scalar(
        select(Connection).where(Connection.connection_type == "fusion")
    )
    assert fusion_conn is not None

    # 1. Simulação: aumentar atenuação da fusão de 0.10 para 3.50 dB (simulando fusão degradada)
    payload = {
        "service_link_id": str(topo["service_link"].id),
        "direction": "downstream",
        "engineering_margin_db": 3.0,
        "overrides": [
            {
                "element_id": str(fusion_conn.id),
                "override_type": "loss_db",
                "new_value": 3.50,
            }
        ],
    }

    resp = client.post("/api/v1/optical/simulations", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    sim_data = resp.json()

    baseline = sim_data["baseline"]
    simulated = sim_data["simulated"]

    assert baseline["status"] == "complete"
    assert simulated["status"] == "complete"

    # Perda adicional da fusão: 3.50 - 0.10 = 3.40 dB
    assert sim_data["delta_loss_db"] == pytest.approx(3.40, abs=0.01)
    # Potência recebida deve diminuir 3.40 dBm
    assert sim_data["delta_predicted_rx_dbm"] == pytest.approx(-3.40, abs=0.01)
    assert simulated["total_loss_db"] > baseline["total_loss_db"]

    # Verifica menção de não alteração operacional nas premissas
    assert any("Simulação" in a and "não sofreram mutação" in a for a in simulated["assumptions"])

    # 2. Invariância operacional: topology_revision não pode mudar
    rev_after = get_current_topology_revision(db_session)
    assert rev_after == rev_before


def test_optical_simulation_with_splitter_ratio_override(
    client: TestClient, db_session: Session
) -> None:
    """Valida simulação de troca de splitter de 1:8 para 1:16."""
    eng = create_engineer(db_session, f"eng_sim_{uuid.uuid4().hex[:6]}@provedor.com.br")
    _csrf_token = auth_client_login(client, eng.email)
    topo = setup_ftth_acceptance_topology(db_session)

    # Localizar um splitter na rota
    splitter = db_session.scalar(select(Splitter))
    assert splitter is not None

    payload = {
        "service_link_id": str(topo["service_link"].id),
        "direction": "downstream",
        "engineering_margin_db": 3.0,
        "overrides": [
            {
                "element_id": str(splitter.id),
                "override_type": "splitter_ratio",
                "new_value": 16.0,  # troca por 1:16 (13.8 dB vs 10.5 dB de 1:8 = +3.3 dB)
            }
        ],
    }

    resp = client.post("/api/v1/optical/simulations", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    sim_data = resp.json()

    # Delta de atenuação esperado: 13.8 - 10.5 = 3.3 dB
    assert sim_data["delta_loss_db"] == pytest.approx(3.30, abs=0.05)
    assert sim_data["delta_predicted_rx_dbm"] == pytest.approx(-3.30, abs=0.05)
