# Resolução da auditoria — re-auditoria final (R28)

> **Confidencial.** Complementa `relatorio-auditoria-seguranca.pdf`, `issues.md` e `roteiro-correcao.md`.
> Branch: `fix/auditoria-seguranca` (27 commits locais, um por etapa R01–R27; **nada foi enviado/mesclado**).
> Esta etapa (R28) não alterou código: só este arquivo e o checklist da seção 6 do roteiro.
> `findings.json`, `issues.md`, `inventario-rotas.md`, o PDF e `evidencias/` continuam sendo o **retrato anterior às correções** (o texto estático do `gen_inventory.py` cita achados que já não existem).

## 1. Resumo

| | Antes | Agora |
|---|---|---|
| Achados (53) | 53 abertos (10 altos) | **50 corrigidos, 3 parciais** (PERF-09, EST-14, EST-17), 0 pendentes |
| Rotas sem autenticação (110 handlers) | 18 | **8** — todas intencionais: `health/live`×2, `health/ready`×2, `auth/csrf`, `auth/login`, `auth/logout`, `metrics` (token; o Caddy responde 404 externamente) |
| Rotas com `require_permission` | 92 com auth, 0 nos stubs | 102 com auth; todas as rotas de negócio autenticadas por padrão (`router.py:32`) |
| `pip-audit` (backend, 56 pacotes) | 0 | 0 |
| `pnpm audit` (frontend) | 7 (1 crítica, 2 altas, 4 moderadas) | **0** |
| Trivy (imagens, HIGH/CRITICAL) | — | 0 |
| Testes | — | backend **534 passam**; frontend 180 passam (`pnpm lint && pnpm typecheck && pnpm test`) |

Regressões encontradas: **nenhuma**. Achados novos/residuais: §4. Decisões humanas assumidas (precisam de confirmação): §5.

## 2. Re-execução das ferramentas e medições

Ambiente descartável: PostGIS 16-3.4 em `127.0.0.1:55432` (banco novo `audit2`, `alembic upgrade head` até `0015_retention_indexes`, gerador sintético `generate_synthetic_load.py --structures 10000`, ~23 s). As ferramentas em `tools/` não foram editadas; as que gravam em `/tmp/audit-env/` rodaram por cópia com o caminho trocado.

`enum_routes.py`: **110 handlers** (igual ao original). `gen_inventory.py` roda, mas o veredito por rota é texto fixo — a contagem "sem auth" acima vem da introspecção (`deps` de cada rota).

| Medição (ferramenta) | Antes (`evidencias/medicoes.md`) | Agora |
|---|---|---|
| `measure.py` dashboard sem auth | 200, 1018–1524 ms, **2514** SQL | **401**, 2–3 ms, 0 SQL |
| `measure.py` busca sem auth `?q=OLT` | 200, 4 SQL | **401** |
| `measure.py` busca `structures ILIKE` (10k linhas) | Seq Scan 4,6 ms | Bitmap Scan `idx_structures_code_trgm` 0,12 ms |
| `measure.py` listagem `OFFSET 9000` | Sort + Seq Scan 5,9 ms | Index Scan `idx_structures_created_desc_id` 4,1 ms |
| `measure2.py` lookup `terminals(entity)` | Seq Scan 12,5 ms | Index Scan `idx_terminals_entity` 0,036 ms |
| `measure2.py` viewer `GET /customers` | 200 com PII | **403** |
| `measure2.py` `GET /customers/not-a-uuid` | 500 | 403 para viewer (a permissão vem antes); 422 para quem tem permissão (`test_uuid_validation.py`) |
| `measure2.py` impacto (1 cliente) | 80–104 ms, 62 SQL | 28–67 ms, **15** SQL |
| `measure2.py` cardinalidade de métricas após 300 paths 404 | 8 → 308 chaves | 8 → **9** |
| `measure3.py` Origin `…3000.evil.example` | passa a checagem (401) | **403** `csrf_origin_mismatch` |
| `measure3.py` produção com defaults | aceita | **recusa a subir** (`SECRET_KEY`, `CSRF_SECRET`, `METRICS_SECRET_TOKEN`, `BACKUP_SIGNING_KEY`) |
| `measure4.py` PNG 9400² direto em `generate_thumbnail_image` | +342 MiB | **igual** (ver §4, N-04: a proteção está no upload, não na função) |
| `measure5.py` 20 dashboards concorrentes sem auth | 3,1 s de CPU | 401 imediato; `/health/ready` 13–34 ms, sempre 200 |
| `measure6.py` `fiber_count=10000` | cria o cabo (10 mil fibras) e o processo cresce | `CableCreate` recusa (`≤ 1728`, 422) — a ferramenta aborta na validação |

Medições próprias das etapas (mesmo dataset; variam ±40 % entre execuções nesta máquina): dashboard autenticado 2516 → **7–8** statements (≈830 → 15–19 ms); bomba de imagem via upload 9400² → 422 em < 1 ms (antes +342 MiB); `/health/ready` com pool saturado 5004 ms (503) → 17–32 ms (200); impacto de 300 clientes 3050–10650 ms / 8366 statements → 641–1103 ms / **14**; trace (`max_hops=60`) 131–178 ms / 360 statements → 19–37 ms / **9**; importação de 50 mil pontos 100 001 → 201 statements; pico de memória da exportação 40 MB → ~4 MB; busca `sites` 80 → 0,4 ms, `customers` 134 → 3,3 ms (100 mil linhas).

## 3. Situação por achado (53)

Legenda de status: **corrigido** · **parcial**. `arquivo:linha` = onde o código atual implementa a correção, conferido manualmente (não foi usado `verify_fidelity.py`). Commits: `git log --oneline master..HEAD`.

| ID | Status | Commit (etapa) | Teste que cobre | Verificação no código atual |
|---|---|---|---|---|
| SEC-01 | corrigido | 116f9e7 (R03) | `integration/test_auth_by_default.py`, `test_reports_dashboard_search.py` | `api/v1/router.py:32` `authenticated = [get_current_user, audit_mutation]`, aplicado aos routers de negócio (`:36…`); `reports.py:39` sem `Depends` próprio, herda do router |
| SEC-02 | corrigido | 94a0309 (R05) | `test_metrics_access.py`, `unit/test_config.py` | `api/v1/metrics.py:37` `hmac.compare_digest`; `config.py:134` default só em dev/test; `config.py:160/166` produção recusa default; `compose.yaml:48/81/125` `${METRICS_SECRET_TOKEN:?…}` |
| SEC-03 | corrigido | d6cd9c0 (R04) | `test_pii_access_control.py` | `api/v1/customers.py:32,77,143` `require_permission("customers:read")`; `core/privacy.py:23-31` |
| SEC-04 | corrigido | d6cd9c0 (R04) | `test_pii_access_control.py`, `test_attachments_audit.py` | `core/privacy.py:31` `require_customer_access` (anexos de cliente); `api/v1/reports.py:219-228` máscara de PII na auditoria sem `customers:read` |
| SEC-05 | corrigido | 94a0309 (R05) | `unit/test_config.py` | `config.py:160` `reject_insecure_production_config`; `compose.yaml:8,27,41` `${POSTGRES_PASSWORD:?…}` |
| SEC-06 | corrigido | f13bc94 (R09) | `test_auth_hardening.py` | `identity/service.py:67` `check_login_rate_limit` por par (IP, e-mail) + teto por IP |
| SEC-07 | corrigido | f13bc94 (R09) | `test_auth_hardening.py` | `identity/service.py:154` mesmo `invalid_credentials` (conta inativa, inexistente ou senha errada) |
| SEC-08 | corrigido | f13bc94 (R09) | `test_auth_hardening.py`, `unit/test_cli_bootstrap.py` | `identity/service.py:246` `revoke_user_sessions`; `cli/bootstrap_admin.py:84` |
| SEC-09 | corrigido | f13bc94 (R09) | `test_auth_hardening.py` | `core/dependencies.py:89` `validate_csrf` (Origin exato); `core/security.py:67` token CSRF assinado (HMAC) |
| SEC-10 | corrigido | 1daabb9 (R19) | `test_backup_security.py` | `core/backup_restore.py:14-16` (docstring do contrato), extração com `filter="data"`, `psycopg.sql.Identifier`, manifesto HMAC (`:23`), `backup_crypto.py:19` AES-256-GCM |
| SEC-11 | corrigido (TLS real por validar) | 5841d22 (R17) | `unit/test_caddyfile.py`, `frontend/tests/csp-middleware.test.ts` | `Caddyfile:23` `{$SITE_ADDRESS::80}` sem `auto_https off`, HSTS só em conexão segura, `@metrics` 404; `frontend/src/middleware.ts:4-7` CSP com nonce, sem `unsafe-inline/eval` em `script-src` |
| SEC-12 | corrigido | 35f3d65 (R26) | `unit/test_script_safety.py`, `frontend/tests/login-no-demo-credentials.test.ts` | `core/script_safety.py:50,67`; `scripts/seed_demo.py:202` `secrets.token_urlsafe(16)` e `:1130` guarda antes de conectar; idem `generate_synthetic_load.py`/`benchmark_endpoints.py`. Extra: a tela de login deixou de exibir a senha fixa |
| SEC-13 | corrigido | 8142cde (R11) | `test_exports_jobs_security.py` | `exports/service.py:87` `record_audit_event`; TTL `EXPORT_TTL_DAYS`, download 410 após vencer, permissão revalidada |
| SEC-14 | corrigido | 8142cde (R11) | `test_exports_jobs_security.py` | `jobs/errors.py:13` `JobValidationError`; erros de job sanitizados, leitura do job exige a permissão do tipo |
| SEC-15 | corrigido | 0d5fe04 (R18) | `pnpm audit` = 0; CI `ci.yml:137` | `frontend/package.json:22` `maplibre-gl ^6.10.0`, vitest 4.1.11, override de `postcss` |
| SEC-16 | corrigido | 116f9e7 + 11a9b28 + 07e6f23 (R03+R08+R15) | `test_auth_by_default.py`, `test_dashboard_performance.py`, `test_db_resilience.py` | `router.py:32`; dashboard 7 statements (`reports/service.py:27`); `db/session.py:13` timeouts e pool |
| SEC-17 | corrigido | 00e81c5 + f13bc94 (R10+R09) | `test_audit_coverage.py`, `test_auth_hardening.py` | `audit/hooks.py:214` listener `after_flush` + `before_commit`; migração `0012` torna `audit_events` append-only; eventos explícitos de login/logout/usuários |
| SEC-18 | corrigido | f13bc94 (R09) | `test_auth_hardening.py` | `main.py:68` `TrustedProxyMiddleware(trusted_proxies=…)`; classe em `core/middleware.py:94` |
| EST-01 | corrigido | 2a2995e (R02) | `test_worker_script.py` | `scripts/run_worker.py:29,57,74` `process_claimed_job`/`run_iteration`; healthcheck `check_worker_heartbeat.py:12` no compose |
| EST-02 | corrigido | 116f9e7 (R03) | `test_auth_by_default.py` | `test_auth_by_default.py:33-50` varre todas as operações OpenAPI e exige 401 sem sessão (exceto as 8 públicas); stubs com permissão |
| EST-03 | corrigido | 670564e (R13) | `test_optimistic_concurrency.py` | `core/concurrency.py:7,23,41`; `version_id_col` no `VersionedModelMixin` (UPDATE atômico) |
| EST-04 | corrigido | 670564e (R13) | `test_optimistic_concurrency.py` | `cables/service.py:573-593` split exige `If-Match` ou `expected_topology_revision`, com lock |
| EST-05 | corrigido | e5c7ea6 (R12) | `test_import_pipeline.py` | `jobs/service.py:361` cabo + `CableSegment` com a geometria e pontas resolvidas (`resolve_cable_endpoints`, `:30`) |
| EST-06 | corrigido | e5c7ea6 (R12) | `test_import_pipeline.py` | `imports/service.py:773-802` chave com escopo de usuário e `ON CONFLICT` |
| EST-07 | corrigido | e5c7ea6 (R12) | `test_import_pipeline.py` | `jobs/service.py:178` `LeaseKeeper`, `:238` `assert_lease_owner` |
| EST-08 | corrigido | e5c7ea6 (R12) | `test_import_pipeline.py` | `core/storage.py:9` raiz = `STORAGE_PATH`, caminhos relativos |
| EST-09 | corrigido | 81dc0b9 (R20) | `test_attachment_consistency.py` | `attachments/service.py:229,349` arquivo temporário `*.uploading` → promoção → commit, com compensação; reconciliador com carência |
| EST-10 | corrigido | 00e81c5 (R10) | `test_audit_coverage.py` | `audit/hooks.py:214-255`; o teste varre todas as mutações da API |
| EST-11 | corrigido | 92ad339 (R06) | `test_input_limits.py`, `unit/test_request_caps.py` | `schemas/cables.py:22` `fiber_count ≤ 1728`; `core/rate_limit.py:27,35`; limite de corpo no Caddy |
| EST-12 | corrigido | 3f10a9b (R25) | `test_uuid_validation.py` | `schemas/common.py:8-16` `UuidStr`; varredura de todas as rotas e do OpenAPI |
| EST-13 | corrigido | f2acac5 (R16) | `test_metrics_cardinality.py` | `core/metrics.py:18,40` `__unmatched__`; `core/metrics_store.py:3,90` agregação entre processos |
| EST-14 | **parcial** | e08f7f2 (R21) | `unit/test_compose_scaling.py` | `docs/adr/0007-escala-horizontal.md`; `compose.yaml` sem `container_name` em backend/worker/frontend, Caddy balanceando, `backup` agendado. **Falta** storage compartilhado de anexos (S3/MinIO/NFS) para multi-réplica de verdade — só ADR (decisão humana) |
| EST-15 | corrigido | bf4a2db (R01) | build de imagem no CI (`ci.yml`) | `frontend/public/.gitkeep` versionado; `frontend/Dockerfile:30` `COPY --from=builder /app/public` |
| EST-16 | corrigido (não executado no GitHub) | 0d5fe04 (R18) | os próprios workflows | `.github/workflows/ci.yml:10` `permissions:`, `:137` pip-audit, gitleaks/Trivy; `codeql.yml:31,36`; `dependabot.yml`. Executei os comandos equivalentes localmente; a execução no GitHub Actions não foi feita |
| EST-17 | **parcial** | 94a0309 (R05), f13bc94 (R09) | `unit/test_config.py`, `test_auth_hardening.py` | Passaram a ser usadas: `CSRF_SECRET` (`core/security.py:62`), `METRICS_ENABLED` (`config.py:128`), `MAX_TRACE_HOPS` (`topology/service.py:62,178`); `DEBUG` removido. **`SECRET_KEY` continua sem consumidor** (`config.py:54`; só é validada em produção) e o comentário em `config.py:52-53` ("serão usadas na R09") ficou desatualizado (N-09) |
| EST-18 | corrigido | 2a2995e (R02) | `test_worker_script.py` | logs JSON e correlação no worker, heartbeat (`check_worker_heartbeat.py:12`), métricas de job (`core/metrics.py:106` `record_job`) |
| EST-19 | corrigido | 1daabb9 (R19) | `test_backup_security.py` | `backup_restore.py` snapshot consistente, `backup_crypto.py:19-45`, chaves `BACKUP_SIGNING_KEY`/`BACKUP_ENCRYPTION_KEY` |
| EST-20 | corrigido | 8ac2c1c (R27) | `contract/test_permissions_contract.py`, `frontend/tests/permissions-parity.test.ts`, `route-permission-guard.test.tsx` | `scripts/export_permissions.py:52` gera `contracts/permissions.json` e `rbac.generated.ts`; `rbac.ts:1-12` só reexporta; `route-permission-guard.tsx:12`; `PermissionGate` nas ações de escrita. `telemetry:write` (só no front) removido |
| EST-21 | corrigido | 670564e (R13) | `test_optimistic_concurrency.py` | `core/concurrency.py:23,41` única implementação de `If-Match` |
| PERF-01 | corrigido | 11a9b28 (R08) | `test_dashboard_performance.py` | `reports/service.py:27` `_cto_occupancy_buckets` em SQL agregado (`:112`); 7–8 statements |
| PERF-02 | corrigido | 1f59f8d (R14) | `test_topology_performance.py` (oráculo `legacy_topology_service.py`) | `topology/service.py:64,78` usa `load_trace_graph`; impacto com nº de queries constante (14) |
| PERF-03 | corrigido | 11a9b28 (R08) | `test_dashboard_performance.py` (plano) | migração `0011_terminals_entity_index.py`; `EXPLAIN` acima: Index Scan 0,036 ms |
| PERF-04 | corrigido | 270f138 (R07) | `test_attachment_image_limits.py` | `api/v1/attachments.py:54` handler síncrono (threadpool); `attachments/service.py:119,247` `validate_image_dimensions` antes de decodificar; `config.py:99` `MAX_IMAGE_PIXELS` |
| PERF-05 | corrigido | 38eb9bd (R22) | `test_import_export_scale.py` | `jobs/service.py:41,278` lotes de 500 e `MAX_IMPORT_FEATURES`; preview fora do event loop |
| PERF-06 | corrigido | 0b6e5de (R23) | `test_search_indexes.py` | `core/search.py:11,18` `contains` com escape de curingas e mínimo de 3 caracteres; migração `0014` (GIN trigram) |
| PERF-07 | corrigido | 0b6e5de (R23) | `test_search_indexes.py` | migração `0014_search_and_list_indexes.py:55,60` `(created_at DESC, id)` |
| PERF-08 | corrigido | 38eb9bd (R22) | `test_import_export_scale.py` | `exports/service.py:111-113` `yield_per` com escrita em fluxo |
| PERF-09 | **parcial** | 07e6f23 (R15) | `test_db_resilience.py` | `gis/service.py:33-50` o `UPDATE network_topology_state` continua sendo a linha única serializadora; mitigado (bump é o último passo antes do commit, importação bumpa uma vez, `statement_timeout` limita a espera). Não foi introduzido advisory lock/sequence |
| PERF-10 | corrigido | 07e6f23 (R15) | `test_db_resilience.py` | `identity/service.py:193` `contains_eager` (1 SELECT); `:222` `last_activity_at` só a cada > 60 s |
| PERF-11 | corrigido (audit_events por decisão) | 9e217e9 (R24) | `test_retention.py` | `retention/service.py:35` `run_retention` (login_attempts 30 d, sessões inválidas 7 d, exportações/prévias vencidas); migração `0015`; `audit_events` nunca expira (append-only) |
| PERF-12 | corrigido | 07e6f23 (R15) | `test_db_resilience.py` | `db/session.py:13-27` `build_engine` (pool 5+5, `connect_timeout`, `statement_timeout`); `Dockerfile` `WEB_CONCURRENCY=2` |
| PERF-13 | corrigido | 07e6f23 (R15) | `test_db_resilience.py`, `test_health_real_db.py` | `db/health.py:19` engine dedicada sem pool com timeouts curtos, `:63-64` head do Alembic em cache |
| PERF-14 | corrigido | 1f59f8d (R14) | `test_topology_performance.py` | `topology/graph.py:141` CTE recursiva `LATERAL`, `:414` `run_trace` em memória; 9 statements independentemente de `max_hops` |

## 4. Achados novos, residuais e limitações

| # | Item | Severidade | Situação |
|---|---|---|---|
| N-01 | `DELETE /customers/{id}` responde **500** quando o cliente tem vínculos históricos (desativados): a FK impede a exclusão e o erro não é mapeado. Já existia antes das correções | baixa | **aberto** (não fazia parte dos 53) |
| N-02 | Diálogo de divisão de segmento no frontend envia o **número** da fibra como `cut_fiber_ids` em vez do UUID; com a validação de UUID (R25) a chamada vira 422 | média (funcional) | **aberto**; corrigir junto com um teste do diálogo |
| N-03 | Permissões definidas sem rota que as exija (`cables:*`, `connectivity:*`, `topology:*`, `map:read`): as rotas usam `network:*`. A UI segue o que o servidor exige | baixa | **aberto** — decisão de produto (afinar ou remover; altera `/auth/me`) |
| N-04 | `generate_thumbnail_image`/`inspect_file_content` não limitam pixels por conta própria; o teto está em `validate_image_dimensions` (`attachments/service.py:247`), chamado por `save_attachment`. Hoje o único caminho de entrada é o upload, então não há exploração, mas um novo chamador herdaria o risco | baixa | **aberto** (defesa em profundidade) |
| N-05 | Rate limit em memória por processo (`WEB_CONCURRENCY=2` ⇒ o limite efetivo é ×2 e zera a cada restart). A interface `RateLimiter` (`core/rate_limit.py:27`) permite trocar por Postgres/Redis | baixa | aceito (decisão §5) |
| N-06 | `METRICS_SECRET_TOKEN` mantém o valor de desenvolvimento como default fora de produção (`config.py:134`); em produção a subida é recusada e o Caddy não publica `/metrics` | informativa | aceito |
| N-07 | Verificações que exigem ambiente real e **não foram feitas**: smoke manual do mapa com `maplibre-gl` 6 no navegador; CSP/nonce e HSTS num navegador com domínio e TLS reais; workflows do GitHub Actions; `docker compose --scale` com storage compartilhado | — | **pendente** (checklist §6 do roteiro / runbook §21–28) |
| N-08 | `docs/security-audit/tools/*.py` têm caminhos absolutos (`/tmp/audit-env`, `/home/bruno/...`) e o `gen_inventory.py` carrega veredito estático; não regerar `inventario-rotas.md` sem revisá-lo | informativa | aberto |
| N-09 | `SECRET_KEY` continua declarada e validada, mas nenhum código a usa; comentário em `config.py:52-53` desatualizado. Remover a variável (e do compose/.env.example) ou usá-la (ex.: assinar algo) | baixa | **aberto** (EST-17 parcial) |

## 5. Decisões humanas assumidas (confirmar)

O roteiro (seção 7) pedia decisões antes de começar; como a execução foi sem interrupções, foi usado o padrão sugerido. Cada uma está documentada em `docs/runbooks/deployment-and-maintenance.md` e é reversível.

| Etapa | Decisão assumida |
|---|---|
| R03 | Não existe painel/busca público: tudo exige login |
| R06 | Rate limit em memória por processo, atrás de interface trocável |
| R10 | Auditoria central por listeners da Session (`after_flush`/`before_commit`) + dependência `audit_mutation`; lote de importação = 1 evento |
| R11 | Exportações expiram em 7 dias (`EXPORT_TTL_DAYS`) |
| R12 | Cabos importados: origem/destino por códigos → proximidade → erro |
| R15 | `WEB_CONCURRENCY=2`, pool 5+5 por processo, `statement_timeout` 30 s (worker 10 min) |
| R17 | TLS no Caddy via `SITE_ADDRESS` (terminação em balanceador externo documentada como alternativa) |
| R18 | Upgrade major do `maplibre-gl` (6.10) aceito — **requer smoke manual do mapa** |
| R19 | Criptografia de backup por biblioteca Python `cryptography` (AES-256-GCM) + manifesto assinado (HMAC) |
| R21 | Somente ADR + compose escalável; storage de anexos multi-réplica (S3/MinIO/NFS) segue em aberto |
| R24 | `login_attempts` 30 dias, sessões inválidas 7 dias; `audit_events` sem retenção |

## 6. Verificação final

- Backend: `uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest` (Postgres/PostGIS descartável em `127.0.0.1:55433`) — **534 passed** (9 min 55 s), `ruff check`, `ruff format --check` (203 arquivos) e `mypy app` (113 arquivos) limpos.
- Frontend: `pnpm lint && pnpm typecheck && pnpm test` — 180 testes passam; `pnpm build` conclui.
- Contratos regenerados: `contracts/openapi.json`, `contracts/api-types.d.ts` e `contracts/permissions.json`; testes de contrato os comparam com o código.
- Migrações `0011`–`0015` com `downgrade` funcional.
- `git status --porcelain` ao final desta etapa: somente `docs/security-audit/` (este arquivo e `roteiro-correcao.md`).
