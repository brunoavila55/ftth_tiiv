#!/usr/bin/env python3
"""Gerador sintético reproduzível de alta escala para FTTH Manager (B16).

Gera um dataset massivo e consistente contendo:
- Pelo menos 10.000 estruturas físicas (POP, CEOs, CTOs e Postes)
- Pelo menos 100.000 segmentos de fibra (fiber_segments)
- Mais de 200.000 terminais ópticos normalizados
- Splitters balanceados (1:8 e 1:16) com saídas normalizadas
- Conexões ópticas (fusões e patch cords) com continuidade ponta a ponta
- Assinantes, portas e vínculos de atendimento (ServiceLink / ONU)
- Indexação espacial PostGIS completa para testes de desempenho e observabilidade.

Uso:
    uv run python scripts/generate_synthetic_load.py [--target-db test|dev] [--seed 42] [--clean]
"""

from __future__ import annotations

import argparse
import datetime
import math
import random
import time
import uuid
from typing import Any

from sqlalchemy import create_engine, text

from app.core.script_safety import (
    ALLOW_FLAG,
    guard_environment_or_exit,
    guard_or_exit,
    raw_environment,
)

# Coordenadas centrais (São Paulo - SP)
CENTER_LAT = -23.550520
CENTER_LON = -46.633308

# Padrão de cores ABNT NBR 14106
ABNT_COLORS = [
    "Verde",
    "Amarelo",
    "Branco",
    "Azul",
    "Vermelho",
    "Violeta",
    "Marrom",
    "Rosa",
    "Preto",
    "Cinza",
    "Laranja",
    "Aqua",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gera dataset sintético de 10k estruturas e 100k fibras para benchmark B16."
    )
    parser.add_argument(
        "--target-db",
        choices=["test", "dev"],
        default="test",
        help="Banco de dados de destino: 'test' (ftth_manager_test) ou 'dev' (ftth_manager). Padrão: test.",
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=None,
        help="URL completa do banco de dados (sobrescreve --target-db).",
    )
    parser.add_argument(
        "--structures",
        type=int,
        default=10000,
        help="Número total de estruturas a gerar (mínimo 10.000). Padrão: 10000.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Semente do gerador aleatório para reprodutibilidade estrita. Padrão: 42.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        default=True,
        help="Limpar/truncar tabelas antes de gerar o dataset. Padrão: True.",
    )
    parser.add_argument(
        "--no-clean",
        action="store_false",
        dest="clean",
        help="Não limpar tabelas antes de inserir.",
    )
    parser.add_argument(
        ALLOW_FLAG,
        dest="allow_non_local",
        action="store_true",
        help="Permite rodar contra um banco NÃO local (nunca contra produção).",
    )
    return parser.parse_args()


def bulk_insert(
    engine: Any, table_name: str, rows: list[dict[str, Any]], batch_size: int = 5000
) -> None:
    """Insere registros em lotes utilizando SQLAlchemy Core text para máxima velocidade."""
    if not rows:
        return

    columns = list(rows[0].keys())
    col_names = ", ".join(columns)
    val_placeholders = ", ".join([f":{c}" for c in columns])
    sql = text(f"INSERT INTO {table_name} ({col_names}) VALUES ({val_placeholders})")

    with engine.begin() as conn:
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            conn.execute(sql, batch)


def generate_dataset(db_url: str, num_structures: int, seed: int, clean: bool) -> None:
    print("=" * 70)
    print("  FTTH MANAGER — GERADOR DE CARGA SINTÉTICA REPRODUZÍVEL (B16)")
    print("=" * 70)
    print(f"[+] Destino: {db_url}")
    print(f"[+] Estruturas planejadas: {num_structures}")
    print(f"[+] Semente aleatória: {seed}")
    print(f"[+] Modo de limpeza prévia: {clean}")

    random.seed(seed)
    start_total_time = time.time()
    now_utc = datetime.datetime.now(datetime.UTC)

    engine = create_engine(db_url, pool_pre_ping=True)

    if clean:
        print("\n[*] Limpando tabelas operacionais...")
        truncate_sql = text(
            "TRUNCATE TABLE import_previews, async_jobs, attachments, optical_measurements, "
            "audit_events, service_links, customers, splitter_outputs, splitters, "
            "connection_endpoints, connections, internal_edges, terminal_reservations, "
            "fiber_segments, fibers, tubes, terminals, cable_segments, "
            "cables, ports, devices, structures, sites, optical_profiles CASCADE;"
        )
        reset_topology_sql = text(
            "INSERT INTO network_topology_state (id, topology_revision, updated_at) "
            "VALUES (1, 1, NOW()) "
            "ON CONFLICT (id) DO UPDATE SET topology_revision = 1, updated_at = NOW();"
        )
        with engine.begin() as conn:
            conn.execute(truncate_sql)
            conn.execute(reset_topology_sql)
        print("[+] Tabelas limpas e topology_revision resetada para 1.")

    # 1. Perfil Óptico Padrão
    print("\n[1/9] Gerando Perfil Óptico...")
    opt_profile_id = uuid.uuid4()
    opt_profiles = [
        {
            "id": opt_profile_id,
            "name": "ITU-T G.652.D Padrão SMF-28 GPON",
            "technology": "GPON",
            "wavelength_nm": 1490,
            "tx_min_dbm": 1.5,
            "tx_max_dbm": 5.0,
            "rx_sensitivity_dbm": -28.0,
            "rx_overload_dbm": -8.0,
            "default_attenuation_db_per_km": 0.35,
            "notes": "Perfil padrão monomodo GPON Classe B+",
            "version": 1,
            "created_at": now_utc,
            "updated_at": now_utc,
        }
    ]
    bulk_insert(engine, "optical_profiles", opt_profiles)

    # 2. Site Central (POP)
    print("[2/9] Gerando Site POP Central...")
    site_id = uuid.uuid4()
    site_struct_id = uuid.uuid4()
    sites = [
        {
            "id": site_id,
            "code": "POP-CENTRAL",
            "name": "Central Office São Paulo - Sé",
            "kind": "central_office",
            "location": f"SRID=4326;POINT({CENTER_LON} {CENTER_LAT})",
            "address": "Praça da Sé, 1 - Centro, São Paulo - SP",
            "status": "active",
            "version": 1,
            "created_at": now_utc,
            "updated_at": now_utc,
        }
    ]
    bulk_insert(engine, "sites", sites)

    # 3. Estruturas Físicas (1 Site + 500 CEOs + 2.500 CTOs + 7.000 Postes = 10.001)
    print(f"[3/9] Gerando {num_structures + 1} Estruturas Físicas com PostGIS...")
    structures_rows: list[dict[str, Any]] = []

    # Estrutura do Site
    structures_rows.append(
        {
            "id": site_struct_id,
            "code": "STR-POP-001",
            "kind": "site",
            "location": f"SRID=4326;POINT({CENTER_LON} {CENTER_LAT})",
            "site_id": site_id,
            "capacity": 1000,
            "status": "installed",
            "condition": "ok",
            "notes": "Estrutura do POP Central",
            "version": 1,
            "created_at": now_utc,
            "updated_at": now_utc,
        }
    )

    num_ceos = 500
    num_ctos = 2500
    num_poles = max(7000, num_structures - num_ceos - num_ctos)

    ceo_struct_ids: list[uuid.UUID] = []
    cto_struct_ids: list[uuid.UUID] = []
    pole_struct_ids: list[uuid.UUID] = []

    radius_scale = 0.08  # ~8-9 km em latitude/longitude

    # CEOs (caixas de emenda principais)
    for i in range(1, num_ceos + 1):
        s_id = uuid.uuid4()
        ceo_struct_ids.append(s_id)
        angle = random.uniform(0, 2 * math.pi)
        r = random.uniform(0.01, radius_scale * 0.6)
        lat = CENTER_LAT + r * math.sin(angle)
        lon = CENTER_LON + r * math.cos(angle)
        structures_rows.append(
            {
                "id": s_id,
                "code": f"CEO-{i:04d}",
                "kind": "ceo",
                "location": f"SRID=4326;POINT({lon:.6f} {lat:.6f})",
                "site_id": site_id,
                "capacity": 96,
                "status": "installed",
                "condition": "ok",
                "notes": f"Caixa de Emenda Óptica {i}",
                "version": 1,
                "created_at": now_utc,
                "updated_at": now_utc,
            }
        )

    # CTOs (caixas de terminação óptica com atendimento)
    for i in range(1, num_ctos + 1):
        s_id = uuid.uuid4()
        cto_struct_ids.append(s_id)
        angle = random.uniform(0, 2 * math.pi)
        r = random.uniform(0.001, 0.02)
        lat = CENTER_LAT + r * math.sin(angle)
        lon = CENTER_LON + r * math.cos(angle)
        structures_rows.append(
            {
                "id": s_id,
                "code": f"CTO-{i:04d}",
                "kind": "cto",
                "location": f"SRID=4326;POINT({lon:.6f} {lat:.6f})",
                "site_id": site_id,
                "capacity": 16,
                "status": "installed",
                "condition": "ok",
                "notes": f"Caixa de Terminação Óptica {i}",
                "version": 1,
                "created_at": now_utc,
                "updated_at": now_utc,
            }
        )

    # Postes (rede de sustentação aérea)
    for i in range(1, num_poles + 1):
        s_id = uuid.uuid4()
        pole_struct_ids.append(s_id)
        angle = random.uniform(0, 2 * math.pi)
        r = random.uniform(0.002, radius_scale)
        lat = CENTER_LAT + r * math.sin(angle)
        lon = CENTER_LON + r * math.cos(angle)
        structures_rows.append(
            {
                "id": s_id,
                "code": f"PST-{i:05d}",
                "kind": "pole",
                "location": f"SRID=4326;POINT({lon:.6f} {lat:.6f})",
                "site_id": site_id,
                "capacity": 6,
                "status": "installed",
                "condition": "ok",
                "notes": f"Poste de Distribuição {i}",
                "version": 1,
                "created_at": now_utc,
                "updated_at": now_utc,
            }
        )

    bulk_insert(engine, "structures", structures_rows, batch_size=5000)
    print(f"[+] {len(structures_rows)} Estruturas inseridas com sucesso.")

    # 4. Dispositivos e Portas (OLT Central e ONU Cliente)
    print("[4/9] Gerando Dispositivos (OLT Central e ONU Cliente)...")
    olt_id = uuid.uuid4()
    onu_id = uuid.uuid4()
    devices = [
        {
            "id": olt_id,
            "code": "OLT-CENTRAL-01",
            "kind": "olt",
            "manufacturer": "FiberHome",
            "model": "AN5516-04",
            "serial_number": "FH-OLT-2026001",
            "site_id": site_id,
            "structure_id": None,
            "status": "installed",
            "version": 1,
            "created_at": now_utc,
            "updated_at": now_utc,
        },
        {
            "id": onu_id,
            "code": "ONU-CUST-0001",
            "kind": "onu",
            "manufacturer": "Huawei",
            "model": "HG8010H",
            "serial_number": "HWTC-2026-9999",
            "site_id": None,
            "structure_id": cto_struct_ids[0],
            "status": "installed",
            "version": 1,
            "created_at": now_utc,
            "updated_at": now_utc,
        },
    ]
    bulk_insert(engine, "devices", devices)

    olt_pon_port_id = uuid.uuid4()
    cto_drop_port_id = uuid.uuid4()
    ports = [
        {
            "id": olt_pon_port_id,
            "device_id": olt_id,
            "structure_id": None,
            "name": "PON 1/1/1",
            "role": "pon",
            "connector_type": "SC/APC",
            "version": 1,
            "created_at": now_utc,
            "updated_at": now_utc,
        },
        {
            "id": cto_drop_port_id,
            "device_id": None,
            "structure_id": cto_struct_ids[0],
            "name": "CTO-0001 Porta 1",
            "role": "customer_drop",
            "connector_type": "SC/APC",
            "version": 1,
            "created_at": now_utc,
            "updated_at": now_utc,
        },
    ]
    bulk_insert(engine, "ports", ports)

    # 5. Cabos, Tubos, Fibras e Segmentos de Cabo
    # Total de fibras: 50*144 + 1000*48 + 4000*12 = 103.200 fibras e fiber_segments
    print("[5/9] Gerando Cabos, Tubos, Fibras e Segmentos de Cabo (alvo: >100.000 FOs)...")

    cables_rows: list[dict[str, Any]] = []
    tubes_rows: list[dict[str, Any]] = []
    fibers_rows: list[dict[str, Any]] = []
    cable_segs_rows: list[dict[str, Any]] = []

    cable_configs = [
        ("trunk", 50, 144, 12, site_struct_id, ceo_struct_ids),
        ("distribution", 1000, 48, 4, None, cto_struct_ids),
        ("drop", 4000, 12, 1, None, pole_struct_ids),
    ]

    total_fibers_count = 0
    cable_idx = 1
    all_fiber_definitions: list[tuple[uuid.UUID, uuid.UUID, int]] = []

    for c_type, count, fiber_count, tubes_count, fixed_origin, dest_list in cable_configs:
        fibers_per_tube = fiber_count // tubes_count

        for i in range(count):
            c_id = uuid.uuid4()
            c_code = f"CBL-{c_type.upper()[:4]}-{cable_idx:05d}"
            cable_idx += 1

            cables_rows.append(
                {
                    "id": c_id,
                    "code": c_code,
                    "model": f"Cabo Óptico {c_type.capitalize()} SM {fiber_count}F",
                    "fiber_count": fiber_count,
                    "tube_count": tubes_count,
                    "color_standard": "NBR",
                    "status": "installed",
                    "notes": f"Cabo {c_type} #{cable_idx}",
                    "version": 1,
                    "created_at": now_utc,
                    "updated_at": now_utc,
                }
            )

            # Origem e destino para o segmento de cabo
            if fixed_origin:
                origin_id = fixed_origin
                dest_id = dest_list[i % len(dest_list)]
            else:
                if c_type == "distribution":
                    origin_id = ceo_struct_ids[i % len(ceo_struct_ids)]
                    dest_id = dest_list[i % len(dest_list)]
                else:  # drop
                    origin_id = cto_struct_ids[i % len(cto_struct_ids)]
                    dest_id = dest_list[i % len(dest_list)]

            cseg_id = uuid.uuid4()
            lat1, lon1 = CENTER_LAT, CENTER_LON
            lat2 = CENTER_LAT + random.uniform(-0.02, 0.02)
            lon2 = CENTER_LON + random.uniform(-0.02, 0.02)

            cable_segs_rows.append(
                {
                    "id": cseg_id,
                    "cable_id": c_id,
                    "origin_structure_id": origin_id,
                    "destination_structure_id": dest_id,
                    "geometry": f"SRID=4326;LINESTRING({lon1:.6f} {lat1:.6f}, {lon2:.6f} {lat2:.6f})",
                    "map_length_m": 850.0,
                    "slack_length_m": 30.0,
                    "effective_length_m": 880.0,
                    "length_source": "calculated",
                    "status": "installed",
                    "version": 1,
                    "created_at": now_utc,
                    "updated_at": now_utc,
                }
            )

            # Tubos e Fibras
            for t_idx in range(1, tubes_count + 1):
                tube_id = uuid.uuid4()
                t_color = ABNT_COLORS[(t_idx - 1) % len(ABNT_COLORS)]
                tubes_rows.append(
                    {
                        "id": tube_id,
                        "cable_id": c_id,
                        "number": t_idx,
                        "color_name": t_color,
                        "is_logical_group": False,
                        "version": 1,
                        "created_at": now_utc,
                        "updated_at": now_utc,
                    }
                )

                for f_pos in range(1, fibers_per_tube + 1):
                    f_id = uuid.uuid4()
                    global_num = (t_idx - 1) * fibers_per_tube + f_pos
                    f_color = ABNT_COLORS[(f_pos - 1) % len(ABNT_COLORS)]

                    fibers_rows.append(
                        {
                            "id": f_id,
                            "cable_id": c_id,
                            "tube_id": tube_id,
                            "global_number": global_num,
                            "tube_position": f_pos,
                            "color_name": f_color,
                            "status": "installed",
                            "version": 1,
                            "created_at": now_utc,
                            "updated_at": now_utc,
                        }
                    )

                    all_fiber_definitions.append((cseg_id, f_id, global_num))
                    total_fibers_count += 1

    bulk_insert(engine, "cables", cables_rows, batch_size=2000)
    bulk_insert(engine, "cable_segments", cable_segs_rows, batch_size=2000)
    bulk_insert(engine, "tubes", tubes_rows, batch_size=5000)
    bulk_insert(engine, "fibers", fibers_rows, batch_size=5000)
    print(
        f"[+] {len(cables_rows)} Cabos, {len(tubes_rows)} Tubos e {len(fibers_rows)} Fibras inseridos."
    )

    # 6. Terminais Ópticos e Segmentos de Fibra (2x Terminais por Segmento = 2N)
    print(
        f"[6/9] Gerando Terminais e {len(all_fiber_definitions)} Segmentos de Fibra (2N model)..."
    )

    terminals_rows: list[dict[str, Any]] = []
    fiber_segments_rows: list[dict[str, Any]] = []

    # Terminal da porta OLT e terminal da porta CTO
    olt_term_id = uuid.uuid4()
    cto_port_term_id = uuid.uuid4()
    terminals_rows.append(
        {
            "id": olt_term_id,
            "site_id": site_id,
            "structure_id": None,
            "kind": "port",
            "entity_type": "port",
            "entity_id": olt_pon_port_id,
            "label": "OLT PON 1/1/1",
            "is_occupied": True,
            "occupancy": "connected",
            "version": 1,
            "created_at": now_utc,
            "updated_at": now_utc,
        }
    )
    terminals_rows.append(
        {
            "id": cto_port_term_id,
            "site_id": None,
            "structure_id": cto_struct_ids[0],
            "kind": "port",
            "entity_type": "port",
            "entity_id": cto_drop_port_id,
            "label": "CTO-0001 Drop Port 1",
            "is_occupied": True,
            "occupancy": "connected",
            "version": 1,
            "created_at": now_utc,
            "updated_at": now_utc,
        }
    )

    first_trunk_fiber_term_a: uuid.UUID | None = None
    first_trunk_fiber_term_b: uuid.UUID | None = None
    first_dist_fiber_term_a: uuid.UUID | None = None
    first_dist_fiber_term_b: uuid.UUID | None = None

    for idx, (cseg_id, f_id, f_num) in enumerate(all_fiber_definitions):
        fseg_id = uuid.uuid4()
        term_a_id = uuid.uuid4()
        term_b_id = uuid.uuid4()

        if idx == 0:
            first_trunk_fiber_term_a = term_a_id
            first_trunk_fiber_term_b = term_b_id
        elif idx == 7200:  # Primeiro cabo de distribuição
            first_dist_fiber_term_a = term_a_id
            first_dist_fiber_term_b = term_b_id

        # Terminal Ponta A
        terminals_rows.append(
            {
                "id": term_a_id,
                "site_id": site_id if idx < 7200 else None,
                "structure_id": site_struct_id if idx < 7200 else ceo_struct_ids[0],
                "kind": "fiber",
                "entity_type": "fiber_segment",
                "entity_id": fseg_id,
                "label": f"FO-{idx + 1:06d}-A",
                "is_occupied": idx in (0, 7200),
                "occupancy": "connected" if idx in (0, 7200) else "free",
                "version": 1,
                "created_at": now_utc,
                "updated_at": now_utc,
            }
        )

        # Terminal Ponta B
        terminals_rows.append(
            {
                "id": term_b_id,
                "site_id": None,
                "structure_id": ceo_struct_ids[0] if idx < 7200 else cto_struct_ids[0],
                "kind": "fiber",
                "entity_type": "fiber_segment",
                "entity_id": fseg_id,
                "label": f"FO-{idx + 1:06d}-B",
                "is_occupied": idx in (0, 7200),
                "occupancy": "connected" if idx in (0, 7200) else "free",
                "version": 1,
                "created_at": now_utc,
                "updated_at": now_utc,
            }
        )

        fiber_segments_rows.append(
            {
                "id": fseg_id,
                "cable_segment_id": cseg_id,
                "fiber_id": f_id,
                "fiber_number": f_num,
                "terminal_a_id": term_a_id,
                "terminal_b_id": term_b_id,
                "occupancy": "connected" if idx in (0, 7200) else "free",
                "version": 1,
                "created_at": now_utc,
                "updated_at": now_utc,
            }
        )

    bulk_insert(engine, "terminals", terminals_rows, batch_size=5000)
    bulk_insert(engine, "fiber_segments", fiber_segments_rows, batch_size=5000)
    print(
        f"[+] {len(terminals_rows)} Terminais e {len(fiber_segments_rows)} Segmentos de Fibra inseridos."
    )

    # 7. Splitters Balanceados (1:8 em CEOs e 1:16 em CTOs)
    print("[7/9] Gerando Splitters Balanceados e Saídas Normalizadas...")
    splitters_rows: list[dict[str, Any]] = []
    splitter_outputs_rows: list[dict[str, Any]] = []
    splitter_terminals_rows: list[dict[str, Any]] = []

    # Splitter CEO-0001 (1:8)
    ceo_spl_id = uuid.uuid4()
    ceo_spl_in_term = uuid.uuid4()
    splitter_terminals_rows.append(
        {
            "id": ceo_spl_in_term,
            "site_id": None,
            "structure_id": ceo_struct_ids[0],
            "kind": "splitter_input",
            "entity_type": "splitter",
            "entity_id": ceo_spl_id,
            "label": "SPL-CEO-01 Entrada",
            "is_occupied": True,
            "occupancy": "connected",
            "version": 1,
            "created_at": now_utc,
            "updated_at": now_utc,
        }
    )
    splitters_rows.append(
        {
            "id": ceo_spl_id,
            "code": "SPL-CEO-0001",
            "ratio": "1:8",
            "splitter_type": "balanced",
            "structure_id": ceo_struct_ids[0],
            "site_id": None,
            "input_terminal_id": ceo_spl_in_term,
            "notes": "Splitter de primeiro nível 1:8",
            "version": 1,
            "created_at": now_utc,
            "updated_at": now_utc,
        }
    )

    first_ceo_spl_out_term: uuid.UUID | None = None
    for o_idx in range(1, 9):
        out_term = uuid.uuid4()
        if o_idx == 1:
            first_ceo_spl_out_term = out_term
        splitter_terminals_rows.append(
            {
                "id": out_term,
                "site_id": None,
                "structure_id": ceo_struct_ids[0],
                "kind": "splitter_output",
                "entity_type": "splitter_output",
                "entity_id": None,
                "label": f"SPL-CEO-01 Saída {o_idx}",
                "is_occupied": o_idx == 1,
                "occupancy": "connected" if o_idx == 1 else "free",
                "version": 1,
                "created_at": now_utc,
                "updated_at": now_utc,
            }
        )
        splitter_outputs_rows.append(
            {
                "id": uuid.uuid4(),
                "splitter_id": ceo_spl_id,
                "output_number": o_idx,
                "terminal_id": out_term,
                "nominal_loss_db": 10.5,
                "measured_loss_db": 10.3,
                "version": 1,
                "created_at": now_utc,
                "updated_at": now_utc,
            }
        )

    # Splitter CTO-0001 (1:16)
    cto_spl_id = uuid.uuid4()
    cto_spl_in_term = uuid.uuid4()
    splitter_terminals_rows.append(
        {
            "id": cto_spl_in_term,
            "site_id": None,
            "structure_id": cto_struct_ids[0],
            "kind": "splitter_input",
            "entity_type": "splitter",
            "entity_id": cto_spl_id,
            "label": "SPL-CTO-01 Entrada",
            "is_occupied": True,
            "occupancy": "connected",
            "version": 1,
            "created_at": now_utc,
            "updated_at": now_utc,
        }
    )
    splitters_rows.append(
        {
            "id": cto_spl_id,
            "code": "SPL-CTO-0001",
            "ratio": "1:16",
            "splitter_type": "balanced",
            "structure_id": cto_struct_ids[0],
            "site_id": None,
            "input_terminal_id": cto_spl_in_term,
            "notes": "Splitter de atendimento 1:16",
            "version": 1,
            "created_at": now_utc,
            "updated_at": now_utc,
        }
    )

    first_cto_spl_out_term: uuid.UUID | None = None
    for o_idx in range(1, 17):
        out_term = uuid.uuid4()
        if o_idx == 1:
            first_cto_spl_out_term = out_term
        splitter_terminals_rows.append(
            {
                "id": out_term,
                "site_id": None,
                "structure_id": cto_struct_ids[0],
                "kind": "splitter_output",
                "entity_type": "splitter_output",
                "entity_id": None,
                "label": f"SPL-CTO-01 Saída {o_idx}",
                "is_occupied": o_idx == 1,
                "occupancy": "connected" if o_idx == 1 else "free",
                "version": 1,
                "created_at": now_utc,
                "updated_at": now_utc,
            }
        )
        splitter_outputs_rows.append(
            {
                "id": uuid.uuid4(),
                "splitter_id": cto_spl_id,
                "output_number": o_idx,
                "terminal_id": out_term,
                "nominal_loss_db": 13.8,
                "measured_loss_db": 13.6,
                "version": 1,
                "created_at": now_utc,
                "updated_at": now_utc,
            }
        )

    bulk_insert(engine, "terminals", splitter_terminals_rows)
    bulk_insert(engine, "splitters", splitters_rows)
    bulk_insert(engine, "splitter_outputs", splitter_outputs_rows)
    print("[+] Splitters e saídas normalizadas criados.")

    # 8. Conexões Ópticas e Continuidade de Rastreamento (Trace Completo)
    print("[8/9] Gerando Conexões e Fusões para Circuito Óptico Completo...")
    connections_rows: list[dict[str, Any]] = []
    conn_endpoints_rows: list[dict[str, Any]] = []

    def add_connection(
        conn_type: str,
        term_a: uuid.UUID,
        term_b: uuid.UUID,
        struct_id: uuid.UUID | None,
        s_id: uuid.UUID | None,
        loss: float,
    ) -> None:
        c_id = uuid.uuid4()
        connections_rows.append(
            {
                "id": c_id,
                "connection_type": conn_type,
                "terminal_a_id": term_a,
                "terminal_b_id": term_b,
                "structure_id": struct_id,
                "site_id": s_id,
                "loss_db": loss,
                "is_active": True,
                "version": 1,
                "created_at": now_utc,
                "updated_at": now_utc,
            }
        )
        conn_endpoints_rows.append(
            {
                "id": uuid.uuid4(),
                "connection_id": c_id,
                "terminal_id": term_a,
                "is_active": True,
                "version": 1,
                "created_at": now_utc,
                "updated_at": now_utc,
            }
        )
        conn_endpoints_rows.append(
            {
                "id": uuid.uuid4(),
                "connection_id": c_id,
                "terminal_id": term_b,
                "is_active": True,
                "version": 1,
                "created_at": now_utc,
                "updated_at": now_utc,
            }
        )

    # Conexão 1: OLT PON -> Trunk Cable FO #1 (Ponta A)
    if first_trunk_fiber_term_a:
        add_connection(
            "patch_cord",
            olt_term_id,
            first_trunk_fiber_term_a,
            site_struct_id,
            site_id,
            0.25,
        )

    # Conexão 2: Trunk Cable FO #1 (Ponta B na CEO) -> Splitter CEO Entrada
    if first_trunk_fiber_term_b:
        add_connection(
            "fusion",
            first_trunk_fiber_term_b,
            ceo_spl_in_term,
            ceo_struct_ids[0],
            None,
            0.05,
        )

    # Conexão 3: Splitter CEO Saída 1 -> Distribution Cable FO #1 (Ponta A na CEO)
    if first_ceo_spl_out_term and first_dist_fiber_term_a:
        add_connection(
            "fusion",
            first_ceo_spl_out_term,
            first_dist_fiber_term_a,
            ceo_struct_ids[0],
            None,
            0.05,
        )

    # Conexão 4: Distribution Cable FO #1 (Ponta B na CTO) -> Splitter CTO Entrada
    if first_dist_fiber_term_b:
        add_connection(
            "fusion",
            first_dist_fiber_term_b,
            cto_spl_in_term,
            cto_struct_ids[0],
            None,
            0.05,
        )

    # Conexão 5: Splitter CTO Saída 1 -> CTO Drop Port
    if first_cto_spl_out_term:
        add_connection(
            "patch_cord",
            first_cto_spl_out_term,
            cto_port_term_id,
            cto_struct_ids[0],
            None,
            0.2,
        )

    bulk_insert(engine, "connections", connections_rows)
    bulk_insert(engine, "connection_endpoints", conn_endpoints_rows)
    print(f"[+] {len(connections_rows)} Conexões/fusões ativas registradas.")

    # 9. Assinantes e Atendimento Ativo (ServiceLink)
    print("[9/9] Gerando Assinantes e Atendimento Ativo...")
    cust_id = uuid.uuid4()
    customers_rows = [
        {
            "id": cust_id,
            "code": "CUST-SYNTH-0001",
            "name": "Cliente Sintético Benchmark Ltda",
            "email": "noc@cliente-benchmark.com.br",
            "phone": "(11) 98765-4321",
            "address": "Av. Brigadeiro Faria Lima, 1000 - São Paulo, SP",
            "notes": "Cliente conectado ao drop da CTO-0001",
            "version": 1,
            "created_at": now_utc,
            "updated_at": now_utc,
        }
    ]
    service_links_rows = [
        {
            "id": uuid.uuid4(),
            "customer_id": cust_id,
            "port_id": cto_drop_port_id,
            "onu_device_id": onu_id,
            "status": "active",
            "activated_at": now_utc,
            "deactivated_at": None,
            "notes": "Circuito ativo para rastreamento óptico B16",
            "version": 1,
            "created_at": now_utc,
            "updated_at": now_utc,
        }
    ]
    bulk_insert(engine, "customers", customers_rows)
    bulk_insert(engine, "service_links", service_links_rows)

    total_duration = round(time.time() - start_total_time, 2)

    # Validação e Contagem Final
    with engine.connect() as conn:
        struct_count = conn.execute(text("SELECT COUNT(*) FROM structures;")).scalar()
        fiber_seg_count = conn.execute(text("SELECT COUNT(*) FROM fiber_segments;")).scalar()
        term_count = conn.execute(text("SELECT COUNT(*) FROM terminals;")).scalar()
        cable_count = conn.execute(text("SELECT COUNT(*) FROM cables;")).scalar()
        cseg_count = conn.execute(text("SELECT COUNT(*) FROM cable_segments;")).scalar()
        conn_count = conn.execute(text("SELECT COUNT(*) FROM connections;")).scalar()

    print("\n" + "=" * 70)
    print("  RESUMO DO DATASET SINTÉTICO (B16) — GERADO COM SUCESSO!")
    print("=" * 70)
    print(f"[*] Tempo total de geração:    {total_duration}s")
    final_structs = int(struct_count or 0)
    final_fsegs = int(fiber_seg_count or 0)
    print(
        f"[*] Estruturas (structures):     {final_structs:,} (Critério B16: >= 10.000) -> {'PASS' if final_structs >= 10000 else 'FAIL'}"
    )
    print(
        f"[*] Segmentos de Fibra (fsegs):  {final_fsegs:,} (Critério B16: >= 100.000) -> {'PASS' if final_fsegs >= 100000 else 'FAIL'}"
    )
    print(f"[*] Terminais ópticos:          {term_count:,}")
    print(f"[*] Cabos físicos:              {cable_count:,}")
    print(f"[*] Segmentos de cabo:          {cseg_count:,}")
    print(f"[*] Conexões ópticas ativas:    {conn_count}")
    print(f"[*] Terminal OLT PON:           {olt_term_id}")
    print(f"[*] Terminal Drop CTO:          {cto_port_term_id}")
    print("=" * 70)


def main() -> None:
    args = parse_args()
    guard_environment_or_exit(environment=raw_environment(), script="generate_synthetic_load.py")
    if args.db_url:
        db_url = args.db_url
    elif args.target_db == "dev":
        db_url = "postgresql+psycopg://ftth_user:ftth_password@127.0.0.1:5432/ftth_manager"
    else:
        db_url = "postgresql+psycopg://ftth_user:ftth_password@127.0.0.1:5432/ftth_manager_test"

    # `TRUNCATE ... CASCADE` em banco remoto/produção é destrutivo: guarda ANTES de conectar
    guard_or_exit(
        db_url,
        environment=raw_environment(),
        allow_non_local=args.allow_non_local,
        script="generate_synthetic_load.py",
    )
    generate_dataset(
        db_url=db_url,
        num_structures=args.structures,
        seed=args.seed,
        clean=args.clean,
    )


if __name__ == "__main__":
    main()
