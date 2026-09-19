#!/usr/bin/env python3
"""Seed Determinístico e Idempotente do Cenário Transversal B18.

Executado sob demanda via CLI:
    uv run python scripts/seed_demo.py [--clean] [--target-db dev|test]

Popula o cenário transversal completo:
1. Admin padrão (admin@provedor.com.br / AdminPass123!)
2. Perfil Óptico GPON ITU-T G.984 Classe B+ (1490 nm, TX +2 a +5 dBm, RX -27 a -8 dBm)
3. Site POP Central com Rack e OLT Huawei MA5800-X7 (Portas PON 1/1/1 e PON 1/1/2)
4. Trajeto principal (7 km total):
   - Feeder Cable (3.5 km, 12 FO)
   - CEO com fusão e splitter balanceado 1:8
   - Cabo de Distribuição (3.5 km, 6 FO)
   - CTO-DEMO-01 com splitter balanceado 1:8
   - Drop / ONU / Cliente DEMO-001 ativo (4 fusões, 2 patch cords, 2 splitters 1:8)
5. Medição óptica de campo certificada (-22.50 dBm)
6. Ramo secundário independente (CTO-DEMO-02 e Cliente DEMO-002) para teste de rompimento de cabo
7. Ramo com ponta aberta (CTO-DEMO-03, 12 FO) para teste de incompletude topológica
8. Fusão com atenuação não aferida (loss_db=0.0) para teste de pendência
9. Histórico de atenuação degradada (-28.50 dBm) para relatórios de degradação

ATENÇÃO: Este seed é estritamente opt-in e NUNCA é executado automaticamente no boot de produção.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from typing import Any

from geoalchemy2.shape import from_shape
from shapely.geometry import LineString, Point
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.modules.cables.models import Cable, CableSegment, Fiber, FiberSegment, Tube
from app.modules.connectivity.models import (
    Connection,
    Splitter,
    SplitterOutput,
    Terminal,
)
from app.modules.customers.models import Customer, ServiceLink
from app.modules.gis.service import bump_topology_revision
from app.modules.identity.models import User
from app.modules.inventory.models import Device, Port, Site, Structure
from app.modules.measurements.models import OpticalMeasurement
from app.modules.optical.models import OpticalProfile
from app.schemas.common import UserRole


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed do cenário transversal do provedor FTTH (B18)."
    )
    parser.add_argument(
        "--target-db",
        choices=["dev", "test"],
        default="dev",
        help="Banco de dados de destino: 'dev' (padrão) ou 'test'.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove todos os dados com prefixo DEMO antes de inserir o cenário.",
    )
    return parser.parse_args()


def get_db_url(target_db: str) -> str:
    settings = get_settings()
    base_url = settings.DATABASE_URL
    if target_db == "test":
        # Substitui nome do banco por ftth_manager_test
        parts = base_url.rsplit("/", 1)
        return f"{parts[0]}/ftth_manager_test"
    return base_url


def clean_demo_data(session: Session) -> None:
    """Remove deterministicamente registros de demonstração anteriores."""
    print("[-] Limpando entidades de demonstração existentes...")

    # Remove medições de terminais demo
    session.execute(
        text(
            "DELETE FROM optical_measurements WHERE terminal_id IN ("
            "SELECT id FROM terminals WHERE label LIKE '%DEMO%' OR label LIKE '%Demo%')"
        )
    )

    # Remove ServiceLinks demo
    session.execute(
        text(
            "DELETE FROM service_links WHERE customer_id IN ("
            "SELECT id FROM customers WHERE code LIKE '%DEMO%')"
        )
    )

    # Remove Clientes demo
    session.execute(text("DELETE FROM customers WHERE code LIKE '%DEMO%'"))

    # Remove Conexões demo
    session.execute(
        text(
            "DELETE FROM connections WHERE terminal_a_id IN ("
            "SELECT id FROM terminals WHERE label LIKE '%DEMO%' OR label LIKE '%Demo%') "
            "OR terminal_b_id IN ("
            "SELECT id FROM terminals WHERE label LIKE '%DEMO%' OR label LIKE '%Demo%')"
        )
    )

    # Remove Splitters demo
    session.execute(
        text(
            "DELETE FROM splitter_outputs WHERE splitter_id IN "
            "(SELECT id FROM splitters WHERE code LIKE '%DEMO%')"
        )
    )
    session.execute(text("DELETE FROM splitters WHERE code LIKE '%DEMO%'"))

    # Remove FiberSegments demo
    session.execute(
        text(
            "DELETE FROM fiber_segments WHERE cable_segment_id IN ("
            "SELECT cs.id FROM cable_segments cs "
            "JOIN cables c ON cs.cable_id = c.id WHERE c.code LIKE '%DEMO%')"
        )
    )

    # Remove Terminais demo
    session.execute(text("DELETE FROM terminals WHERE label LIKE '%DEMO%' OR label LIKE '%Demo%'"))

    # Remove Portas demo
    session.execute(
        text(
            "DELETE FROM ports WHERE device_id IN (SELECT id FROM devices WHERE code LIKE '%DEMO%') "
            "OR structure_id IN (SELECT id FROM structures WHERE code LIKE '%DEMO%')"
        )
    )

    # Remove Dispositivos demo
    session.execute(text("DELETE FROM devices WHERE code LIKE '%DEMO%'"))

    # Remove Fibras, Tubos e Segmentos de Cabos demo
    session.execute(
        text(
            "DELETE FROM fibers WHERE cable_id IN (SELECT id FROM cables WHERE code LIKE '%DEMO%')"
        )
    )
    session.execute(
        text("DELETE FROM tubes WHERE cable_id IN (SELECT id FROM cables WHERE code LIKE '%DEMO%')")
    )
    session.execute(
        text(
            "DELETE FROM cable_segments WHERE cable_id IN (SELECT id FROM cables WHERE code LIKE '%DEMO%')"
        )
    )
    session.execute(text("DELETE FROM cables WHERE code LIKE '%DEMO%'"))

    # Remove Estruturas demo
    session.execute(text("DELETE FROM structures WHERE code LIKE '%DEMO%'"))

    # Remove Site demo
    session.execute(text("DELETE FROM sites WHERE code LIKE '%DEMO%'"))

    # Remove Perfil demo
    session.execute(text("DELETE FROM optical_profiles WHERE name LIKE '%Demo%'"))

    session.commit()
    print("[+] Limpeza concluída com sucesso.")


def seed_demo_scenario(session: Session) -> dict[str, Any]:
    """Popula todo o cenário transversal determinístico."""
    print("[*] Iniciando população do cenário transversal B18...")

    # 1. Admin Bootstrap
    admin = session.scalar(select(User).where(User.email == "admin@provedor.com.br"))
    if not admin:
        admin = User(
            email="admin@provedor.com.br",
            name="Administrador do Sistema",
            password_hash=hash_password("AdminPass123!"),
            role=UserRole.ADMIN.value,
            is_active=True,
            version=1,
        )
        session.add(admin)
        session.flush()
        print("  [+] Admin admin@provedor.com.br provisionado.")
    else:
        print("  [.] Admin admin@provedor.com.br já existe.")

    # 2. Perfil Óptico GPON
    profile = session.scalar(
        select(OpticalProfile).where(OpticalProfile.name == "GPON ITU-T G.984 Classe B+ (Demo)")
    )
    if not profile:
        profile = OpticalProfile(
            name="GPON ITU-T G.984 Classe B+ (Demo)",
            technology="GPON",
            wavelength_nm=1490,
            tx_min_dbm=2.0,
            tx_max_dbm=5.0,
            rx_sensitivity_dbm=-27.0,
            rx_overload_dbm=-8.0,
            default_attenuation_db_per_km=0.25,
            notes="ITU-T G.984 Classe B+ padrão de ativação demo.",
            version=1,
        )
        session.add(profile)
        session.flush()

    # 3. Infraestrutura Física: POP e Estruturas
    pop_site = Site(
        code="POP-DEMO-01",
        name="POP Central Demo",
        kind="pop",
        status="installed",
        location=from_shape(Point(-46.6333, -23.5505), srid=4326),
        version=1,
    )
    session.add(pop_site)
    session.flush()

    struct_pop = Structure(
        site_id=pop_site.id,
        code="STR-POP-DEMO-01",
        kind="rack",
        status="installed",
        location=from_shape(Point(-46.6333, -23.5505), srid=4326),
        version=1,
    )
    struct_ceo = Structure(
        code="CEO-DEMO-01",
        kind="ceo",
        status="installed",
        location=from_shape(Point(-46.6350, -23.5520), srid=4326),
        version=1,
    )
    struct_cto1 = Structure(
        code="CTO-DEMO-01",
        kind="cto",
        status="installed",
        location=from_shape(Point(-46.6370, -23.5540), srid=4326),
        version=1,
    )
    # CTO 2: Ramo independente para teste de corte de cabo
    struct_cto2 = Structure(
        code="CTO-DEMO-02",
        kind="cto",
        status="installed",
        location=from_shape(Point(-46.6390, -23.5510), srid=4326),
        version=1,
    )
    # CTO 3: Ramo com ponta aberta
    struct_cto3 = Structure(
        code="CTO-DEMO-03",
        kind="cto",
        status="installed",
        location=from_shape(Point(-46.6400, -23.5530), srid=4326),
        version=1,
    )
    session.add_all([struct_pop, struct_ceo, struct_cto1, struct_cto2, struct_cto3])
    session.flush()

    # 4. Dispositivo OLT no POP com 2 portas PON
    olt = Device(
        structure_id=struct_pop.id,
        code="OLT-DEMO-01",
        kind="olt",
        model="MA5800-X7",
        manufacturer="Huawei",
        status="installed",
        version=1,
    )
    session.add(olt)
    session.flush()

    olt_p1 = Port(
        device_id=olt.id,
        name="PON 1/1/1",
        role="pon",
        connector_type="SC/APC",
        version=1,
    )
    olt_p2 = Port(
        device_id=olt.id,
        name="PON 1/1/2",
        role="pon",
        connector_type="SC/APC",
        version=1,
    )
    session.add_all([olt_p1, olt_p2])
    session.flush()

    term_olt_tx1 = Terminal(
        entity_type="port",
        entity_id=olt_p1.id,
        structure_id=struct_pop.id,
        kind="port_front",
        label="OLT-DEMO-01 PON 1/1/1 TX",
        is_occupied=True,
        occupancy="connected",
        version=1,
    )
    term_olt_tx2 = Terminal(
        entity_type="port",
        entity_id=olt_p2.id,
        structure_id=struct_pop.id,
        kind="port_front",
        label="OLT-DEMO-01 PON 1/1/2 TX",
        is_occupied=True,
        occupancy="connected",
        version=1,
    )
    session.add_all([term_olt_tx1, term_olt_tx2])
    session.flush()

    # 5. Cabo Alimentador Principal: POP -> CEO (3.5 km, 12 FO)
    feeder_cable = Cable(
        code="CBL-FEEDER-DEMO-01",
        model="AS-80-12FO",
        fiber_count=12,
        tube_count=1,
        color_standard="NBR",
        status="installed",
        version=1,
    )
    session.add(feeder_cable)
    session.flush()

    feeder_seg = CableSegment(
        cable_id=feeder_cable.id,
        origin_structure_id=struct_pop.id,
        destination_structure_id=struct_ceo.id,
        map_length_m=3500.0,
        effective_length_m=3500.0,
        length_source="measured",
        status="installed",
        geometry=from_shape(LineString([(-46.6333, -23.5505), (-46.6350, -23.5520)]), srid=4326),
        version=1,
    )
    session.add(feeder_seg)
    session.flush()

    tube_feeder = Tube(cable_id=feeder_cable.id, number=1, color_name="Verde", version=1)
    session.add(tube_feeder)
    session.flush()

    fiber_feeder1 = Fiber(
        cable_id=feeder_cable.id,
        tube_id=tube_feeder.id,
        global_number=1,
        tube_position=1,
        color_name="Verde",
        version=1,
    )
    session.add(fiber_feeder1)
    session.flush()

    term_feeder_a = Terminal(
        entity_type="fiber_segment",
        entity_id=feeder_seg.id,
        structure_id=struct_pop.id,
        kind="fiber_endpoint",
        label="Feeder DEMO FO1 Ponta A (POP)",
        is_occupied=True,
        occupancy="connected",
        version=1,
    )
    term_feeder_b = Terminal(
        entity_type="fiber_segment",
        entity_id=feeder_seg.id,
        structure_id=struct_ceo.id,
        kind="fiber_endpoint",
        label="Feeder DEMO FO1 Ponta B (CEO)",
        is_occupied=True,
        occupancy="connected",
        version=1,
    )
    session.add_all([term_feeder_a, term_feeder_b])
    session.flush()

    fseg_feeder = FiberSegment(
        cable_segment_id=feeder_seg.id,
        fiber_id=fiber_feeder1.id,
        fiber_number=1,
        terminal_a_id=term_feeder_a.id,
        terminal_b_id=term_feeder_b.id,
        occupancy="connected",
        version=1,
    )
    session.add(fseg_feeder)
    session.flush()

    # Patch cord no POP: OLT PON 1/1/1 -> Feeder Ponta A (Mated pair 1: 0.30 dB)
    patch_pop = Connection(
        terminal_a_id=term_olt_tx1.id,
        terminal_b_id=term_feeder_a.id,
        structure_id=struct_pop.id,
        connection_type="patchcord",
        loss_db=0.30,
        is_active=True,
        version=1,
    )
    session.add(patch_pop)
    session.flush()

    # 6. Splitter 1:8 no CEO
    term_ceo_spl_in = Terminal(
        entity_type="splitter",
        structure_id=struct_ceo.id,
        kind="splitter_input",
        label="CEO Splitter IN",
        is_occupied=True,
        occupancy="connected",
        version=1,
    )
    term_ceo_spl_out1 = Terminal(
        entity_type="splitter",
        structure_id=struct_ceo.id,
        kind="splitter_output",
        label="CEO Splitter OUT #1",
        is_occupied=True,
        occupancy="connected",
        version=1,
    )
    session.add_all([term_ceo_spl_in, term_ceo_spl_out1])
    session.flush()

    ceo_splitter = Splitter(
        structure_id=struct_ceo.id,
        code="SPL-CEO-DEMO-1x8",
        ratio="1:8",
        splitter_type="balanced",
        input_terminal_id=term_ceo_spl_in.id,
        version=1,
    )
    session.add(ceo_splitter)
    session.flush()

    spl_ceo_out1 = SplitterOutput(
        splitter_id=ceo_splitter.id,
        terminal_id=term_ceo_spl_out1.id,
        output_number=1,
        nominal_loss_db=10.2,
        version=1,
    )
    session.add(spl_ceo_out1)
    session.flush()

    # Fusão 1 no CEO: Feeder Ponta B -> Splitter IN (0.10 dB)
    fusion_ceo1 = Connection(
        terminal_a_id=term_feeder_b.id,
        terminal_b_id=term_ceo_spl_in.id,
        structure_id=struct_ceo.id,
        connection_type="fusion",
        loss_db=0.10,
        is_active=True,
        version=1,
    )
    session.add(fusion_ceo1)
    session.flush()

    # 7. Cabo de Distribuição: CEO -> CTO-DEMO-01 (3.5 km, 6 FO)
    dist_cable = Cable(
        code="CBL-DIST-DEMO-01",
        model="AS-80-6FO",
        fiber_count=6,
        tube_count=1,
        color_standard="NBR",
        status="installed",
        version=1,
    )
    session.add(dist_cable)
    session.flush()

    dist_seg = CableSegment(
        cable_id=dist_cable.id,
        origin_structure_id=struct_ceo.id,
        destination_structure_id=struct_cto1.id,
        map_length_m=3500.0,
        effective_length_m=3500.0,
        length_source="measured",
        status="installed",
        geometry=from_shape(LineString([(-46.6350, -23.5520), (-46.6370, -23.5540)]), srid=4326),
        version=1,
    )
    session.add(dist_seg)
    session.flush()

    tube_dist = Tube(cable_id=dist_cable.id, number=1, color_name="Verde", version=1)
    session.add(tube_dist)
    session.flush()

    fiber_dist1 = Fiber(
        cable_id=dist_cable.id,
        tube_id=tube_dist.id,
        global_number=1,
        tube_position=1,
        color_name="Verde",
        version=1,
    )
    session.add(fiber_dist1)
    session.flush()

    term_dist_a = Terminal(
        entity_type="fiber_segment",
        entity_id=dist_seg.id,
        structure_id=struct_ceo.id,
        kind="fiber_endpoint",
        label="Dist DEMO FO1 Ponta A (CEO)",
        is_occupied=True,
        occupancy="connected",
        version=1,
    )
    term_dist_b = Terminal(
        entity_type="fiber_segment",
        entity_id=dist_seg.id,
        structure_id=struct_cto1.id,
        kind="fiber_endpoint",
        label="Dist DEMO FO1 Ponta B (CTO-01)",
        is_occupied=True,
        occupancy="connected",
        version=1,
    )
    session.add_all([term_dist_a, term_dist_b])
    session.flush()

    fseg_dist = FiberSegment(
        cable_segment_id=dist_seg.id,
        fiber_id=fiber_dist1.id,
        fiber_number=1,
        terminal_a_id=term_dist_a.id,
        terminal_b_id=term_dist_b.id,
        occupancy="connected",
        version=1,
    )
    session.add(fseg_dist)
    session.flush()

    # Fusão 2 no CEO: Splitter OUT #1 -> Dist FO1 Ponta A (0.10 dB)
    fusion_ceo2 = Connection(
        terminal_a_id=term_ceo_spl_out1.id,
        terminal_b_id=term_dist_a.id,
        structure_id=struct_ceo.id,
        connection_type="fusion",
        loss_db=0.10,
        is_active=True,
        version=1,
    )
    session.add(fusion_ceo2)
    session.flush()

    # 8. Splitter 1:8 e Porta de Atendimento na CTO-DEMO-01
    term_cto_spl_in = Terminal(
        entity_type="splitter",
        structure_id=struct_cto1.id,
        kind="splitter_input",
        label="CTO-01 Splitter IN",
        is_occupied=True,
        occupancy="connected",
        version=1,
    )
    term_cto_spl_out1 = Terminal(
        entity_type="splitter",
        structure_id=struct_cto1.id,
        kind="splitter_output",
        label="CTO-01 Splitter OUT #1",
        is_occupied=True,
        occupancy="connected",
        version=1,
    )
    session.add_all([term_cto_spl_in, term_cto_spl_out1])
    session.flush()

    cto_splitter = Splitter(
        structure_id=struct_cto1.id,
        code="SPL-CTO-DEMO-1x8",
        ratio="1:8",
        splitter_type="balanced",
        input_terminal_id=term_cto_spl_in.id,
        version=1,
    )
    session.add(cto_splitter)
    session.flush()

    spl_cto_out1 = SplitterOutput(
        splitter_id=cto_splitter.id,
        terminal_id=term_cto_spl_out1.id,
        output_number=1,
        nominal_loss_db=10.2,
        version=1,
    )
    session.add(spl_cto_out1)
    session.flush()

    # Fusão 3 na CTO-01: Dist FO1 Ponta B -> Splitter IN da CTO (0.10 dB)
    fusion_cto3 = Connection(
        terminal_a_id=term_dist_b.id,
        terminal_b_id=term_cto_spl_in.id,
        structure_id=struct_cto1.id,
        connection_type="fusion",
        loss_db=0.10,
        is_active=True,
        version=1,
    )
    session.add(fusion_cto3)
    session.flush()

    # Porta de Atendimento da CTO-01
    cto_p1 = Port(
        structure_id=struct_cto1.id,
        name="Porta Atendimento #1",
        role="client_drop",
        connector_type="SC/APC",
        version=1,
    )
    session.add(cto_p1)
    session.flush()

    term_cto_p1 = Terminal(
        entity_type="port",
        entity_id=cto_p1.id,
        structure_id=struct_cto1.id,
        kind="port_front",
        label="CTO-01 Porta 1",
        is_occupied=True,
        occupancy="connected",
        version=1,
    )
    session.add(term_cto_p1)
    session.flush()

    # Fusão 4 na CTO-01: Splitter OUT #1 -> Porta Atendimento (0.10 dB)
    fusion_cto4 = Connection(
        terminal_a_id=term_cto_spl_out1.id,
        terminal_b_id=term_cto_p1.id,
        structure_id=struct_cto1.id,
        connection_type="fusion",
        loss_db=0.10,
        is_active=True,
        version=1,
    )
    session.add(fusion_cto4)
    session.flush()

    # 9. Assinante Principal: CLI-DEMO-001 e ONU
    customer1 = Customer(
        code="CLI-DEMO-001",
        name="Empresa Alfa Demo Ltda",
        phone="(11) 98765-4321",
        email="contato@alfa-demo.com.br",
        address="Av. Paulista, 1000 - São Paulo, SP",
        notes="Cliente principal do circuito transversal auditado.",
        version=1,
    )
    session.add(customer1)
    session.flush()

    onu1 = Device(
        structure_id=struct_cto1.id,
        code="ONU-DEMO-001",
        kind="onu",
        model="HG8245H",
        manufacturer="Huawei",
        serial_number="HWTC-DEMO-0001",
        status="installed",
        version=1,
    )
    session.add(onu1)
    session.flush()

    onu_p1 = Port(
        device_id=onu1.id,
        name="PON Opt",
        role="uplink",
        connector_type="SC/APC",
        version=1,
    )
    session.add(onu_p1)
    session.flush()

    term_onu_rx1 = Terminal(
        entity_type="port",
        entity_id=onu_p1.id,
        structure_id=struct_cto1.id,
        kind="port_front",
        label="ONU-DEMO-001 PON RX",
        is_occupied=True,
        occupancy="connected",
        version=1,
    )
    session.add(term_onu_rx1)
    session.flush()

    # Drop de Conexão Cliente: CTO Porta 1 -> ONU (Mated pair 2: 0.30 dB)
    drop_conn1 = Connection(
        terminal_a_id=term_cto_p1.id,
        terminal_b_id=term_onu_rx1.id,
        structure_id=struct_cto1.id,
        connection_type="patchcord",
        loss_db=0.30,
        is_active=True,
        version=1,
    )
    session.add(drop_conn1)
    session.flush()

    svc_link1 = ServiceLink(
        customer_id=customer1.id,
        port_id=cto_p1.id,
        onu_device_id=onu1.id,
        status="active",
        notes="Atendimento em produção auditado em B18.",
        version=1,
    )
    session.add(svc_link1)
    session.flush()

    # Medição Óptica de Campo Aprovada na Ativação (-22.50 dBm)
    meas1 = OpticalMeasurement(
        terminal_id=term_onu_rx1.id,
        service_link_id=svc_link1.id,
        power_dbm=-22.50,
        wavelength_nm=1490,
        direction="downstream",
        origin="field_power_meter",
        instrument_model="PowerMeter EXFO PPM-350D",
        measured_at=datetime.now(UTC),
        user_id=admin.id,
        predicted_power_dbm=-21.15,
        excess_loss_db=1.35,
        version=1,
    )
    session.add(meas1)
    session.flush()

    # 10. Ramo Secundário Independente (CTO-DEMO-02 + CLI-DEMO-002)
    # Permite validar que um corte no alimentador principal NÃO afeta este cliente
    cbl_indep = Cable(
        code="CBL-DIST-DEMO-02",
        model="AS-80-6FO",
        fiber_count=6,
        tube_count=1,
        color_standard="NBR",
        status="installed",
        version=1,
    )
    session.add(cbl_indep)
    session.flush()

    seg_indep = CableSegment(
        cable_id=cbl_indep.id,
        origin_structure_id=struct_pop.id,
        destination_structure_id=struct_cto2.id,
        map_length_m=2000.0,
        effective_length_m=2000.0,
        length_source="measured",
        status="installed",
        geometry=from_shape(LineString([(-46.6333, -23.5505), (-46.6390, -23.5510)]), srid=4326),
        version=1,
    )
    session.add(seg_indep)
    session.flush()

    tube_indep = Tube(cable_id=cbl_indep.id, number=1, color_name="Verde", version=1)
    session.add(tube_indep)
    session.flush()

    fiber_indep = Fiber(
        cable_id=cbl_indep.id,
        tube_id=tube_indep.id,
        global_number=1,
        tube_position=1,
        color_name="Verde",
        version=1,
    )
    session.add(fiber_indep)
    session.flush()

    term_indep_a = Terminal(
        entity_type="fiber_segment",
        entity_id=seg_indep.id,
        structure_id=struct_pop.id,
        kind="fiber_endpoint",
        label="Indep DEMO FO1 Ponta A (POP)",
        is_occupied=True,
        occupancy="connected",
        version=1,
    )
    term_indep_b = Terminal(
        entity_type="fiber_segment",
        entity_id=seg_indep.id,
        structure_id=struct_cto2.id,
        kind="fiber_endpoint",
        label="Indep DEMO FO1 Ponta B (CTO-02)",
        is_occupied=True,
        occupancy="connected",
        version=1,
    )
    session.add_all([term_indep_a, term_indep_b])
    session.flush()

    fseg_indep = FiberSegment(
        cable_segment_id=seg_indep.id,
        fiber_id=fiber_indep.id,
        fiber_number=1,
        terminal_a_id=term_indep_a.id,
        terminal_b_id=term_indep_b.id,
        occupancy="connected",
        version=1,
    )
    session.add(fseg_indep)
    session.flush()

    # Patch cord no POP da porta PON 1/1/2 -> Cabo Independente
    patch_indep = Connection(
        terminal_a_id=term_olt_tx2.id,
        terminal_b_id=term_indep_a.id,
        structure_id=struct_pop.id,
        connection_type="patchcord",
        loss_db=0.30,
        is_active=True,
        version=1,
    )
    session.add(patch_indep)
    session.flush()

    # Porta CTO-02 e Cliente DEMO-002
    cto2_p1 = Port(
        structure_id=struct_cto2.id,
        name="Porta Atendimento #1",
        role="client_drop",
        connector_type="SC/APC",
        version=1,
    )
    session.add(cto2_p1)
    session.flush()

    term_cto2_p1 = Terminal(
        entity_type="port",
        entity_id=cto2_p1.id,
        structure_id=struct_cto2.id,
        kind="port_front",
        label="CTO-02 Porta 1",
        is_occupied=True,
        occupancy="connected",
        version=1,
    )
    session.add(term_cto2_p1)
    session.flush()

    fusion_indep = Connection(
        terminal_a_id=term_indep_b.id,
        terminal_b_id=term_cto2_p1.id,
        structure_id=struct_cto2.id,
        connection_type="fusion",
        loss_db=0.10,
        is_active=True,
        version=1,
    )
    session.add(fusion_indep)
    session.flush()

    customer2 = Customer(
        code="CLI-DEMO-002",
        name="Beta Comércio Demo Eireli",
        phone="(11) 97654-3210",
        email="suporte@beta-demo.com.br",
        address="Rua Augusta, 500 - São Paulo, SP",
        notes="Cliente em rota independente (não afetado por corte no feeder 01).",
        version=1,
    )
    session.add(customer2)
    session.flush()

    onu2 = Device(
        structure_id=struct_cto2.id,
        code="ONU-DEMO-002",
        kind="onu",
        model="HG8245H",
        manufacturer="Huawei",
        serial_number="HWTC-DEMO-0002",
        status="installed",
        version=1,
    )
    session.add(onu2)
    session.flush()

    onu2_p1 = Port(
        device_id=onu2.id,
        name="PON Opt",
        role="uplink",
        connector_type="SC/APC",
        version=1,
    )
    session.add(onu2_p1)
    session.flush()

    term_onu_rx2 = Terminal(
        entity_type="port",
        entity_id=onu2_p1.id,
        structure_id=struct_cto2.id,
        kind="port_front",
        label="ONU-DEMO-002 PON RX",
        is_occupied=True,
        occupancy="connected",
        version=1,
    )
    session.add(term_onu_rx2)
    session.flush()

    drop_conn2 = Connection(
        terminal_a_id=term_cto2_p1.id,
        terminal_b_id=term_onu_rx2.id,
        structure_id=struct_cto2.id,
        connection_type="patchcord",
        loss_db=0.30,
        is_active=True,
        version=1,
    )
    session.add(drop_conn2)
    session.flush()

    svc_link2 = ServiceLink(
        customer_id=customer2.id,
        port_id=cto2_p1.id,
        onu_device_id=onu2.id,
        status="active",
        notes="Atendimento em ramo independente ativo.",
        version=1,
    )
    session.add(svc_link2)
    session.flush()

    # 11. Ramo com Ponta Aberta (Cabo de 12 FO para aviso de incompletude / ponta aberta)
    cbl_open = Cable(
        code="CBL-BRANCH-OPEN-DEMO",
        model="AS-80-12FO",
        fiber_count=12,
        tube_count=1,
        color_standard="NBR",
        status="installed",
        version=1,
    )
    session.add(cbl_open)
    session.flush()

    seg_open = CableSegment(
        cable_id=cbl_open.id,
        origin_structure_id=struct_ceo.id,
        destination_structure_id=struct_cto3.id,
        map_length_m=1200.0,
        effective_length_m=1200.0,
        length_source="measured",
        status="installed",
        geometry=from_shape(LineString([(-46.6350, -23.5520), (-46.6400, -23.5530)]), srid=4326),
        version=1,
    )
    session.add(seg_open)
    session.flush()

    tube_open = Tube(cable_id=cbl_open.id, number=1, color_name="Verde", version=1)
    session.add(tube_open)
    session.flush()

    fiber_open = Fiber(
        cable_id=cbl_open.id,
        tube_id=tube_open.id,
        global_number=1,
        tube_position=1,
        color_name="Verde",
        version=1,
    )
    session.add(fiber_open)
    session.flush()

    term_open_a = Terminal(
        entity_type="fiber_segment",
        entity_id=seg_open.id,
        structure_id=struct_ceo.id,
        kind="fiber_endpoint",
        label="Open DEMO FO1 Ponta A (CEO)",
        is_occupied=True,
        occupancy="connected",
        version=1,
    )
    term_open_b = Terminal(
        entity_type="fiber_segment",
        entity_id=seg_open.id,
        structure_id=struct_cto3.id,
        kind="fiber_endpoint",
        label="Open DEMO FO1 Ponta B (Ponta Aberta)",
        is_occupied=False,
        occupancy="free",
        version=1,
    )
    session.add_all([term_open_a, term_open_b])
    session.flush()

    fseg_open = FiberSegment(
        cable_segment_id=seg_open.id,
        fiber_id=fiber_open.id,
        fiber_number=1,
        terminal_a_id=term_open_a.id,
        terminal_b_id=term_open_b.id,
        occupancy="free",
        version=1,
    )
    session.add(fseg_open)
    session.flush()

    # Saída 2 do Splitter do CEO conectada a esta fibra aberta
    term_ceo_spl_out2 = Terminal(
        entity_type="splitter",
        structure_id=struct_ceo.id,
        kind="splitter_output",
        label="CEO Splitter OUT #2",
        is_occupied=True,
        occupancy="connected",
        version=1,
    )
    session.add(term_ceo_spl_out2)
    session.flush()

    spl_ceo_out2 = SplitterOutput(
        splitter_id=ceo_splitter.id,
        terminal_id=term_ceo_spl_out2.id,
        output_number=2,
        nominal_loss_db=10.2,
        version=1,
    )
    session.add(spl_ceo_out2)
    session.flush()

    # 12. Fusão com atenuação ausente / não aferida (loss_db=0.0)
    fusion_unmeasured = Connection(
        terminal_a_id=term_ceo_spl_out2.id,
        terminal_b_id=term_open_a.id,
        structure_id=struct_ceo.id,
        connection_type="fusion",
        loss_db=0.0,
        is_active=True,
        notes="Fusão sem aferição de perda óptica (loss_db=0.0 para teste de aviso).",
        version=1,
    )
    session.add(fusion_unmeasured)
    session.flush()

    # 13. Assinante com atenuação degradada para relatórios (CLI-DEMO-003)
    customer3 = Customer(
        code="CLI-DEMO-003",
        name="Gama Indústria Demo S/A",
        phone="(11) 96543-2109",
        email="operacao@gama-demo.com.br",
        address="Rua da Consolação, 200 - São Paulo, SP",
        notes="Cliente com histórico de sinal óptico degradado.",
        version=1,
    )
    session.add(customer3)
    session.flush()

    meas_degraded = OpticalMeasurement(
        terminal_id=term_onu_rx1.id,
        service_link_id=svc_link1.id,
        power_dbm=-28.50,
        wavelength_nm=1490,
        direction="downstream",
        origin="field_power_meter",
        instrument_model="PowerMeter EXFO PPM-350D",
        measured_at=datetime.now(UTC),
        user_id=admin.id,
        predicted_power_dbm=-21.15,
        excess_loss_db=7.35,
        notes="ALERTA: Potência abaixo da sensibilidade (-28.50 dBm < -27.0 dBm). Degradação severa.",
        version=1,
    )
    session.add(meas_degraded)
    session.flush()

    bump_topology_revision(session)
    session.commit()
    print("[+] Cenário transversal B18 provisionado com sucesso!")

    return {
        "admin_email": admin.email,
        "customer_primary": customer1.code,
        "customer_secondary": customer2.code,
        "pop_code": pop_site.code,
        "feeder_cable": feeder_cable.code,
        "dist_cable": dist_cable.code,
        "ceo_code": struct_ceo.code,
        "cto_code": struct_cto1.code,
    }


def main() -> None:
    args = parse_args()
    db_url = get_db_url(args.target_db)
    print(f"[*] Conectando ao banco de dados [{args.target_db}]: {db_url}")

    engine = create_engine(db_url, echo=False)
    with Session(engine) as session:
        if args.clean:
            clean_demo_data(session)

        # Verifica se cenário já existe
        existing = session.scalar(select(Customer).where(Customer.code == "CLI-DEMO-001"))
        if existing and not args.clean:
            print("[!] O cenário de demonstração já está presente no banco de dados.")
            print("    Use --clean para recriar do zero: python scripts/seed_demo.py --clean")
            sys.exit(0)

        summary = seed_demo_scenario(session)
        print("\n=== Resumo do Provisionamento ===")
        for k, v in summary.items():
            print(f"  {k}: {v}")
        print("=================================")


if __name__ == "__main__":
    main()
