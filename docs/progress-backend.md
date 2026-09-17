# FTTH Manager — Progresso do Backend

Este documento rastreia a evolução contínua da implementação do backend conforme a especificação `backend.md`.

---

## Status Geral por Etapa

| Etapa | Nome | Status | Evidências / Observações |
|---|---|---|---|
| **B01** | **Fundação reproduzível** | Concluído | Configuração tipada, uv.lock, Dockerfile multi-stage, health live/ready, RFC 7807, logs JSON mascarando segredos, Alembic PostGIS e 17 testes automatizados passando. |
| **B02** | **Contrato e schemas antes de telas** | Concluído | OpenAPI determinístico em `contracts/openapi.json` (60 paths, 124 schemas), types TypeScript gerados (`contracts/api-types.d.ts`), units explícitas, 28 testes passando e detecção de drift. |
| **B03** | **Sessões, usuários e permissões** | Concluído | Autenticação Argon2id, sessões opacas com expiração (7d) e inatividade (24h), CSRF com Origin e Double-Submit, rate limit no PostgreSQL (5 tentativas/15min), RBAC estrito, CLI de bootstrap admin e 41 testes passando. |
| **B04** | **Inventário e migrações** | Concluído | Modelos de sites, structures, devices, ports, catálogos e perfis ópticos com PostGIS, constraints exclusivas, 0003 migration e 56 testes passando. |
| **B05** | **GIS e comprimentos confiáveis** | Concluído | SRID 4326, GeoJSON, PostGIS geography para comprimentos em metros, regra óptica (sem dupla reserva), tolerância de rota, GiST bbox, truncated flag, revisão de topologia e 73 testes passando. |
| **B06** | **Cabos, tubos, fibras e segmentação** | Pendente | Geração transacional de cabo, tubos, fibras, segmentos e divisão com preservação de continuidade. |
| **B07** | **Motor de conectividade e fusões** | Pendente | Terminais normalizados, conexões atômicas, lote com `expected_topology_revision`. |
| **B08** | **Splitters, CTOs e atendimento** | Pendente | Splitters 1:N, portas CTO, ocupação e service links com histórico. |
| **B09** | **Rastreamento óptico** | Pendente | Algoritmo de travessia PON→ONU e ONU→PON com semântica de portas e splitters. |
| **B10** | **Cálculo óptico independente** | Pendente | Módulo puro de cálculo de atenuação, perdas, TX/RX, sensibilidade e sobrecarga. |
| **B11** | **Medições e comparação com previsão** | Pendente | Leituras manuais de potência, tolerâncias e cálculo de perda excedente. |
| **B12** | **Impacto de rompimento e simulações** | Pendente | Análise de falha em grafo virtual sem mutação no estado operacional. |
| **B13** | **Fotos, anexos e auditoria** | Pendente | Armazenamento de arquivos com validação de mime/conteúdo e auditoria append-only. |
| **B14** | **Importação com prévia e exportação** | Pendente | Importadores GeoJSON/KML/CSV, validação prévia e commit idempotente; exportações com jobs. |
| **B15** | **Busca, painel e relatórios** | Pendente | Busca global, métricas de ocupação de CTO e relatórios de viabilidade óptica. |
| **B16** | **Desempenho e observabilidade** | Pendente | Dataset sintético de carga, medição de latência e métricas estruturadas. |
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
- **Próximo passo**: Etapa **B07 — Motor de conectividade e fusões** (terminais normalizados, arestas internas, conexões externas, conexão/desconexão/reserva, lote atômico para editor de fusão com `expected_topology_revision`, bloqueio determinístico anti-deadlock e prevenção de dupla ocupação concorrente no banco).
