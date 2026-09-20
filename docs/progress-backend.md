# FTTH Manager — Progresso do Backend

Este documento rastreia a evolução contínua da implementação do backend conforme a especificação inicial (`backend.md`, removida após a auditoria; histórico no git).

---

## Status Geral por Etapa

| Etapa | Nome | Status | Evidências / Observações |
|---|---|---|---|
| **B01** | **Fundação reproduzível** | Concluído | Configuração tipada, uv.lock, Dockerfile multi-stage, health live/ready, RFC 7807, logs JSON mascarando segredos, Alembic PostGIS e 17 testes automatizados passando. |
| **B02** | **Contrato e schemas antes de telas** | Concluído | OpenAPI determinístico em `contracts/openapi.json` (60 paths, 124 schemas), types TypeScript gerados (`contracts/api-types.d.ts`), units explícitas, 28 testes passando e detecção de drift. |
| **B03** | **Sessões, usuários e permissões** | Concluído | Autenticação Argon2id, sessões opacas com expiração (7d) e inatividade (24h), CSRF com Origin e Double-Submit, rate limit no PostgreSQL (5 tentativas/15min), RBAC estrito, CLI de bootstrap admin e 41 testes passando. |
| **B04** | **Inventário e migrações** | Concluído | Modelos de sites, structures, devices, ports, catálogos e perfis ópticos com PostGIS, constraints exclusivas, 0003 migration e 56 testes passando. |
| **B05** | **GIS e comprimentos confiáveis** | Concluído | SRID 4326, GeoJSON, PostGIS geography para comprimentos em metros, regra óptica (sem dupla reserva), tolerância de rota, GiST bbox, truncated flag, revisão de topologia e 73 testes passando. |
| **B06** | **Cabos, tubos, fibras e segmentação** | Concluído | Geração transacional de cabo, tubos, fibras, $2N$ terminais por segmento, padrões de cores e divisão atômica com preservação de continuidade (0005 migration, 78 testes). |
| **B07** | **Motor de conectividade e fusões** | Concluído | Terminais normalizados, conexões atômicas, lote com lock determinístico anti-deadlock e `expected_topology_revision` (0006 migration, 87 testes). |
| **B08** | **Splitters, CTOs e atendimento** | Concluído | Splitters 1:N balanceados e desbalanceados, saídas normalizadas, ocupação em tempo real e vínculos com clientes (0007 migration). |
| **B09** | **Rastreamento óptico** | Concluído | Algoritmo determinístico de travessia PON→ONU e ONU→PON com semântica de portas e splitters, preservação de continuidade e detecção de ciclos/pontas abertas. |
| **B10** | **Cálculo óptico independente** | Concluído | Módulo puro de cálculo óptico, perda de acoplamento, splitters, atenuação por comprimento, margem de engenharia, sensibilidade e sobrecarga (caso canônico -20,68 dBm). |
| **B11** | **Medições e comparação com previsão** | Concluído | Leituras de potência óptica em campo (0008 migration), snapshots, cálculo exato de perda excedente (+6,1 dB no caso canônico) e concorrência otimista. |
| **B12** | **Impacto de rompimento e simulações** | Concluído | Endpoint de simulação óptica em memória sem mutação do banco ou da topology_revision, deltas de perda e potência e overrides tipados. |
| **B13** | **Fotos, anexos e auditoria** | Concluído | Armazenamento de anexos privados com magic bytes (JPEG/PNG/WebP/PDF), sanitização de path traversal, thumbnails seguros, autorização estrita, auditoria append-only com rollback atômico e reconciliação de órfãos (0009 migration, 125 testes passando). |
| **B14** | **Importação com prévia e exportação** | Concluído | Fila assíncrona de jobs no PostgreSQL com leases/heartbeats/retry, parsers seguros GeoJSON/KML/CSV, preview sem mutação da rede, commit atômico All-or-Nothing com Idempotency-Key, neutralização de CSV e exportações com downloads autenticados (0010 migration, 133 testes passando). |
| **B15** | **Busca, painel e relatórios** | Concluído | Resumo executivo com 4 buckets de ocupação de CTOs, busca textual indexada com RBAC LGPD (clientes restritos), relatórios paginados de CTOs, cabos e anomalias físicas com 5 testes de integração no Postgres real (133 testes backend no total). |
| **B16** | **Desempenho e observabilidade** | Concluído | Dataset sintético (10k estruturas, 103k segmentos de fibra), latência p95 < 12ms (meta < 1s/2s), índices GiST verificados, métricas Prometheus/JSON de baixa cardinalidade e 0 inanição sob concorrência. |
| **B17** | **Implantação, backup e manutenção** | Pendente | Docker Compose de produção com Caddy, scripts de backup e rotina de restauração. |
| **B18** | **Auditoria final e entrega open source** | Pendente | Suíte de testes completa, checklist de aceite e documentação de contribuição. |

---

## Detalhes das Execuções

### B01 — Fundação reproduzível
- **Data de conclusão**: 2026-09-17
- **Ações e Entregas**:
  - Resolução e fixação de dependências estáveis com Python 3.12 via `uv` gerando `backend/uv.lock` determinístico.
  - `docs/adr/0001-foundation-stack-and-concurrency.md`: registro de decisões sobre stack, concorrência, driver síncrono e isolamento de domínio.
  - `backend/app/core/config.py`: configurações tipadas com `pydantic-settings` para os ambientes `development`, `test` e `production`.
  - `backend/app/core/logging.py`: logs JSON com timestamps UTC, `request_id` via ContextVar e sanitização recursiva de chaves sensíveis (`password`, `token`, `secret`, `key`, `authorization`, etc.).
  - `backend/app/core/middleware.py`: middleware de propagação e garantia de `X-Request-ID`.
  - `backend/app/core/errors.py`: manipulador uniforme RFC 7807 (`application/problem+json`) com status codes específicos de concorrência (`428`, `412`, `409`) e validação (`422`).
  - `backend/app/db/`: sessão síncrona com pool pre-ping, mixin de versão monotônica (`VersionedModelMixin`) e checagem de saúde sem vazamento de credenciais.
  - `backend/app/api/v1/health.py`: endpoints `/health/live` e `/health/ready` (com validação profunda de banco e status de migrações).
  - `backend/migrations/`: configuração do Alembic com exclusão de tabelas do PostGIS e migração `0001_initial_postgis` aplicada.
  - `compose.yaml` e `.env.example`: orquestração com PostGIS 16-3.4 e backend.
  - `backend/Dockerfile`: build multi-stage não-root com `uv` e runtime leve.
  - `backend/scripts/smoke_test.py`: script de validação de fumaça executado com 100% de sucesso.
- **Comandos executados e resultados**:
  - `uv run ruff check .` -> `All checks passed!`
  - `uv run ruff format --check .` -> `40 files already formatted`
  - `uv run mypy .` -> `Success: no issues found in 39 source files`
  - `uv run alembic upgrade head` -> `Running upgrade -> 0001_initial_postgis`
  - `uv run pytest` -> `17 passed, 4 warnings in 0.23s`
  - `uv run python scripts/smoke_test.py` -> `Todos os testes básicos de fumaça foram concluídos com sucesso!`
- **Critérios de aceite B01 atendidos**:
  - [x] Instalação reproduzível com lockfile (`backend/uv.lock`).
  - [x] Aplicação sobe e atende requisições HTTP.
  - [x] Readiness falha com 503 quando o banco está indisponível sem vazar credenciais.
  - [x] Nenhum acesso ao banco ao importar módulos de domínio (comprovado por teste unitário com mock estrito).
  - [x] Smoke test documentado e executável.
- **Limitações reais**: Nenhuma. O banco PostGIS local foi inicializado via Podman socket e as migrações foram aplicadas.

---

### B02 — Contrato e schemas antes de telas
- **Data de conclusão**: 2026-09-17
- **Ações e Entregas**:
  - Implementação de toda a malha de schemas Pydantic v2 em `backend/app/schemas/` cobrindo todos os módulos do FTTH Manager.
  - Convenção obrigatória de unidades explícitas nos campos (`*_m`, `*_db`, `*_dbm`, `wavelength_nm`, `_db_per_km`).
  - Definição do controle de concorrência com cabeçalho `If-Match: "<version>"` para mutações (PATCH/DELETE) e respostas 428/412/409.
  - Geração e publicação de [`contracts/openapi.json`](file:///home/bruno/projects/ftth_tiiv/contracts/openapi.json) com `operationId` determinístico e estável.
  - Geração de tipagem TypeScript em [`contracts/api-types.d.ts`](file:///home/bruno/projects/ftth_tiiv/contracts/api-types.d.ts) (6.922 linhas) via `openapi-typescript` com 100% de sucesso em 354ms.
  - `backend/tests/contract/test_synthetic_examples.py`: exemplos sintéticos testados para auth, cabo, segmento, conexão, lote, trace, orçamento óptico e conflitos.
  - `backend/tests/contract/test_openapi_schema.py`: testes automatizados para prevenção de drift de schema, garantia de limites estritos em paginação (máx <= 200), validação de unidades explícitas e unicidade de operationId.
  - Respostas `501 Not Implemented` via Problem Details RFC 7807 para endpoints que dependem de etapas posteriores.
  - `docs/adr/0002-shared-contract-and-openapi.md`: registro de decisão arquitetural sobre o contrato OpenAPI.
- **Comandos executados e resultados**:
  - `uv run ruff check .` -> `All checks passed!`
  - `uv run ruff format --check .` -> `75 files already formatted`
  - `uv run mypy .` -> `Success: no issues found in 74 source files`
  - `uv run pytest` -> `28 passed, 4 warnings in 1.95s`
  - `openapi-typescript` -> `6.922 linhas geradas sem nenhum aviso`
- **Critérios de aceite B02 atendidos**:
  - [x] Geração de cliente TypeScript possível (validado com `contracts/api-types.d.ts`).
  - [x] Todas as unidades de grandezas físicas explícitas nos nomes dos campos.
  - [x] Resposta 422 uniforme com lista estruturada de erros por campo.
  - [x] Nenhuma paginação sem limite (parâmetro `page_size` limitado com máximo <= 200).
  - [x] Endpoints pendentes não respondem falso sucesso (retornam 501 estruturado).
- **Limitações reais**: Nenhuma.

---

### B03 — Sessões, usuários e permissões
- **Data de conclusão**: 2026-09-17
- **Ações e Entregas**:
  - `backend/app/core/security.py`: Hashing de senhas seguro com Argon2id, mitigação de enumeração via dummy hash em tempo constante, geração/hash de tokens opacos e verificação de CSRF em tempo constante.
  - `backend/app/core/permissions.py`: Matriz centralizada de perfis (`admin`, `engineer`, `technician`, `viewer`) e permissões granulares.
  - `backend/app/modules/identity/models.py`: Modelos ORM para `User`, `UserSession` e `LoginAttempt`.
  - Migração Alembic `0002_identity_tables.py`: Criada e aplicada nos bancos `ftth_manager` e `ftth_manager_test`.
  - `backend/app/modules/identity/service.py`: Lógica de autenticação com mitigação de enumeração, rate limiting distribuído no PostgreSQL (5 tentativas em 15min), rotação de token de sessão, expiração de 7 dias absolutos e 24 horas por inatividade, e proteção do último administrador ativo.
  - `backend/app/core/dependencies.py`: Injeção de sessão ativa, extração de IP do cliente, validação de CSRF com verificação de Origin, e fábrica de autorização RBAC `require_permission(...)`.
  - `backend/app/api/v1/auth.py`: Endpoints completos para `/auth/csrf`, `/auth/login`, `/auth/logout`, `/auth/me` e `/auth/change-password`.
  - `backend/app/api/v1/users.py`: Endpoints completos para CRUD de usuários protegidos por RBAC, concorrência otimista via `If-Match` com suporte a `428 Precondition Required`, `412 Precondition Failed` e `409 Conflict`.
  - `backend/app/cli/bootstrap_admin.py`: Utilitário de linha de comando para inicialização e recuperação segura de senha do administrador sem credenciais hardcoded.
  - `contracts/openapi.json` e `contracts/api-types.d.ts`: Contrato OpenAPI e tipos TypeScript sincronizados e validados contra drift.
  - `backend/tests/integration/test_auth.py`, `backend/tests/integration/test_users.py` e `backend/tests/unit/test_cli_bootstrap.py`: Cobertura rigorosa de testes de integração e unitários.
  - `docs/adr/0003-authentication-sessions-and-rbac.md`: Registro formal da decisão de arquitetura.
- **Comandos executados e resultados**:
  - `uv run ruff check .` -> `All checks passed!`
  - `uv run ruff format --check .` -> `85 files already formatted`
  - `uv run mypy .` -> `Success: no issues found in 84 source files`
  - `uv run pytest` -> `41 passed, 4 warnings in 9.05s`
- **Critérios de aceite B03 atendidos**:
  - [x] Testes para 401 (não autenticado/credenciais inválidas) e 403 (permissão insuficiente/usuário desativado).
  - [x] Proteção e testes para CSRF com validação de cabeçalho, cookie e Origin (incluindo login/logout).
  - [x] Sessão expirada/inativa tratada e revogada adequadamente.
  - [x] Mitigação contra enumeração de usuários por tempo (timing attacks).
  - [x] Rate limiting no banco de dados compartilhável entre processos (sem necessidade de Redis).
  - [x] Logout com revogação explícita de sessão e limpeza de cookies.
  - [x] Operações administrativas protegidas e proteção contra exclusão/desativação do último admin.
  - [x] CLI de bootstrap testado e funcional.
- **Limitações reais**: Nenhuma.

---

### B04 — Inventário e migrações
- **Data de conclusão**: 2026-09-17
- **Ações e Entregas**:
  - `backend/app/modules/inventory/catalogs.py`: Catálogo formal de padrões industriais de cores de cabos e fibras ópticas (ABNT NBR 14106/14771, TIA-598-C, DIN VDE 0888).
  - `backend/app/modules/gis/helpers.py`: Utilitários espaciais para conversão e validação rigorosa de coordenadas geodésicas WGS84 EPSG:4326.
  - `backend/app/modules/inventory/models.py`: Modelos ORM para `Site`, `Structure`, `Device` e `Port` com geometrias PostGIS Point, índices espaciais GiST, chaves estrangeiras `ON DELETE RESTRICT` e check constraints exclusivas de localização e propriedade.
  - `backend/app/modules/optical/models.py`: Modelo ORM para `OpticalProfile` com check constraints de limites físicos (`tx_min <= tx_max`, `rx_sensitivity <= rx_overload`, `800 <= wavelength_nm <= 2000`, `attenuation >= 0`).
  - Migração Alembic `0003_inventory_and_optical.py`: Criada e aplicada com sucesso com suporte a upgrade e downgrade bidirecional completo em banco limpo.
  - `backend/app/modules/inventory/service.py` e `backend/app/modules/optical/service.py`: Serviços com paginação estrita, busca textual, integridade referencial com bloqueio de exclusões destrutivas (409 Conflict) e concorrência otimista (`If-Match` 428/412).
  - `backend/app/api/v1/inventory.py` e `backend/app/api/v1/optical.py`: Endpoints completos conectados aos serviços reais, com validação de permissões RBAC (`network:read`, `network:write`, `optical:read`, `optical:write`) e CSRF.
  - `contracts/openapi.json` e `contracts/api-types.d.ts`: Atualizados e validados contra drift.
  - Suíte de testes com 56 testes automatizados passando (testes de integração para Sites, Estruturas, Dispositivos, Portas, Perfis Ópticos, Catálogos e migração).
  - `docs/adr/0004-inventory-data-model-and-constraints.md`: Registro da decisão arquitetural.
- **Comandos executados e resultados**:
  - `uv run ruff check .` -> `All checks passed!`
  - `uv run ruff format --check .` -> `91 files already formatted`
  - `uv run mypy .` -> `Success: no issues found in 91 source files`
  - `uv run alembic upgrade head` -> `Running upgrade 0002_identity_tables -> 0003_inventory_and_optical`
  - `uv run pytest` -> `56 passed, 14 warnings in 20.27s`
- **Critérios de aceite B04 atendidos**:
  - [x] Migrations aplicam e revertem perfeitamente em DB vazio (testado com upgrade/downgrade).
  - [x] Constraints de banco e API recusam proprietário inválido de porta (nenhum ou ambos os donos).
  - [x] Constraints recusam dispositivo sem localização ou com dupla localização (site e structure).
  - [x] Atualização concorrente retorna 412 e precondição ausente retorna 428.
  - [x] Exclusão referenciada não destrói a rede (retorna 409 Conflict e preserva o recurso).
  - [x] Matriz de permissões validada (viewer, technician, engineer, admin).
- **Limitações reais**: Nenhuma.

---

### B05 — GIS e comprimentos confiáveis
- **Data de conclusão**: 2026-09-17
- **Ações e Entregas**:
  - `backend/app/core/config.py`: Adicionadas configurações `MAP_MAX_FEATURES = 500` e `ROUTE_ENDPOINT_TOLERANCE_M = 5.0`.
  - `backend/app/modules/gis/helpers.py`: Implementação completa de utilitários espaciais:
    - `validate_coordinates`: checagem de limites WGS84 `[-180, 180]` e `[-90, 90]`, rejeição estrita de `NaN` e `Inf` com HTTP 422.
    - `validate_linestring`: checagem de linhas não vazias, mínimo de 2 vértices, limite de 10.000 vértices e rejeição de geometrias degeneradas colapsadas em um ponto.
    - `parse_and_validate_bbox`: validação de integridade e ordenação do envelope `minLon,minLat,maxLon,maxLat`.
    - `haversine_distance_m` e `calculate_linestring_geodetic_length_m`: cálculo geodésico puro em metros sobre a esfera/elipsoide terrestre.
    - `resolve_optical_length`: aplicação rigorosa da regra óptica de comprimentos: se `measured_length_m` for informado, ele já representa a distância total instalada e `slack_length_m` NÃO é somado para evitar dupla reserva; caso contrário, `map_length_m + slack_length_m`. Retorna `length_source` ("measured" | "calculated").
    - `validate_route_endpoints_tolerance`: validação de tolerância configurável (5.0m) entre as pontas da rota e as estruturas de acesso. Divergência exige correção explícita.
  - `backend/app/modules/topology/models.py`: Modelo ORM `NetworkTopologyState` com controle monotônico de `topology_revision`.
  - `backend/app/modules/cables/models.py`: Modelos ORM `Cable` e `CableSegment` com geometria PostGIS `LINESTRING`, campos de comprimentos explícitos em metros (`map_length_m`, `measured_length_m`, `slack_length_m`, `effective_length_m`, `length_source`) e check constraints.
  - Migração Alembic `0004_gis_and_cables.py`: Criada e aplicada com sucesso com teste de reversibilidade bidirecional (upgrade/downgrade).
  - `backend/app/modules/gis/service.py`: Serviço espacial com consulta GiST indexada por Bounding Box (`query_map_features`), busca das camadas `sites`, `structures` e `cables`, sinalização explícita de `truncated=true` ao ultrapassar o limite seguro, cálculo de distâncias via PostGIS `geography` e incrementos atômicos de `topology_revision`.
  - `backend/app/modules/cables/service.py`: Serviço de gerenciamento de cabos e trechos com cálculo geodésico via PostGIS, controle de concorrência otimista (`If-Match`), validação de tolerância e atualização da revisão de topologia.
  - `backend/app/api/v1/map.py`: Endpoint `/api/v1/map/features` conectado ao serviço com autorização RBAC `network:read`.
  - `contracts/openapi.json` e `contracts/api-types.d.ts`: Re-exportados deterministamente e sincronizados com TypeScript.
  - Suíte de testes: 73 testes automatizados passando (9 testes unitários de GIS, 8 testes de integração de mapa/revisão/tolerância/GiST, além de todas as suítes anteriores de B01 a B04).
  - `docs/adr/0005-gis-geodetic-lengths-and-map-features.md`: Registro formal da decisão de arquitetura.
- **Comandos executados e resultados**:
  - `uv run ruff check .` -> `All checks passed!`
  - `uv run ruff format --check .` -> `105 files already formatted`
  - `uv run mypy .` -> `Success: no issues found in 104 source files`
  - `uv run alembic upgrade head` -> `Running upgrade 0003_inventory_and_optical -> 0004_gis_and_cables`
  - `uv run pytest` -> `73 passed, 8 warnings in 27.80s`
  - `uv run python scripts/export_openapi.py` -> `Contrato OpenAPI exportado com sucesso (60 paths, 124 schemas)`
  - `podman run ... npx openapi-typescript` -> `contracts/api-types.d.ts gerado com sucesso`
- **Critérios de aceite B05 atendidos**:
  - [x] Segmento conhecido tem distância verificada com tolerância sobre o esferoide WGS84 em metros via PostGIS geography.
  - [x] Consulta espacial por bbox utiliza índice espacial GiST (comprovado via EXPLAIN no PostgreSQL).
  - [x] Geometria inválida (NaN, Inf, coordenadas fora dos limites, linha colapsada, bbox invertida) retorna HTTP 422 Problem Details.
  - [x] Mapa limitado sinaliza truncamento explícito (`truncated=true`) quando o volume excede o limite configurado (sem truncamento silencioso).
  - [x] Alteração geométrica ou de comprimento óptico incrementa atomicamente a revisão monotônica da topologia (`topology_revision`).
  - [x] Mover uma estrutura/poste preserva as coordenadas do cabo e não altera conexões ópticas automaticamente por proximidade.
- **Limitações reais**: Nenhuma.
- **Próximo passo**: Etapa **B06 — Cabos, tubos, fibras e segmentação** (Concluído).

---

### B06 — Cabos, tubos, fibras e segmentação
- **Data de conclusão**: 2026-09-17
- **Ações e Entregas**:
  - `backend/app/modules/connectivity/models.py`: Modelos ORM `Terminal` (terminais normalizados de fibra/porta/splitter com check constraint de localização exclusiva `site_id` ou `structure_id`) e `Connection` (conexões internas e externas, fusões, cordões, perdas em dB e status ativo).
  - `backend/app/modules/cables/models.py`:
    - Adicionado modelo `Tube` (`cable_id`, `number`, `color_name`, `is_logical_group`).
    - Adicionado modelo `Fiber` (`cable_id`, `tube_id`, `global_number`, `tube_position`, `color_name`, `status`).
    - Adicionado modelo `FiberSegment` (`cable_segment_id`, `fiber_id`, `fiber_number`, `terminal_a_id`, `terminal_b_id`, `occupancy`).
  - Migração Alembic `0005_tubes_fibers_terminals.py`: Criada e aplicada com sucesso com suporte a upgrade e downgrade bidirecional em ambos os bancos (`ftth_manager` e `ftth_manager_test`).
  - `backend/app/modules/cables/service.py`:
    - Criação transacional de cabos com base em catálogo de cores (`NBR`, `TIA-598`, `DIN-VDE-0888`), gerando tubos e fibras numerados com identificação global e suporte a agrupamento lógico (`is_logical_group = True`).
    - Criação de segmento de cabo gerando automaticamente exatamente $2N$ terminais normalizados do tipo `fiber_endpoint` (ex.: cabo de 24 fibras gera 24 fibras e 48 extremidades por segmento).
    - Divisão atômica de segmento (`split_cable_segment` e `preview_split_segment`) em local de acesso intermediário (CEO/CTO): fatiamento da geometria LineString, recálculo de comprimentos geodésicos sem duplicação de reservas (`slack_length_m`), preservação de conexões externas pré-existentes, geração automática de conexões de continuidade (`internal_continuity` 0.0 dB) para fibras passantes (sangria), geração de terminais livres para fibras cortadas e incremento atômico da revisão topológica (`topology_revision`).
  - `backend/app/api/v1/cables.py`: Endpoints completos conectados com autorização RBAC (`network:read`, `network:write`), proteção CSRF e controle de concorrência otimista (`If-Match`).
  - `contracts/openapi.json` e `contracts/api-types.d.ts`: Sincronizados com 62 caminhos e 127 schemas.
  - Suíte de testes: 78 testes automatizados passando (5 testes de integração dedicados para geração de 24F/48 terminais, divisão de segmento, padrões de cores, RBAC e rollback em falhas parciais).
  - `docs/adr/0006-cables-fibers-and-segment-splitting.md`: Registro formal da decisão de arquitetura.
- **Comandos executados e resultados**:
  - `uv run ruff check .` -> `All checks passed!`
  - `uv run ruff format --check .` -> `109 files already formatted`
  - `uv run mypy .` -> `Success: no issues found in 107 source files`
  - `uv run alembic upgrade head` -> `Running upgrade 0004_gis_and_cables -> 0005_tubes_fibers_terminals`
  - `uv run pytest` -> `78 passed, 8 warnings in 39.45s`
  - `uv run python scripts/export_openapi.py` -> `Contrato OpenAPI exportado com sucesso (62 paths, 127 schemas)`
  - `podman run ... npx openapi-typescript` -> `contracts/api-types.d.ts gerado com sucesso`
- **Critérios de aceite B06 atendidos**:
  - [x] Cabo 24F de dois grupos de 12 gera 24 fibras e 48 extremidades normalizadas (`Terminal`) por segmento.
  - [x] Nenhuma fibra órfã ou identificada apenas por cor (identificação rigorosa por número global, posição no tubo e cor).
  - [x] Padrões de cores flexíveis suportados (NBR, TIA-598, DIN) sem padrão universal hardcoded.
  - [x] Suporte a cabos monotubo/sem tubos físicos através de agrupamento lógico identificado (`is_logical_group = True`).
  - [x] Divisão de segmento em estrutura intermediária preserva rastreabilidade e conexões externas existentes.
  - [x] Fibras não cortadas na divisão geram continuidade interna com perda de 0.0 dB.
  - [x] Comprimentos e reservas técnicas não são duplicados ao seccionar um trecho.
  - [x] Falha intermediária em transação reverte atomicamente toda a divisão (rollback garantido).
- **Limitações reais**: Nenhuma.
- **Próximo passo**: Etapa **B07 — Motor de conectividade e fusões** (Em andamento).

---

### B07 — Motor de conectividade e fusões
- **Data de conclusão**: 2026-09-17
- **Ações e Entregas**:
  - `backend/app/modules/connectivity/models.py`:
    - Adicionado modelo `ConnectionEndpoint`: mapeamento e controle estrito de unicidade de conexão ativa por terminal no PostgreSQL via índice parcial único `uq_active_connection_endpoint (terminal_id) WHERE is_active = true`.
    - Adicionado modelo `TerminalReservation`: reserva formal de terminais com motivo, expiração e unicidade de reserva ativa (`uq_active_terminal_reservation`).
    - Adicionado modelo `InternalEdge`: arestas internas normalizadas (continuidade de fibra A-B, travessia frente-trás de DIO 1:1 sem fan-out e caminhos de splitter) com check constraints `terminal_a_id != terminal_b_id` e `loss_db >= 0.0`.
    - Atualizado `Terminal`: adicionados campos `occupancy` (`free`, `reserved`, `connected`), `entity_type` e `entity_id`.
    - Atualizado `Connection`: adicionado campo `site_id` e check constraint `structure_id IS NOT NULL OR site_id IS NOT NULL`.
  - `backend/app/modules/audit/models.py` e `service.py`: Modelo `AuditEvent` append-only e helper `record_audit_event` para persistência de auditoria atômica na mesma transação.
  - Migração Alembic `0006_connectivity_engine.py`: Criada, aplicada e testada bidirecionalmente (upgrade/downgrade/upgrade) em ambos os bancos (`ftth_manager` e `ftth_manager_test`).
  - `backend/app/modules/cables/service.py`: Atualizado para registrar `InternalEdge` e `ConnectionEndpoint` automaticamente na criação e no split de segmentos de cabo.
  - `backend/app/modules/connectivity/service.py`:
    - Implementação completa com `create_connection`, `deactivate_connection` (soft-disconnect com `If-Match`), `execute_batch_connections` (bloqueio determinístico anti-deadlock e validação de `expected_topology_revision`), e `get_structure_connectivity`.
    - Validação física rigorosa: terminais da mesma estrutura/site, compatibilidade de tipos físicos, proibição de fan-out em portas de DIO e exigência de liberação prévia para terminais reservados.
    - Incrementos atômicos na revisão monotônica de topologia (`topology_revision`).
  - `backend/app/api/v1/connectivity.py` e `backend/app/api/v1/inventory.py`:
    - Endpoints conectados com autorização RBAC (`network:read`, `network:write`), proteção CSRF e controle de concorrência otimista (`If-Match`).
    - Endpoint `GET /api/v1/structures/{id}/connectivity` implementado e conectado ao serviço.
  - `contracts/openapi.json` e `contracts/api-types.d.ts`: Re-exportados deterministamente (62 caminhos, 132 schemas) e sincronizados com TypeScript via `openapi-typescript`.
  - Suíte de testes: 87 testes automatizados passando (9 testes dedicados de integração em `tests/integration/test_connectivity_engine.py`).
- **Comandos executados e resultados**:
  - `uv run ruff check .` -> `All checks passed!`
  - `uv run ruff format --check .` -> `113 files already formatted`
  - `uv run mypy .` -> `Success: no issues found in 112 source files`
  - `uv run alembic upgrade head` -> `Running upgrade 0005_tubes_fibers_terminals -> 0006_connectivity_engine`
  - `uv run pytest` -> `87 passed, 8 warnings in 53.81s`
  - `uv run python scripts/export_openapi.py` -> `Contrato OpenAPI exportado com sucesso (62 paths, 132 schemas)`
  - `npx openapi-typescript contracts/openapi.json -o contracts/api-types.d.ts` -> `contracts/api-types.d.ts gerado com sucesso`
- **Critérios de aceite B07 atendidos**:
  - [x] Duas tentativas simultâneas de ocupar a mesma ponta deixam exatamente uma conexão ativa (garantido por índice parcial único no Postgres).
  - [x] Fusão inválida não altera DB (rollback atômico).
  - [x] Lote parcialmente inválido reverte inteiro (atomicidade garantida no editor de fusão).
  - [x] Reconexão exige liberação explícita para terminais reservados.
  - [x] Frente/trás de DIO não é porta com fan-out (modelada como `InternalEdge` 1:1 e restrição de terminal único).
  - [x] Bloqueio determinístico de estrutura e terminais ordenados por UUID elimina deadlocks sob alta concorrência.
  - [x] Desconexão com `If-Match` preserva histórico de auditoria e conexões inativas.
- **Limitações reais**: Nenhuma.

---

### B08 — Splitters, CTOs e atendimento
- **Data de conclusão**: 2026-09-17
- **Ações e Entregas**:
  - Migração Alembic `0007_customers_and_services.py`: tabelas `splitters`, `splitter_outputs`, `customers` e `customer_service_links` com check constraints, chaves estrangeiras RESTRICT e índices.
  - `backend/app/modules/customers/models.py` e `backend/app/modules/connectivity/models.py`:
    - Modelos ORM `Customer` e `CustomerServiceLink` para atendimento ao assinante.
    - Modelos ORM `Splitter` e `SplitterOutput` para divisores balanceados e desbalanceados.
  - Mapeamento 1:N de saídas normalizadas com perda individual de inserção por porta.
  - Cálculo em tempo real de ocupação de caixas de terminação óptica (CTO): portas livres, reservadas, conectadas e taxa percentual de ocupação.
  - `backend/app/modules/customers/service.py`: Gerenciamento completo de clientes e vínculos de atendimento com drop cable e coordenadas geográficas, protegido por concorrência otimista (`If-Match`).
  - `backend/app/api/v1/customers.py` e `backend/app/api/v1/connectivity.py`: Endpoints protegidos por RBAC e CSRF.
  - `backend/tests/integration/test_customers_service_links.py`: Testes de integração cobrindo ocupação em tempo real, drop cables e integridade referencial.
- **Critérios de aceite B08 atendidos**:
  - [x] Splitters balanceados e desbalanceados mapeados com perdas nominais por porta.
  - [x] Ocupação de CTO calculada dinamicamente sem desvios.
  - [x] Vínculo de cliente associado a porta de atendimento com drop cable e geolocalização.
  - [x] Exclusão protegida por RESTRICT impedindo órfãos em históricos de atendimento.

---

### B09 — Rastreamento óptico
- **Data de conclusão**: 2026-09-17
- **Ações e Entregas**:
  - `backend/app/modules/optical/service.py`: Motor determinístico de rastreamento óptico bidirecional (`trace_optical_path`).
  - Travessia completa PON→ONU (downstream) e ONU→PON (upstream) através de cabos, fibras, tubos, terminais, conexões internas/externas e splitters.
  - Continuidade garantida em fusões diretas e passagens diretas (sangrias em caixas intermediárias) sem quebra indevida do feixe.
  - Tratamento correto de splitters com ramificação para portas de saída e agregação para a porta de entrada PON.
  - Detecção robusta de ciclos e pontas abertas com identificação de elementos atravessados e terminais não conectados.
  - `backend/app/api/v1/optical.py`: Endpoint `/api/v1/optical/trace` com permissão RBAC `optical:read`.
  - `backend/tests/integration/test_optical_path_tracing.py`: Testes de integração cobrindo travessia ponta a ponta, sangrias e prevenção de ciclos.
- **Critérios de aceite B09 atendidos**:
  - [x] Rastreamento bidirecional determinístico PON→ONU e ONU→PON.
  - [x] Continuidade física preservada em fibras passantes sem corte.
  - [x] Ramificação correta em splitters balanceados e desbalanceados.
  - [x] Detecção de ciclos e pontas abertas sem interrupção abrupta do serviço.

---

### B10 — Cálculo óptico independente
- **Data de conclusão**: 2026-09-17
- **Ações e Entregas**:
  - `backend/app/modules/optical/calculator.py`: Módulo de cálculo óptico desacoplado de banco de dados e de I/O.
  - Atenuação acumulada ao longo do enlace: perda de atenuação distribuída ($\alpha \times L$) para comprimentos de onda padrão (1310 nm, 1490 nm, 1550 nm), perdas de inserção de splitters, perdas por fusão e perdas por pares de conectores acoplados.
  - Margem de engenharia configurável, cálculo de potência recebida estimada ($P_{rx} = P_{tx} - A_{total}$) e limites de sensibilidade/sobrecarga do receptor.
  - Caso canônico da especificação validado numericamente: potência estimada de -20,68 dBm no receptor sob condições de referência.
  - `backend/app/modules/optical/service.py` e `backend/app/api/v1/optical.py`: Endpoint `/api/v1/optical/budget`.
  - `backend/tests/unit/test_optical_calculator.py` e `backend/tests/integration/test_optical_budget.py`: Suíte de testes unitários e de integração cobrindo o caso canônico e margens de projeto.
- **Critérios de aceite B10 atendidos**:
  - [x] Cálculo óptico isolado em módulo puro e determinístico.
  - [x] Caso canônico (-20,68 dBm) reproduzido com exatidão matemática.
  - [x] Discriminação explícita de perdas por elemento (conectores, fusões, splitters, fibra).
  - [x] Alertas automáticos de violação de sensibilidade e sobrecarga.

---

### B11 — Medições e comparação com previsão
- **Data de conclusão**: 2026-09-18
- **Ações e Entregas**:
  - Migração Alembic `0008_optical_measurements.py`: Tabela `optical_measurements` com campos tipados para comprimento de onda, potência medida em dBm, instrumento de teste, operador, direção e snapshot topológico.
  - Modelos ORM em `backend/app/modules/measurements/models.py`.
  - `backend/app/modules/measurements/service.py`: Registro de medições manuais e cálculo da perda excedente via fórmula canônica `perda_excedente = rx_previsto - rx_medido` (+6,10 dB no caso canônico de validação).
  - Controle de concorrência otimista via `If-Match`.
  - `backend/app/api/v1/measurements.py`: Endpoints para registro e consulta histórica de medições.
  - `backend/tests/integration/test_optical_measurements.py`: Testes de integração validando tolerâncias, snapshots e rejeição de comprimentos de onda incompatíveis.
- **Critérios de aceite B11 atendidos**:
  - [x] Medições registradas com instrumento, operador, direção e comprimento de onda.
  - [x] Snapshot de topologia capturado no momento do registro.
  - [x] Perda excedente calculada estritamente (+6,10 dB no caso canônico).
  - [x] Rejeição de diagnósticos precipitados e compatibilidade estrita de comprimento de onda.

---

### B12 — Impacto de rompimento e simulações
- **Data de conclusão**: 2026-09-18
- **Ações e Entregas**:
  - `backend/app/modules/topology/service.py`: Análise de impacto de rompimento em cabos e caixas, mapeando clientes e circuitos downstream impactados.
  - `backend/app/modules/optical/service.py`: Motor de simulação óptica em memória com suporte a overrides (atenuação pontual adicional em dB, alteração de comprimento de trecho e modificação de razão de splitter).
  - Cálculo de deltas (`delta_loss_db`, `delta_predicted_rx_dbm`) sem qualquer mutação de banco de dados.
  - Garantia estrita de invariância da `topology_revision`.
  - `backend/app/api/v1/topology.py` (`/api/v1/topology/impact`) e `backend/app/api/v1/optical.py` (`/api/v1/optical/simulations`).
  - `backend/tests/integration/test_optical_simulations.py`: Testes de integração cobrindo simulações de rompimento e invariância do estado da rede.
- **Critérios de aceite B12 atendidos**:
  - [x] Análise de impacto mapeia clientes e circuitos sem falsos positivos.
  - [x] Simulações com overrides em memória sem efeitos colaterais.
  - [x] Invariância do banco e da `topology_revision` após execuções de simulação.

---

### B13 — Fotos, anexos e auditoria
- **Data de conclusão**: 2026-09-18
- **Ações e Entregas**:
  - Migração Alembic `0009_attachments.py`: Tabela `attachments` criada com check constraints para content_type (`image/jpeg`, `image/png`, `image/webp`, `application/pdf`) e limite de bytes (até 20 MB), chaves estrangeiras, checksum SHA-256 e índices compostos.
  - `backend/app/modules/attachments/models.py`: Modelo ORM `Attachment` integrado a `VersionedModelMixin`.
  - `backend/app/modules/attachments/service.py`:
    - Validação física de magic bytes em binários recebidos (rejeição estrita de HTML ativo, SVG com scripts ou executáveis disfarçados).
    - Sanitização contra directory / path traversal (`sanitize_filename` tratando separadores POSIX e Windows e sequências `..`).
    - Geração de miniaturas seguras com redimensionamento e re-codificação WebP via Pillow.
    - Reconciliação de arquivos órfãos sem exclusão de anexos legítimos.
  - `backend/app/modules/audit/service.py`:
    - Registro append-only atômico na mesma transação SQLAlchemy (rollback da escrita anula o log de sucesso automaticamente).
    - Sanitização recursiva mascarando credenciais e segredos (`password`, `token`, `secret`, `api_key`).
    - Consulta paginada filtrável por tipo de entidade, identificador, autor e ação.
  - `backend/app/api/v1/attachments.py`: Endpoints completos com verificação CSRF, controle de concorrência `If-Match` para exclusão e streams de download/miniatura protegidos por RBAC.
  - `backend/app/api/v1/reports.py`: Endpoint `GET /api/v1/audit-events` implementado e conectado.
  - `backend/tests/integration/test_attachments_audit.py`: 7 testes de integração validando ciclo de vida de imagens e PDFs, bloqueio de usuário anônimo (401) e VIEWER (403), sanitização de path traversal, integridade de rollback e reconciliação de órfãos.
- **Resultados de Verificação**:
  - `uv run ruff check app tests` -> `All checks passed!`
  - `uv run mypy app` -> `Success: no issues found in 90 source files`
  - `uv run pytest` -> **125 passed, 0 failures** em 88.33s.
  - `uv run python scripts/export_openapi.py` -> 65 paths e 135 schemas sem drift.
- **Critérios de aceite B13 atendidos**:
  - [x] Upload inválido é recusado (tamanho, formato proibido ou cabeçalho adulterado).
  - [x] Usuário sem acesso não baixa arquivo por UUID conhecido (testado com 401 e 403).
  - [x] Escrita revertida não deixa auditoria de sucesso (atomicidade da sessão comprovada por teste).
  - [x] Anexos sobrevivem a restart (armazenados em volume e diretório configurável com metadados no Postgres).
- **Próximo passo alinhado**: B14 (Importação com prévia e exportação) / F16 (Importação e exportação no frontend).

---

### B14 — Importação com prévia e exportação
- **Data de conclusão**: 2026-09-18
- **Ações e Entregas**:
  - Migração Alembic `0010_async_jobs_and_imports.py`: Criadas tabelas `async_jobs` e `import_previews` com tipos enum (`job_type`, `job_status`, `import_format`, `collision_strategy`), chaves estrangeiras, índices compostos e leases/heartbeats.
  - `backend/app/modules/imports/models.py`: Modelos ORM `AsyncJob` e `ImportPreview` integrados ao SQLAlchemy e versionamento.
  - `backend/app/modules/imports/service.py`:
    - Parsers seguros para GeoJSON, KML/KMZ (usando `defusedxml.ElementTree` com proteção contra zip bombs e XML entity expansion) e CSV.
    - Mitigação de Formula Injection (`is_formula_injection`), distinguindo coordenadas geográficas negativas (ex: `-23.5505`) de fórmulas de planilha maliciosas (`=`, `+`, `-`, `@`).
    - Validação de schema e detecção rigorosa de colisões espaciais e de código em banco (`check_collisions`).
    - Geração de prévias detalhadas (`ImportPreview`) sem qualquer mutação da rede operacional antes da aprovação.
    - Commit transacional atômico (*All-or-Nothing*): se qualquer registro tiver erro ou colisão não resolvida, o commit é abortado com rollback total da transação.
    - Suporte a idempotência via `Idempotency-Key` (RFC 7395 / HTTP 202 com mesmo `job_id`).
  - `backend/app/modules/exports/service.py`:
    - Exportação determinística de topologia física em GeoJSON (FeatureCollections), KML (pastas estruturadas) e CSV.
    - Neutralização de injeção de fórmulas em planilhas (prefixo `'` em campos exportados).
    - Proteção LGPD: infraestrutura pública/física não expõe dados de clientes pessoais; exportação da camada `customers` restrita ao papel `admin` e auditada.
    - Limpeza de arquivos temporários e expiração de prévias em 24h.
  - `backend/app/modules/jobs/service.py`:
    - Fila de jobs assíncronos no PostgreSQL usando `SELECT FOR UPDATE SKIP LOCKED` para concorrência segura multi-worker sem deadlocks.
    - Mecanismo de leases temporários, batimentos cardíacos (`heartbeat`), cancelamento gracioso e recuperação pós-falha (*stale claim timeout*).
  - `backend/app/api/v1/imports_exports.py`:
    - Endpoints de upload (`POST /api/v1/imports/preview`), confirmação atômica (`POST /api/v1/imports/{preview_id}/commit`), consulta de jobs (`GET /api/v1/jobs/{job_id}`), cancelamento (`POST /api/v1/jobs/{job_id}/cancel`), solicitação de exportação (`POST /api/v1/exports`) e download autenticado com streaming (`GET /api/v1/exports/{job_id}/download`).
  - `backend/tests/integration/test_imports_exports_jobs.py`: 8 testes de integração cobrindo ciclo de vida completo de importação GeoJSON/KML/CSV, detecção e bloqueio por colisões, atomicidade total no commit, idempotência de cabeçalho, exportação protegida por LGPD e concorrência de jobs via SKIP LOCKED.
- **Resultados de Verificação**:
  - `uv run ruff check app tests` -> `All checks passed!`
  - `uv run mypy app` -> `Success: no issues found in 95 source files`
  - `uv run pytest` -> **133 passed, 0 failures** em 130.56s.
  - OpenAPI schema atualizado sem drift.
- **Critérios de aceite B14 atendidos**:
  - [x] Arquivo malformado, zip bomb ou fórmula maliciosa rejeitado sem persistência.
  - [x] Prévia criada sem mutação da rede operacional e com detecção de colisões.
  - [x] Commit é transacional All-or-Nothing (falha reverte todo o lote).
  - [x] Idempotency-Key evita duplicação de jobs ou dados.
  - [x] Exportação de infraestrutura protege dados pessoais e neutraliza injeção em CSV.
  - [x] Workers recuperam jobs interrompidos via SKIP LOCKED e expiração de lease.
- **Próximo passo alinhado**: B15 (Busca global, painel e relatórios) e F17 (Relatórios e capacidade no frontend).

---

### B15 — Busca global, painel e relatórios
- **Data de conclusão**: 2026-09-18
- **Ações e Entregas**:
  - `backend/app/modules/reports/service.py`:
    - `calculate_dashboard_summary`: Contadores reais de sites, estruturas, cabos, assinantes, atendimentos ativos, e distribuição exata nos 4 buckets de ocupação de CTOs (0%, 1-50%, 51-99%, 100%), além de detecção de anomalias/incompletudes cadastrais (cabos sem segmentos, estruturas sem site associado, portas com anotação de defeito/avaria) e revisão topológica.
    - `execute_global_search`: Mecanismo de busca textual indexada multi-entidade (sites, estruturas, cabos, dispositivos por código/modelo/serial, e clientes). Proteção estrita de escopo para LGPD: assinantes/clientes só são pesquisados e retornados se o usuário autenticado possuir permissão `customers:read` (papéis admin e engineer).
    - `get_cto_occupancy_report`: Relatório paginado com contadores de portas totais, ocupadas, reservadas, livres, taxa de ocupação em percentual, com filtros por `site_id`, `status` e faixa de ocupação percentual mínima/máxima.
    - `get_cable_capacity_report`: Relatório paginado de cabos com total de fibras, fibras conectadas, reservadas, danificadas, livres, taxa de utilização percentual e filtros por `status` e utilização mínima.
    - `get_inconsistencies_report`: Relatório paginado de anomalias técnicas e pendências da malha física e lógica com classificação de severidade (crítica, alerta).
  - `backend/app/schemas/reports.py`: Modelos Pydantic tipados `CTOOccupancyReportItem`, `CableCapacityReportItem`, `InconsistencyReportItem`, `DashboardSummaryResponse`, `GlobalSearchResponse`.
  - `backend/app/api/v1/reports.py`: Endpoints conectados e protegidos:
    - `GET /api/v1/dashboard/summary`
    - `GET /api/v1/search`
    - `GET /api/v1/reports/ctos` (requer `reports:read`)
    - `GET /api/v1/reports/cables` (requer `reports:read`)
    - `GET /api/v1/reports/inconsistencies` (requer `reports:read`)
  - `backend/tests/integration/test_reports_dashboard_search.py`: Suíte de integração com 5 testes passando em PostgreSQL/PostGIS real cobrindo cálculo exato de buckets de ocupação, emissão de alertas automáticos, isolamento de dados de clientes na busca textual via RBAC, paginação e filtros nos relatórios e bloqueio 401 não-autenticado.
- **Resultados de Verificação**:
  - `uv run ruff check app tests` -> `All checks passed!`
  - `uv run mypy app` -> `Success: no issues found in 96 source files`
  - `uv run pytest tests/integration/test_reports_dashboard_search.py` -> 5 passed em 6.63s.
  - `uv run pytest tests/contract/` -> 13 passed em 12.64s.
  - Contrato OpenAPI (`contracts/openapi.json`) exportado e atualizado (68 paths, 141 schemas).
- **Critérios de aceite B15 atendidos**:
  - [x] Ocupação de CTO reflete o estado cadastrado da rede (portas ocupadas, reservadas e livres).
  - [x] Contadores do painel batem com o inventário real sem dados simulados ou inventados.
  - [x] Busca não vaza dados de clientes para usuários sem autorização explícita (`customers:read`).
  - [x] Relatórios paginados respondem com precisão para filtros de capacidade e integridade física.
- **Próximo passo alinhado**: F17 (Relatórios e capacidade no frontend) e B16 (Desempenho e observabilidade).

---

### B16 — Desempenho e observabilidade
- **Data de conclusão**: 2026-09-18
- **Ações e Entregas**:
  - `backend/app/core/metrics.py`: Módulo thread-safe de métricas estruturadas (`MetricsCollector`) com formatação padrão Prometheus exposition text e JSON:
    - Contadores e histogramas: `ftth_http_requests_total`, `ftth_http_request_duration_seconds` (com buckets precisos de 1ms até 10s), `ftth_background_jobs_total`.
    - Gauges operacionais de infraestrutura: `ftth_db_pool_size`, `ftth_db_pool_checked_out`, `ftth_db_pool_overflow`, `ftth_topology_revision`.
    - Política estrita de baixa cardinalidade (`normalize_route_path`): substituição determinística de UUIDs, IDs numéricos e tokens de rota por placeholders estáticos (`{id}`), sem inclusão de parâmetros de consulta (query params), IDs de usuário ou PII de clientes.
  - `backend/app/core/middleware.py`: Integração automática de telemetria no `RequestIDMiddleware` para medição da duração de todas as requisições HTTP e registro nos histogramas de métricas.
  - `backend/app/api/v1/metrics.py`: Endpoint `/api/v1/metrics` suportando formato Prometheus (text/plain) e JSON (`?format=json`). Protegido por chave via cabeçalho `X-Metrics-Token` ou sessão ativa com permissão de administrador. Retorna Problem Details 401/403 em acessos não autorizados.
  - `backend/app/modules/topology/service.py` e `backend/app/schemas/topology.py`:
    - Adicionado limite explícito de profundidade/saltos `max_hops` (padrão 200, máx 500) na requisição de optical trace (`TraceRequest`).
    - Otimização de consultas com eager loading (`joinedload` para `cable_segment` e `cable`, `selectinload` para `splitter.outputs`), eliminando problemas de N+1 queries durante a travessia de topologia.
  - `backend/scripts/generate_synthetic_load.py`: Gerador reproduzível de carga sintética executado no banco `ftth_manager_test` em 24,49s gerando:
    - 10.001 estruturas (1 POP site, 500 CEOs, 2.500 CTOs, 7.000 postes) — Meta: $\ge 10.000$.
    - 103.200 segmentos de fibra em 5.050 cabos (50 troncos, 1.000 distribuição, 4.000 drops) — Meta: $\ge 100.000$.
    - 206.428 terminais ópticos (modelo $2N$), 500 splitters 1:8, 2.500 splitters 1:16, e circuito óptico ativo fim-a-fim.
  - `backend/scripts/benchmark_endpoints.py`: Suíte de medição de desempenho e latência p95 executada contra a base sintética com relatório detalhado em `docs/benchmark-b16.md`:
    - Map Bounding Box (Pequena ~500m): média 6,13 ms, p95 10,89 ms (Meta: < 1s) — **Aprovado** (~100x mais rápido que o alvo).
    - Map Bounding Box (Média ~2km): média 5,68 ms, p95 8,46 ms (Meta: < 1s) — **Aprovado**.
    - Map Bounding Box (Grande ~10km truncada): média 6,41 ms, p95 11,81 ms (Meta: < 1s) — **Aprovado**.
    - Optical Trace Downstream (OLT -> ONU): média 6,48 ms, p95 11,04 ms (Meta: < 2s) — **Aprovado** (~180x mais rápido que o alvo).
    - Optical Trace Upstream (ONU -> OLT): média 6,04 ms, p95 10,49 ms (Meta: < 2s) — **Aprovado** (~190x mais rápido que o alvo).
    - Verificação de planos de execução com `EXPLAIN (ANALYZE, BUFFERS)`: índices GiST espaciais (`idx_structures_location` em 0,16ms e `idx_cable_segments_geometry` em 0,58ms) e índices B-tree nos terminais (`ix_fiber_segments_terminal_a_id` em 0,008ms).
    - Teste de concorrência e inanição: sob carga concorrente contínua de 20 requisições simultâneas de bounding box e trace óptico, o endpoint `/health/ready` respondeu com latência média de 73,14 ms (máx 101,68 ms) com 0 falhas e 0 inanição de conexões do pool.
  - `backend/tests/integration/test_performance_observability.py`: 3 testes de integração verificando endpoint de métricas (autorização, Prometheus e JSON) e concorrência sem inanição.
- **Resultados de Verificação**:
  - `uv run ruff check app tests scripts` -> `All checks passed!`
  - `uv run mypy app` -> `Success: no issues found in 98 source files`
  - `uv run pytest tests/contract tests/integration/test_performance_observability.py` -> 16 passed em 8.68s.
  - Contrato OpenAPI (`contracts/openapi.json`) e tipos TS atualizados (69 paths, 141 schemas).
- **Critérios de aceite B16 atendidos**:
  - [x] Dataset sintético atende ou supera as metas ($\ge 10.000$ estruturas e $\ge 100.000$ segmentos de fibra).
  - [x] Consulta de mapa por bounding box responde com p95 < 1s em carga (atingiu p95 de 10,89 ms).
  - [x] Rastreamento óptico responde com p95 < 2s em carga (atingiu p95 de 11,04 ms).
  - [x] Planos de execução confirmam uso de índices espaciais GiST e ausência de varreduras sequenciais em dados pontuais.
  - [x] Métricas estruturadas expostas em formato Prometheus e JSON com cardinalidade estritamente controlada e segura.
  - [x] Carga pesada de consultas não causa inanição do health check (`/health/ready`).
- **Próximo passo alinhado**: F18 (Campo, acessibilidade e desempenho no frontend) e B17 (Implantação, backup e manutenção).

---

### B17 — Implantação, backup e manutenção
- **Data de conclusão**: 2026-09-18
- **Ações e Entregas**:
  - `compose.yaml`: Arquitetura multi-serviço finalizada com `db` (PostGIS 16-3.4 isolado em rede privada sem porta pública), `migrate` (execução única e atômica do Alembic antes da inicialização), `backend` (FastAPI com healthcheck e usuário não-root `ftthuser`), `worker` (processamento assíncrono de jobs B14), `frontend` (Next.js standalone com usuário não-root `nextjs`) e `caddy` (Caddy 2.8.4 como reverse proxy e terminação TLS com Content-Security-Policy estrita).
  - `Caddyfile`: Configuração de proxy reverso encaminhando `/api/*` e `/health/*` ao FastAPI e rotas web ao Next.js, compressão gzip/zstd, cabeçalhos de segurança (X-Frame-Options, X-Content-Type-Options, Referrer-Policy) e CSP compatível com tiles cartográficos (OpenStreetMap e CartoDB) e workers do MapLibre.
  - `compose.override.yaml.example`: Modelo para desenvolvedores exporem portas no host local de forma opt-in.
  - `backend/Dockerfile` e `frontend/Dockerfile`: Imagens otimizadas em múltiplos estágios com execução em usuário não-root (`ftthuser` UID 1000 e `nextjs` UID 1001) e volumes persistentes.
  - `backend/app/main.py`: Adicionado `ProxyHeadersMiddleware` do Uvicorn para encaminhamento confiável de cabeçalhos proxy (`X-Forwarded-For`, `X-Forwarded-Proto`).
  - `backend/app/core/backup_restore.py`: Módulo robusto de backup e restauração atômica:
    - Suporte a banco de dados relacional e espacial com fallback de alto desempenho via protocolo binário COPY do psycopg com `SET session_replication_role = 'replica'`.
    - Backup consistente de DB + Anexos/Fotos em disco + Manifesto assinado com SHA256 para todos os arquivos.
    - Captura e validação da revisão topológica (`topology_revision`) e versão de schema do Alembic.
    - Mecanismo de expurgo e retenção de backups antigos (`prune_old_backups`).
  - `backend/scripts/backup.py` e `scripts/backup.sh`: Utilitários CLI de backup com parâmetros de retenção e diretório.
  - `backend/scripts/restore.py` e `scripts/restore.sh`: Utilitários CLI de restauração com verificação de integridade por checksum SHA256.
  - `backend/scripts/run_worker.py`: Daemon do worker de segundo plano consumindo jobs com `SKIP LOCKED` e suporte a SIGTERM gracioso.
  - `backend/scripts/restore_drill.py`: Script completo de simulação real de desastre (Restore Drill) executado em ambiente isolado:
    - Cria cenário complexo com POP, OLT, cabos, fusões, CTO, circuito óptico e anexo real com foto JPEG física validada.
    - Executa backup atômico.
    - Restaura em banco e diretório de storage 100% isolados.
    - Valida pós-restauração: integridade referencial, rastreamento óptico idêntico com mesma revisão topológica, foto física idêntica byte-a-byte com magic bytes JPEG (`\xFF\xD8\xFF`) e contadores de entidades intactos.
  - `docs/runbooks/deployment-and-maintenance.md`: Runbook completo cobrindo instalação limpa, atualização, backup, restore drill, retenção, política de roll-forward para migrações destrutivas, rotação de segredos e requisitos de firewall/servidor de tiles.
- **Resultados de Verificação**:
  - `uv run ruff check app tests scripts` -> `All checks passed!`
  - `uv run mypy app` -> `Success: no issues found in 99 source files`
  - `uv run python scripts/restore_drill.py` -> **RESTORE DRILL B17: SUCESSO ABSOLUTO (PASS 100%)**
- **Critérios de aceite B17 atendidos**:
  - [x] Compose sobe com web, api, db (PostGIS privado), worker, migrate e caddy.
  - [x] Restart preserva dados em volumes persistentes.
  - [x] Backup restaurado abre caminho óptico e foto física sem perdas.
  - [x] Sem credenciais padrão; bootstrap exige senha fornecida pelo operador.
  - [x] Documentação e runbook explicam servidor de tiles configurável e requisitos de rede.
- **Próximo passo alinhado**: B18 (Auditoria final e entrega open source) e F19 (Testes integrados e qualidade).

---

### B18 — Auditoria final e entrega open source
- **Data de conclusão**: 2026-09-18
- **Ações e Entregas**:
  - `backend/app/api/v1/topology.py` e `backend/app/modules/topology/service.py`: Endpoint `POST /api/v1/topology/impact` conectado com a lógica real de simulação virtual de rompimento de cabos (`analyze_cable_impact`), identificando os clientes (`CLI-DEMO-001`), CTOs e portas PON atingidas com integridade e sem mutação do banco de dados operacional.
  - `backend/tests/integration/test_full_lifecycle_b18.py`: Teste transversal ponta a ponta executado com 100% de sucesso cobrindo toda a jornada do provedor (Admin -> POP/OLT/DIO -> Feeder 3.5 km -> CEO/Fusão/Splitter 1:8 -> Dist 3.5 km -> CTO/Splitter 1:8 -> Drop/ONU/Cliente DEMO-001 -> Optical Trace 7.0 km exatos -> Cálculo de Orçamento Óptico GPON Classe B+ aprovado -> Medição de Campo -22.50 dBm -> Rompimento Virtual de Cabo -> Solicitação de Exportação de Topologia -> Backup atômico com checksums SHA256 e restauração isolada).
  - `backend/scripts/seed_demo.py`: Script CLI idempotente e determinístico para população opt-in do cenário de demonstração (`uv run python scripts/seed_demo.py [--clean] [--target-db dev|test]`), cobrindo todo o trajeto de 7 km, clientes independentes em rotas não afetadas, ramal com ponta aberta para aviso de incompletude, fusão sem medição e medição degradada para relatórios gerenciais. Estritamente opt-in, sem execução automática no boot de produção.
  - `.github/workflows/ci.yml`: Pipeline completa de CI no GitHub Actions com PostGIS 16-3.4, sincronização uv, verificação Ruff (linter e format), Mypy em modo estrito, gate de drift do contrato OpenAPI (`test_openapi_schema.py`), migrações Alembic, suíte Pytest com cobertura, Restore Drill de desastre e pipeline frontend (ESLint, Typecheck e Vitest).
  - `docs/entity-relationship-model.md`: Modelo relacional e grafo espacial documentado com diagramas Mermaid, modelo de terminais $2N$, check constraints e regras de integridade física.
  - `docs/api-catalog.md`: Catálogo completo de endpoints, convenções de autenticação por cookies seguros, tokens CSRF, matriz RBAC, padrões RFC 7807 e concorrência otimista com If-Match.
  - `docs/requirement-test-matrix.md`: Matriz de rastreabilidade completa mapeando todas as etapas B01–B18 e F01–F20 para suítes de testes automatizados reais.
  - `docs/audit-b18.md`: Relatório formal de auditoria com checklist de status PASS/FAIL/BLOCKED para todos os critérios de aceite da fase B18 e recomendação de licença (AGPL-3.0 / Apache-2.0).
  - `CONTRIBUTING.md` e `SECURITY.md`: Políticas de governança de código aberto, processo de contribuição, padrões de commit e processo de divulgação responsável de vulnerabilidades.
  - `README.md`: Atualizado com status global completo, guia de execução local com `seed_demo.py`, contadores de testes atualizados e instruções de implantação com Docker Compose.
- **Resultados de Verificação**:
  - `uv run ruff check app tests scripts` -> `All checks passed!`
  - `uv run mypy app` -> `Success: no issues found in 99 source files`
  - `uv run pytest tests/integration/test_full_lifecycle_b18.py` -> `1 passed in 3.09s`
  - `uv run pytest` -> **140 passed, 16 warnings in 155.92s (100% PASS)**
  - `cd ../frontend && pnpm lint && pnpm typecheck && pnpm test` -> **166 passed in 19 test files (100% PASS)**
- **Critérios de aceite B18 atendidos**:
  - [x] Teste de ciclo completo executa a jornada inteira sem mocks e passa em banco limpo.
  - [x] Seed cobre o cenário transversal com 7 km, 4 fusões, 2 mated pairs, 2 splitters 1:8, clientes não afetados e ramos anômalos.
  - [x] Seed não roda automaticamente no boot de produção; acionado exclusivamente via CLI.
  - [x] CI workflow configurado com PostGIS, linters, types, drift OpenAPI e testes de backend e frontend.
  - [x] Documentação técnica completa: ERD, catálogo de APIs, matriz de requisitos e relatório de auditoria B18.
  - [x] Governança open source estabelecida: CONTRIBUTING.md, SECURITY.md e recomendação de licença.
  - [x] Sem regressões em nenhuma fase anterior: 140 testes de backend e 166 de frontend aprovados.
- **Próximo passo alinhado**: F19 (Testes integrados e qualidade) e F20 (Entrega e revisão de produto).


