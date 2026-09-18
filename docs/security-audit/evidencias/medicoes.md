# Evidências de medição (saídas literais)

Ambiente: PostgreSQL 16 + PostGIS 3.4 **descartável** (`docker run --rm`, `127.0.0.1:55432`, sem volume), migrado com `alembic upgrade head`
e populado com o gerador sintético do próprio repositório (`backend/scripts/generate_synthetic_load.py --db-url <descartável> --structures 10000`).
Todas as medições são *in-process* (Starlette `TestClient`) — indicam ordem de grandeza e proporção, não capacidade de produção.
Scripts: `docs/security-audit/tools/measure*.py` (abortam se `DATABASE_URL` não apontar para `127.0.0.1:55432/audit`).

## Dataset

```
ROWS {"users": 0, "sites": 1, "structures": 10001, "devices": 2, "ports": 2, "cables": 5050, "cable_segments": 5050,
      "fibers": 103200, "fiber_segments": 103200, "terminals": 206428, "connections": 5, "customers": 1, "service_links": 1, ...}
```

## measure.py — EXPLAIN e dashboard (PERF-01, PERF-03, PERF-06, PERF-07, SEC-01)

```
### search structures ILIKE %x% (code)
  ->  Seq Scan on structures  (actual time=4.581..4.581 rows=0 loops=1)   Rows Removed by Filter: 10001
Execution Time: 4.588 ms

### structures ORDER BY created_at DESC OFFSET 9000
  ->  Sort ... Sort Method: quicksort  Memory: 2920kB   ->  Seq Scan on structures (rows=10001)
Execution Time: 5.924 ms

### count(*) structures            Execution Time: 1.415 ms

### GET /api/v1/dashboard/summary (SEM auth) run1: status=200 1524 ms, 2514 SQL statements
### GET /api/v1/dashboard/summary (SEM auth) run2: status=200 1018 ms, 2514 SQL statements
### GET /api/v1/dashboard/summary (SEM auth) run3: status=200 1129 ms, 2514 SQL statements
### GET /api/v1/search?q=OLT (SEM auth): status=200 23 ms, 4 SQL; groups=['device']
```

## measure2.py — viewer, /metrics, impacto, cardinalidade (SEC-02, SEC-03, PERF-02, PERF-03, EST-12, EST-13)

```
### terminals(entity_type,entity_id) lookup:  Parallel Seq Scan on terminals  Rows Removed by Filter: 68809  Execution Time: 12.526 ms (14.406 ms na 2ª execução)
/auth/me as viewer: 200 viewer
### VIEWER GET /customers: 200 [('id',…), ('code',…), ('name',…), ('phone',…), ('email',…), ('address',…), ('notes',…), ('version',…)]
### VIEWER GET /attachments: 403
### VIEWER GET /audit-events: 403
### VIEWER GET /jobs/<uuid>: 404
### GET /customers/not-a-uuid: 500 application/problem+json
### GET /metrics com token default do código: 200
### VIEWER POST /topology/impact (1 cliente, 1 vínculo): status=200 104 ms, 62 SQL
### VIEWER POST /topology/impact (1 cliente, 1 vínculo): status=200 80 ms, 62 SQL
### métricas: chaves _http_requests antes=8 depois de 300 GETs a paths 404 distintos=308
```

## measure3.py — CSRF Origin, defaults de configuração, Pillow (SEC-09, SEC-05, SEC-02, PERF-04)

```
Origin='http://localhost:3000'                       -> (401, 'invalid_credentials')
Origin='https://evil.example'                        -> (403, 'csrf_origin_mismatch')
Origin='http://localhost:3000.evil.example'          -> (401, 'invalid_credentials')      # passou na checagem de Origin
Origin='http://127.0.0.1:3000.attacker.test'         -> (401, 'invalid_credentials')      # passou na checagem de Origin
compose METRICS_TOKEN definido; Settings.METRICS_SECRET_TOKEN começa com: dev-… | igual ao default do código: True
ENVIRONMENT=production aceita SECRET_KEY default? dev-… is_production: True
DecompressionBombError bases: ['DecompressionBombError', 'Exception', 'BaseException', 'object'] | MAX_IMAGE_PIXELS: 89478485
```

## measure4.py — upload de imagem (PERF-04, EST-09)

```
PNG 9400x9400 = 88.4 Mpx, tamanho do arquivo = 100 KiB (limite de upload = 10 MiB)
passa em inspect_file_content: ('image/png', '.png')
generate_thumbnail_image: 0.67s, thumb=ok, RSS pico 516 MiB (antes 177 MiB) => +339 MiB por upload

PNG 14000x14000 (196 Mpx), 23.3 KiB
EXCEÇÃO NÃO CAPTURADA em generate_thumbnail_image: DecompressionBombError
```

## measure5.py — concorrência no dashboard anônimo (SEC-16, PERF-12)

```
baseline /health/ready=151 ms; dashboard sequencial=1095 ms
20 dashboards concorrentes SEM auth: wall=16.9s (sequencial teórico 21.9s), p50=16.8s, max=16.9s, status=[200]
/health/ready durante a carga (ms): [1126, 228, 259, 216, 260, 219] status: [200]
```

## measure6.py — fiber_count sem teto (EST-11)

```
fiber_count= 10000:   1.5s, RSS pico 144 MiB (+50 MiB)
fiber_count= 40000:   5.9s, RSS pico 270 MiB (+125 MiB)
```

## enum_routes.py — inventário (P0)

```
total handlers: 110 | total (método,path): 110 | non-API routes: 4   (/openapi.json, /docs, /docs/oauth2-redirect, /redoc)
handlers mutantes: 56 | sem validate_csrf: 9 | sem qualquer dependência de auth: 16 | com require_permission: 89
```

## Worker (EST-01)

```
$ python -c "import scripts.run_worker"      # importação apenas
ImportError: cannot import name 'process_claimed_job' from 'app.modules.jobs.service'
```

## Reprodução do COPY de diretório inexistente (EST-15)

`tools/repro-copy-missing-dir/Dockerfile` (equivalente ao estágio `runner` do frontend):

```
ERROR: failed to build: failed to solve: failed to compute cache key: ... "/app/public": not found
```

## Scanners

- `pip-audit -r requirements(uv export --frozen) --no-deps`: **No known vulnerabilities found** (55 dependências) — `pip-audit-backend.json`.
- `pnpm audit --json`: **7 advisories** (1 crítica maplibre-gl, 2 altas postcss, 4 moderadas) — `pnpm-audit-frontend.json`.
