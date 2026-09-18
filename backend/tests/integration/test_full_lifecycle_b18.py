"""Teste de Integração de Ciclo Completo End-to-End (B18).

Valida o fluxo transversal ponta a ponta exigido em B18:
Admin -> POP/OLT/DIO -> Cabo Alimentador -> CEO/Fusão/Splitter -> Cabo Distribuição -> CTO -> Drop/ONU/Cliente
-> Optical Trace -> Cálculo de Orçamento Óptico -> Medição Óptica -> Análise de Impacto de Rompimento
-> Exportação GeoJSON/CSV -> Backup Atômico e Verificação de Integridade.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from geoalchemy2.shape import from_shape
from shapely.geometry import LineString, Point
from sqlalchemy.orm import Session

from app.core.backup_restore import create_backup, restore_backup
from app.core.security import hash_password
from app.modules.cables.models import Cable, CableSegment, Fiber, FiberSegment, Tube
from app.modules.connectivity.models import Connection, Splitter, SplitterOutput, Terminal
from app.modules.customers.models import Customer, ServiceLink
from app.modules.gis.service import bump_topology_revision
from app.modules.identity.models import User
from app.modules.inventory.models import Device, Port, Site, Structure
from app.modules.optical.models import OpticalProfile
from app.schemas.common import UserRole


def auth_login(client: TestClient, email: str, password: str = "AdminPass123!") -> str:
    csrf_resp = client.get("/api/v1/auth/csrf")
    csrf_token = csrf_resp.json()["csrf_token"]
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert login_resp.status_code == status.HTTP_200_OK
    cookie_token = client.cookies.get("ftth_csrf_token")
    assert cookie_token is not None
    return str(cookie_token)


def test_full_transversal_lifecycle_b18(client: TestClient, db_session: Session) -> None:
    """Executa a jornada completa do provedor com todas as camadas integradas."""
    # 1. Admin Bootstrap & Login
    admin = User(
        email="admin_audit@provedor.com.br",
        name="Admin Auditor",
        password_hash=hash_password("AdminPass123!"),
        role=UserRole.ADMIN.value,
        is_active=True,
        version=1,
    )
    db_session.add(admin)
    db_session.commit()
    csrf_token = auth_login(client, admin.email)
    headers = {"X-CSRF-Token": csrf_token}

    # 2. Infraestrutura Física: POP Site + Estruturas
    pop_site = Site(
        code="POP-AUDIT-01",
        name="POP Central Audit",
        kind="pop",
        status="installed",
        location=from_shape(Point(-46.6333, -23.5505), srid=4326),
        version=1,
    )
    db_session.add(pop_site)
    db_session.flush()

    struct_pop = Structure(
        site_id=pop_site.id,
        code="STR-POP-01",
        kind="rack",
        status="installed",
        location=from_shape(Point(-46.6333, -23.5505), srid=4326),
        version=1,
    )
    struct_ceo = Structure(
        code="CEO-AUDIT-01",
        kind="ceo",
        status="installed",
        location=from_shape(Point(-46.6350, -23.5520), srid=4326),
        version=1,
    )
    struct_cto = Structure(
        code="CTO-AUDIT-01",
        kind="cto",
        status="installed",
        location=from_shape(Point(-46.6370, -23.5540), srid=4326),
        version=1,
    )
    db_session.add_all([struct_pop, struct_ceo, struct_cto])
    db_session.flush()

    # Perfil Óptico GPON
    profile = OpticalProfile(
        name="GPON-B18-AUDIT",
        technology="GPON",
        wavelength_nm=1490,
        tx_min_dbm=2.0,
        tx_max_dbm=5.0,
        rx_sensitivity_dbm=-27.0,
        rx_overload_dbm=-8.0,
        default_attenuation_db_per_km=0.25,
        notes="ITU-T G.984 Class B+",
        version=1,
    )
    db_session.add(profile)
    db_session.flush()

    # OLT e Porta PON
    olt = Device(
        structure_id=struct_pop.id,
        code="OLT-AUDIT-01",
        kind="olt",
        model="MA5800-X7",
        manufacturer="Huawei",
        status="installed",
        version=1,
    )
    db_session.add(olt)
    db_session.flush()

    olt_port = Port(
        device_id=olt.id,
        name="PON 1/1/1",
        role="pon",
        connector_type="SC/APC",
        version=1,
    )
    db_session.add(olt_port)
    db_session.flush()

    term_olt_tx = Terminal(
        entity_type="port",
        entity_id=olt_port.id,
        structure_id=struct_pop.id,
        kind="port_front",
        label="OLT PON 1/1/1 TX",
        is_occupied=True,
        occupancy="connected",
        version=1,
    )
    db_session.add(term_olt_tx)
    db_session.flush()

    # 3. Cabos, Tubos e Fibras
    # Cabo Alimentador: POP -> CEO (3.5 km)
    feeder_cable = Cable(
        code="CBL-FEEDER-01",
        model="AS-80-12FO",
        fiber_count=12,
        tube_count=1,
        color_standard="NBR",
        status="installed",
        version=1,
    )
    db_session.add(feeder_cable)
    db_session.flush()

    feeder_seg = CableSegment(
        cable_id=feeder_cable.id,
        origin_structure_id=struct_pop.id,
        destination_structure_id=struct_ceo.id,
        map_length_m=3500.0,
        effective_length_m=3500.0,
        length_source="measured",
        status="installed",
        geometry=from_shape(
            LineString([(-46.6333, -23.5505), (-46.6350, -23.5520)]), srid=4326
        ),
        version=1,
    )
    db_session.add(feeder_seg)
    db_session.flush()

    tube1 = Tube(cable_id=feeder_cable.id, number=1, color_name="Verde", version=1)
    db_session.add(tube1)
    db_session.flush()

    fiber1 = Fiber(
        cable_id=feeder_cable.id,
        tube_id=tube1.id,
        global_number=1,
        tube_position=1,
        color_name="Verde",
        version=1,
    )
    db_session.add(fiber1)
    db_session.flush()

    term_feeder_a = Terminal(
        entity_type="fiber_segment",
        entity_id=feeder_seg.id,
        structure_id=struct_pop.id,
        kind="fiber_endpoint",
        label="Feeder FO1 Ponta A (POP)",
        is_occupied=True,
        occupancy="connected",
        version=1,
    )
    term_feeder_b = Terminal(
        entity_type="fiber_segment",
        entity_id=feeder_seg.id,
        structure_id=struct_ceo.id,
        kind="fiber_endpoint",
        label="Feeder FO1 Ponta B (CEO)",
        is_occupied=True,
        occupancy="connected",
        version=1,
    )
    db_session.add_all([term_feeder_a, term_feeder_b])
    db_session.flush()

    fseg_feeder = FiberSegment(
        cable_segment_id=feeder_seg.id,
        fiber_id=fiber1.id,
        fiber_number=1,
        terminal_a_id=term_feeder_a.id,
        terminal_b_id=term_feeder_b.id,
        occupancy="connected",
        version=1,
    )
    db_session.add(fseg_feeder)
    db_session.flush()

    # Patch cord no POP: OLT -> Feeder Ponta A
    patch_pop = Connection(
        terminal_a_id=term_olt_tx.id,
        terminal_b_id=term_feeder_a.id,
        structure_id=struct_pop.id,
        connection_type="patchcord",
        loss_db=0.30,
        is_active=True,
        version=1,
    )
    db_session.add(patch_pop)
    db_session.flush()

    # Terminais do Splitter 1:8 no CEO
    term_spl_in = Terminal(
        entity_type="splitter",
        structure_id=struct_ceo.id,
        kind="splitter_input",
        label="Splitter IN",
        is_occupied=True,
        occupancy="connected",
        version=1,
    )
    term_spl_out1 = Terminal(
        entity_type="splitter",
        structure_id=struct_ceo.id,
        kind="splitter_output",
        label="Splitter OUT #1",
        is_occupied=True,
        occupancy="connected",
        version=1,
    )
    db_session.add_all([term_spl_in, term_spl_out1])
    db_session.flush()

    # Splitter 1:8 no CEO
    ceo_splitter = Splitter(
        structure_id=struct_ceo.id,
        code="SPL-CEO-1x8",
        ratio="1:8",
        splitter_type="balanced",
        input_terminal_id=term_spl_in.id,
        version=1,
    )
    db_session.add(ceo_splitter)
    db_session.flush()

    spl_out1_entry = SplitterOutput(
        splitter_id=ceo_splitter.id,
        terminal_id=term_spl_out1.id,
        output_number=1,
        nominal_loss_db=10.2,
        version=1,
    )
    db_session.add(spl_out1_entry)
    db_session.flush()

    # Fusão no CEO: Feeder Ponta B -> Splitter IN
    fusion_ceo = Connection(
        terminal_a_id=term_feeder_b.id,
        terminal_b_id=term_spl_in.id,
        structure_id=struct_ceo.id,
        connection_type="fusion",
        loss_db=0.10,
        is_active=True,
        version=1,
    )
    db_session.add(fusion_ceo)
    db_session.flush()

    # Cabo de Distribuição: CEO -> CTO (3.5 km)
    dist_cable = Cable(
        code="CBL-DIST-01",
        model="AS-80-6FO",
        fiber_count=6,
        tube_count=1,
        color_standard="NBR",
        status="installed",
        version=1,
    )
    db_session.add(dist_cable)
    db_session.flush()

    dist_seg = CableSegment(
        cable_id=dist_cable.id,
        origin_structure_id=struct_ceo.id,
        destination_structure_id=struct_cto.id,
        map_length_m=3500.0,
        effective_length_m=3500.0,
        length_source="measured",
        status="installed",
        geometry=from_shape(
            LineString([(-46.6350, -23.5520), (-46.6370, -23.5540)]), srid=4326
        ),
        version=1,
    )
    db_session.add(dist_seg)
    db_session.flush()

    tube_dist = Tube(cable_id=dist_cable.id, number=1, color_name="Verde", version=1)
    db_session.add(tube_dist)
    db_session.flush()

    fiber_dist = Fiber(
        cable_id=dist_cable.id,
        tube_id=tube_dist.id,
        global_number=1,
        tube_position=1,
        color_name="Verde",
        version=1,
    )
    db_session.add(fiber_dist)
    db_session.flush()

    term_dist_a = Terminal(
        entity_type="fiber_segment",
        entity_id=dist_seg.id,
        structure_id=struct_ceo.id,
        kind="fiber_endpoint",
        label="Dist FO1 Ponta A (CEO)",
        is_occupied=True,
        occupancy="connected",
        version=1,
    )
    term_dist_b = Terminal(
        entity_type="fiber_segment",
        entity_id=dist_seg.id,
        structure_id=struct_cto.id,
        kind="fiber_endpoint",
        label="Dist FO1 Ponta B (CTO)",
        is_occupied=True,
        occupancy="connected",
        version=1,
    )
    db_session.add_all([term_dist_a, term_dist_b])
    db_session.flush()

    fseg_dist = FiberSegment(
        cable_segment_id=dist_seg.id,
        fiber_id=fiber_dist.id,
        fiber_number=1,
        terminal_a_id=term_dist_a.id,
        terminal_b_id=term_dist_b.id,
        occupancy="connected",
        version=1,
    )
    db_session.add(fseg_dist)
    db_session.flush()

    # Fusão no CEO: Splitter OUT #1 -> Dist FO1 Ponta A
    fusion_ceo_dist = Connection(
        terminal_a_id=term_spl_out1.id,
        terminal_b_id=term_dist_a.id,
        structure_id=struct_ceo.id,
        connection_type="fusion",
        loss_db=0.10,
        is_active=True,
        version=1,
    )
    db_session.add(fusion_ceo_dist)
    db_session.flush()

    # Splitter 1:8 na CTO (segundo splitter conforme B10 / cenário transversal)
    term_cto_spl_in = Terminal(
        entity_type="splitter",
        structure_id=struct_cto.id,
        kind="splitter_input",
        label="CTO Splitter IN",
        is_occupied=True,
        occupancy="connected",
        version=1,
    )
    term_cto_spl_out1 = Terminal(
        entity_type="splitter",
        structure_id=struct_cto.id,
        kind="splitter_output",
        label="CTO Splitter OUT #1",
        is_occupied=True,
        occupancy="connected",
        version=1,
    )
    db_session.add_all([term_cto_spl_in, term_cto_spl_out1])
    db_session.flush()

    cto_splitter = Splitter(
        structure_id=struct_cto.id,
        code="SPL-CTO-1x8",
        ratio="1:8",
        splitter_type="balanced",
        input_terminal_id=term_cto_spl_in.id,
        version=1,
    )
    db_session.add(cto_splitter)
    db_session.flush()

    spl_cto_out1_entry = SplitterOutput(
        splitter_id=cto_splitter.id,
        terminal_id=term_cto_spl_out1.id,
        output_number=1,
        nominal_loss_db=10.2,
        version=1,
    )
    db_session.add(spl_cto_out1_entry)
    db_session.flush()

    # Fusão na CTO: Dist FO1 Ponta B -> Splitter IN da CTO
    fusion_cto_in = Connection(
        terminal_a_id=term_dist_b.id,
        terminal_b_id=term_cto_spl_in.id,
        structure_id=struct_cto.id,
        connection_type="fusion",
        loss_db=0.10,
        is_active=True,
        version=1,
    )
    db_session.add(fusion_cto_in)
    db_session.flush()

    # Porta de Atendimento da CTO
    cto_port = Port(
        structure_id=struct_cto.id,
        name="Porta Atendimento #1",
        role="client_drop",
        connector_type="SC/APC",
        version=1,
    )
    db_session.add(cto_port)
    db_session.flush()

    term_cto_port = Terminal(
        entity_type="port",
        entity_id=cto_port.id,
        structure_id=struct_cto.id,
        kind="port_front",
        label="CTO Porta 1",
        is_occupied=True,
        occupancy="connected",
        version=1,
    )
    db_session.add(term_cto_port)
    db_session.flush()

    # Fusão na CTO: Splitter OUT #1 -> Terminal Porta CTO
    fusion_cto_out = Connection(
        terminal_a_id=term_cto_spl_out1.id,
        terminal_b_id=term_cto_port.id,
        structure_id=struct_cto.id,
        connection_type="fusion",
        loss_db=0.10,
        is_active=True,
        version=1,
    )
    db_session.add(fusion_cto_out)
    db_session.flush()

    # 4. Cliente Sintético DEMO-001 e Atendimento Ativo
    customer = Customer(
        code="CLI-DEMO-001",
        name="Cliente Audit B18",
        version=1,
    )
    db_session.add(customer)
    db_session.flush()

    onu_device = Device(
        structure_id=struct_cto.id,
        code="ONU-DEMO-001",
        kind="onu",
        model="HG8245H",
        manufacturer="Huawei",
        serial_number="HWTC12345678",
        status="installed",
        version=1,
    )
    db_session.add(onu_device)
    db_session.flush()

    onu_port = Port(
        device_id=onu_device.id,
        name="PON Opt",
        role="uplink",
        connector_type="SC/APC",
        version=1,
    )
    db_session.add(onu_port)
    db_session.flush()

    term_onu_rx = Terminal(
        entity_type="port",
        entity_id=onu_port.id,
        structure_id=struct_cto.id,
        kind="port_front",
        label="ONU PON RX",
        is_occupied=True,
        occupancy="connected",
        version=1,
    )
    db_session.add(term_onu_rx)
    db_session.flush()

    # Conexão Drop do Cliente: CTO Porta -> ONU
    drop_conn = Connection(
        terminal_a_id=term_cto_port.id,
        terminal_b_id=term_onu_rx.id,
        structure_id=struct_cto.id,
        connection_type="patchcord",
        loss_db=0.30,
        is_active=True,
        version=1,
    )
    db_session.add(drop_conn)
    db_session.flush()

    svc_link = ServiceLink(
        customer_id=customer.id,
        port_id=cto_port.id,
        onu_device_id=onu_device.id,
        status="active",
        version=1,
    )
    db_session.add(svc_link)

    bump_topology_revision(db_session)
    db_session.commit()

    # =========================================================================
    # 5. Rastreamento Óptico Fim-a-Fim (Trace Downstream)
    # =========================================================================
    trace_resp = client.post(
        "/api/v1/topology/trace",
        json={
            "start_terminal_id": str(term_olt_tx.id),
            "direction": "downstream",
        },
        headers=headers,
    )
    assert trace_resp.status_code == status.HTTP_200_OK
    trace_data = trace_resp.json()
    assert trace_data["status"] == "complete"
    assert len(trace_data["paths"]) == 1
    path = trace_data["paths"][0]
    assert path["origin_terminal_id"] == str(term_olt_tx.id)
    assert path["destination_terminal_id"] == str(term_onu_rx.id)
    # Distância total: 3500m + 3500m = 7000m (7 km exatos)
    assert path["total_length_m"] == pytest.approx(7000.0, rel=1e-2)
    assert len(path["steps"]) >= 4

    # =========================================================================
    # 6. Cálculo de Orçamento Óptico (Optical Budget)
    # =========================================================================
    budget_resp = client.post(
        "/api/v1/optical/budgets",
        json={
            "start_terminal_id": str(term_olt_tx.id),
            "profile_id": str(profile.id),
            "direction": "downstream",
            "engineering_margin_db": 3.0,
        },
        headers=headers,
    )
    assert budget_resp.status_code == status.HTTP_200_OK
    budget_data = budget_resp.json()
    assert budget_data["assessment"] in ["pass", "low_margin"]
    assert budget_data["predicted_rx_dbm"] is not None
    assert budget_data["remaining_margin_db"] is not None

    # =========================================================================
    # 7. Medição Óptica em Campo (Optical Measurement)
    # =========================================================================
    meas_resp = client.post(
        "/api/v1/measurements",
        json={
            "terminal_id": str(term_onu_rx.id),
            "service_link_id": str(svc_link.id),
            "power_dbm": -22.50,
            "wavelength_nm": 1490,
            "direction": "downstream",
            "instrument_model": "PowerMeter EXFO PPM-350D",
            "notes": "Medição de certificação na ativação do cliente.",
        },
        headers=headers,
    )
    assert meas_resp.status_code == status.HTTP_201_CREATED
    meas_data = meas_resp.json()
    assert meas_data["power_dbm"] == -22.50
    assert "excess_loss_db" in meas_data

    # =========================================================================
    # 8. Análise de Impacto de Rompimento (Impact Analysis)
    # =========================================================================
    current_rev = trace_data["topology_revision"]
    impact_resp = client.post(
        "/api/v1/topology/impact",
        json={
            "cable_segment_ids": [str(feeder_seg.id)],
            "expected_topology_revision": current_rev,
        },
        headers=headers,
    )
    assert impact_resp.status_code == status.HTTP_200_OK
    impact_data = impact_resp.json()
    assert impact_data["broken_segments_count"] == 1
    assert len(impact_data["impacted_customers"]) == 1
    assert impact_data["impacted_customers"][0]["customer_code"] == "CLI-DEMO-001"

    # =========================================================================
    # 9. Solicitação de Exportação de Topologia (Jobs / Exports)
    # =========================================================================
    export_resp = client.post(
        "/api/v1/exports",
        json={"format": "geojson", "layer": "all"},
        headers=headers,
    )
    assert export_resp.status_code == status.HTTP_202_ACCEPTED
    export_job = export_resp.json()
    assert "job_id" in export_job

    # =========================================================================
    # 10. Backup Consistente e Restauração Isolada
    # =========================================================================
    with tempfile.TemporaryDirectory() as bkp_tmp:
        bkp_dir = Path(bkp_tmp)
        backup_file = create_backup(target_dir=bkp_dir)
        assert backup_file.exists()
        assert backup_file.stat().st_size > 0

        with tempfile.TemporaryDirectory() as restore_storage:
            manifest = restore_backup(
                archive_path=backup_file,
                target_storage_path=Path(restore_storage),
                verify_checksums=True,
            )
            assert manifest.topology_revision >= 1
            assert manifest.schema_version != ""
