# FTTH Manager — Progresso do Backend

Este documento rastreia a evolução contínua da implementação do backend conforme a especificação `backend.md`.

---

## Status Geral por Etapa

| Etapa | Nome | Status | Evidências / Observações |
|---|---|---|---|
| **B01** | **Fundação reproduzível** | Concluído | Configuração tipada, uv.lock, Dockerfile multi-stage, health live/ready, RFC 7807, logs JSON mascarando segredos, Alembic PostGIS e 17 testes automatizados passando. |
| **B02** | **Contrato e schemas antes de telas** | Concluído | OpenAPI determinístico em `contracts/openapi.json` (60 paths, 124 schemas), types TypeScript gerados (`contracts/api-types.d.ts`), units explícitas, 28 testes passando e detecção de drift. |
| **B03** | **Sessões, usuários e permissões** | Pendente | Autenticação Argon2id, sessões opacas com expiração, CSRF, rate limit em banco, RBAC e CLI bootstrap. |
| **B04** | **Inventário e migrações** | Pendente | Modelos de sites, structures, devices, ports, catálogos e perfis ópticos. |
| **B05** | **GIS e comprimentos confiáveis** | Pendente | PostGIS SRID 4326, bbox indexado, comprimentos geográficos vs medidos vs reservas. |
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
- **Próximo passo**: Etapa **B03 — Sessões, usuários e permissões** (Argon2id, tabela de sessões opacas com expiração e rotação, rate limit persistido, proteção CSRF com cookie de vínculo, CLI de bootstrap admin e controle de perfis RBAC).
