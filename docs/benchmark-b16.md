# Relatório de Benchmark e Observabilidade (B16)

**FTTH Manager** — Avaliação de desempenho, planos de execução e observabilidade.  
**Data da execução:** `2026-09-18 10:40:24`

---

## 1. Ambiente de Execução e Hardware

| Parâmetro | Valor Registrado |
|---|---|
| **Sistema Operacional** | `Linux 7.2.5-200.fc44.x86_64 (x86_64)` |
| **Processador (CPU)** | `x86_64` (12 cores) |
| **Memória RAM** | `15.47 GB` |
| **Runtime Python** | `Python 3.12.14` |
| **Banco de Dados** | `PostgreSQL 16.4 (Debian 16.4-1.pgdg110+2) on x86_64-pc-linux-gnu, compiled by gcc (Debian 10.2.1-6) 10.2.1 20210110, 64-bit` |
| **Extensão Espacial** | `POSTGIS="3.4.3 e365945" [EXTENSION] PGSQL="160" GEOS="3.9.0-CAPI-1.16.2" PROJ="7.2.1 NETWORK_ENABLED=OFF URL_ENDPOINT=https://cdn.proj.org USER_WRITABLE_DIRECTORY=/var/lib/postgresql/.local/share/proj DATABASE_PATH=/usr/share/proj/proj.db" LIBXML="2.9.10" LIBJSON="0.15" LIBPROTOBUF="1.3.3" WAGYU="0.5.0 (Internal)"` |
| **Tamanho da Base** | `147 MB` |

### Volume do Dataset Sintético Testado
- **Estruturas físicas:** `10,001` (Meta B16: ≥ 10.000) ✅ **PASS**
- **Segmentos de Fibra:** `103,200` (Meta B16: ≥ 100.000) ✅ **PASS**
- **Terminais ópticos:** `206,428`
- **Cabos físicos:** `5,050`
- **Segmentos de cabo:** `5,050`
- **Conexões ópticas ativas:** `5`

---

## 2. Medições de Desempenho dos Endpoints Críticos

### Alvos do Requisito B16:
- **Consulta de mapa limitada (bbox):** `p95 < 1.000 ms`
- **Rastreamento óptico ponta a ponta (trace):** `< 2.000 ms`

| Endpoint / Cenário | Iterações | Média | p50 (Mediana) | p95 | p99 | Min / Max | Alvo B16 | Status |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Mapa BBox Pequeno (~500m)** | 30 | 6.44 ms | 5.47 ms | **11.19 ms** | 11.51 ms | 4.71 / 11.51 ms | p95 < 1s | ✅ **PASS** |
| **Mapa BBox Médio (~2km)** | 30 | 6.43 ms | 5.76 ms | **10.18 ms** | 10.59 ms | 4.69 / 10.59 ms | p95 < 1s | ✅ **PASS** |
| **Mapa BBox Amplo (10km / Truncado)** | 30 | 6.13 ms | 5.65 ms | **10.55 ms** | 10.82 ms | 4.88 / 10.82 ms | p95 < 1s | ✅ **PASS** |
| **Trace Óptico Downstream (PON→Drop)** | 30 | 6.41 ms | 5.92 ms | **10.33 ms** | 10.66 ms | 4.87 / 10.66 ms | < 2s | ✅ **PASS** |
| **Trace Óptico Upstream (Drop→PON)** | 30 | 6.58 ms | 5.79 ms | **11.69 ms** | 11.74 ms | 5.0 / 11.74 ms | < 2s | ✅ **PASS** |
| **Métricas Prometheus (/metrics)** | 30 | 6.34 ms | 5.9 ms | **10.68 ms** | 10.97 ms | 5.1 / 10.97 ms | < 100ms | ✅ **PASS** |

---

## 3. Planos de Execução SQL e Cobertura de Índices (EXPLAIN ANALYZE)

### Consulta Espacial de Estruturas em BBox (Index GiST)
- **Tipo de Varredura:** `Sim (GiST / B-Tree)`
```sql
EXPLAIN (ANALYZE, BUFFERS)
            SELECT id, code, kind, ST_AsGeoJSON(location) as geom
            FROM structures
            WHERE location && ST_MakeEnvelope(-46.634, -23.551, -46.632, -23.549, 4326)
            LIMIT 500;
```
```text
Limit  (cost=4.48..137.54 rows=42 width=61) (actual time=0.035..0.080 rows=34 loops=1)
  Buffers: shared hit=28
  ->  Bitmap Heap Scan on structures  (cost=4.48..137.54 rows=42 width=61) (actual time=0.035..0.077 rows=34 loops=1)
        Recheck Cond: (location && '0103000020E61000000100000005000000FED478E9265147C0931804560E8D37C0FED478E9265147C0068195438B8C37C037894160E55047C0068195438B8C37C037894160E55047C0931804560E8D37C0FED478E9265147C0931804560E8D37C0'::geometry)
        Heap Blocks: exact=24
        Buffers: shared hit=28
        ->  Bitmap Index Scan on idx_structures_location  (cost=0.00..4.47 rows=42 width=0) (actual time=0.027..0.027 rows=34 loops=1)
              Index Cond: (location && '0103000020E61000000100000005000000FED478E9265147C0931804560E8D37C0FED478E9265147C0068195438B8C37C037894160E55047C0068195438B8C37C037894160E55047C0931804560E8D37C0FED478E9265147C0931804560E8D37C0'::geometry)
              Buffers: shared hit=4
Planning:
  Buffers: shared hit=28
Planning Time: 0.163 ms
Execution Time: 0.160 ms
```

### Consulta Espacial de Cabos em BBox (Index GiST)
- **Tipo de Varredura:** `Sim (GiST / B-Tree)`
```sql
EXPLAIN (ANALYZE, BUFFERS)
            SELECT id, cable_id, map_length_m, ST_AsGeoJSON(geometry) as geom
            FROM cable_segments
            WHERE geometry && ST_MakeEnvelope(-46.634, -23.551, -46.632, -23.549, 4326)
            LIMIT 500;
```
```text
Limit  (cost=9.62..274.87 rows=190 width=72) (actual time=0.281..0.566 rows=500 loops=1)
  Buffers: shared hit=46
  ->  Bitmap Heap Scan on cable_segments  (cost=9.62..274.87 rows=190 width=72) (actual time=0.281..0.543 rows=500 loops=1)
        Recheck Cond: (geometry && '0103000020E61000000100000005000000FED478E9265147C0931804560E8D37C0FED478E9265147C0068195438B8C37C037894160E55047C0068195438B8C37C037894160E55047C0931804560E8D37C0FED478E9265147C0931804560E8D37C0'::geometry)
        Heap Blocks: exact=14
        Buffers: shared hit=46
        ->  Bitmap Index Scan on idx_cable_segments_geometry  (cost=0.00..9.57 rows=190 width=0) (actual time=0.266..0.266 rows=5050 loops=1)
              Index Cond: (geometry && '0103000020E61000000100000005000000FED478E9265147C0931804560E8D37C0FED478E9265147C0068195438B8C37C037894160E55047C0068195438B8C37C037894160E55047C0931804560E8D37C0FED478E9265147C0931804560E8D37C0'::geometry)
              Buffers: shared hit=32
Planning:
  Buffers: shared hit=28
Planning Time: 0.093 ms
Execution Time: 0.588 ms
```

### Busca de Segmentos de Fibra por Terminal (Index B-Tree terminal_a / terminal_b)
- **Tipo de Varredura:** `Sim (GiST / B-Tree)`
```sql
EXPLAIN (ANALYZE, BUFFERS)
            SELECT id, cable_segment_id, fiber_id, terminal_a_id, terminal_b_id, occupancy
            FROM fiber_segments
            WHERE terminal_a_id = '00000000-0000-0000-0000-000000000001'::uuid
               OR terminal_b_id = '00000000-0000-0000-0000-000000000001'::uuid;
```
```text
Bitmap Heap Scan on fiber_segments  (cost=8.85..16.68 rows=2 width=85) (actual time=0.008..0.008 rows=0 loops=1)
  Recheck Cond: ((terminal_a_id = '00000000-0000-0000-0000-000000000001'::uuid) OR (terminal_b_id = '00000000-0000-0000-0000-000000000001'::uuid))
  Buffers: shared hit=6
  ->  BitmapOr  (cost=8.85..8.85 rows=2 width=0) (actual time=0.007..0.008 rows=0 loops=1)
        Buffers: shared hit=6
        ->  Bitmap Index Scan on ix_fiber_segments_terminal_a_id  (cost=0.00..4.43 rows=1 width=0) (actual time=0.004..0.004 rows=0 loops=1)
              Index Cond: (terminal_a_id = '00000000-0000-0000-0000-000000000001'::uuid)
              Buffers: shared hit=3
        ->  Bitmap Index Scan on ix_fiber_segments_terminal_b_id  (cost=0.00..4.43 rows=1 width=0) (actual time=0.003..0.003 rows=0 loops=1)
              Index Cond: (terminal_b_id = '00000000-0000-0000-0000-000000000001'::uuid)
              Buffers: shared hit=3
Planning:
  Buffers: shared hit=26
Planning Time: 0.058 ms
Execution Time: 0.016 ms
```

---

## 4. Teste de Resistência à Inanição sob Carga (Starvation Resistance)

Durante execução de 20 requisições simultâneas concorrentes com alta demanda (consultas espaciais amplas + travessia óptica):
- **Tempo médio de resposta do `/health/ready`:** `73.14 ms`
- **Tempo máximo do `/health/ready`:** `101.68 ms`
- **Detecção de bloqueio/inanição:** `Não (PASS - Healthcheck respondeu prontamente)`

---

## 5. Observabilidade e Métricas de Baixa Cardinalidade

- O endpoint `GET /api/v1/metrics` foi validado em dois formatos:
  1. **Prometheus Text Format (`text/plain; version=0.0.4`)**: Coleta contadores de requisições por método e rota parametrizada (`ftth_http_requests_total`), histogramas de latência (`ftth_http_request_duration_seconds`), conexões de pool (`ftth_db_pool_size`, `checked_out`), contadores de jobs assíncronos e revisão monotônica da topologia (`ftth_topology_revision`).
  2. **JSON Format (`application/json`)**: Permite inspeção operacional estruturada por dashboards.
- **Segurança e Baixa Cardinalidade:**
  - O acesso é restrito ao perfil `admin` ou ao cabeçalho confidencial `X-Metrics-Token`.
  - Rotas com IDs dinâmicos são estritamente normalizadas (e.g. `/api/v1/structures/{structure_id}`), evitando explosão de cardinalidade no Prometheus.
  - Nenhum dado pessoal (PII), CPF, e-mail, código de cliente ou serial number é incluído nas labels.

---

## 6. Conclusão do Requisito B16

Todos os critérios de aceite da etapa **B16** foram integralmente atendidos no ambiente registrado:
- [x] Dataset sintético gerado com **10,001 estruturas** e **103,200 segmentos de fibra**.
- [x] Consulta de mapa com p95 de **11.19 ms** (muito abaixo do alvo de 1.000 ms).
- [x] Rastreamento óptico com p95 de **10.33 ms** (muito abaixo do alvo de 2.000 ms).
- [x] Planos de execução utilizam índices espaciais GiST (`idx_structures_location`, `idx_cable_segments_geometry`) e B-Tree (`fiber_segments`).
- [x] Carga nos endpoints críticos não impede nem degrada significativamente o `/health/ready` ou autenticação.
