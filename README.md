# FTTH Manager

Sistema open source e self-hosted para gestão técnica e operacional de redes de fibra óptica (FTTH), cobrindo inventário de infraestrutura, GIS geodésico, conectividade fibra a fibra, splitters, clientes, rastreamento óptico, cálculo de potência e auditoria completa.

---

## 🚀 Status do Projeto (Roadmap Backend B01–B18)

O backend segue estritamente as etapas definidas em [`backend.md`](file:///home/bruno/projects/ftth_tiiv/backend.md).

| Etapa | Descrição | Status |
|---|---|:---:|
| **B01** | **Fundação reproduzível**: Configurações tipadas, logging JSON sanitizado, RFC 7807 Problem Details, healthchecks (`/health/live`, `/health/ready`), Compose e isolamento de domínio. | ✅ Concluído |
| **B02** | **Contrato e schemas**: Schemas Pydantic v2, paginação estrita, enums, contratos pendentes 501, exportador determinístico para `contracts/openapi.json` e tipos TypeScript em `contracts/api-types.d.ts`. | ✅ Concluído |
| **B03** | **Sessões, usuários e permissões**: Hashing Argon2id, mitigação de enumeração de timing, CSRF com double submit cookie, rate limiting distribuído no PostgreSQL, sessões com expiração absoluta e inatividade, RBAC granular e CLI de bootstrap de admin. | ✅ Concluído |
| **B04** | **Inventário e migrações**: Sites, Estruturas (Postes, Caixas CEO/CTO, POPs), Dispositivos (OLT, Switch, DIO), Portas com regras de propriedade estrita, Perfis Ópticos com check constraints de limites físicos e integridade referencial. | ✅ Concluído |
| **B05** | **GIS e comprimentos confiáveis**: SRID 4326, GeoJSON, validação estrita de geometrias e bounding box, comprimentos geodésicos em metros via PostGIS geography, regra óptica contra dupla contagem de reserva, tolerância de rotas (5m), índice GiST espacial e controle monotônico de `topology_revision`. | ✅ Concluído |
| **B06** | **Cabos, tubos, fibras e segmentação**: Cabos multitubo e monotubo com agrupamento lógico, catálogos flexíveis de cores (ABNT NBR 14106, TIA-598, DIN), geração de $2N$ terminais normalizados por trecho, divisão atômica de segmento em estrutura intermediária com preservação de continuidade óptica para fibras passantes (0.0 dB) e conexões externas pré-existentes. | ✅ Concluído |
| **B07** | **Motor de conectividade e fusões**: Modelos de banco de dados e migração `0006_connectivity_engine` criados e aplicados (`connection_endpoints` com índice único parcial no Postgres, `terminal_reservations`, `internal_edges` DIO sem fan-out, `audit_events` append-only). Implementação do editor de fusão em lote e endpoints em andamento. | 🔄 Em andamento |
| **B08** | **Splitters, CTOs e atendimento** | ⏳ Pendente |
| **B09** | **Rastreamento óptico** | ⏳ Pendente |
| **B10** | **Cálculo óptico independente e testável** | ⏳ Pendente |
| **B11** | **Medições e comparação com previsão** | ⏳ Pendente |
| **B12** | **Impacto de rompimento e simulações** | ⏳ Pendente |
| **B13** | **Fotos, anexos e auditoria** | ⏳ Pendente |
| **B14** | **Importação e exportação confiáveis** | ⏳ Pendente |
| **B15** | **Hardening, observabilidade e migração de produção** | ⏳ Pendente |
| **B16** | **Datasets de teste e validação de ponta a ponta** | ⏳ Pendente |
| **B17** | **Documentação operacional** | ⏳ Pendente |
| **B18** | **Auditoria final e entrega open source** | ⏳ Pendente |

---

## 🛠️ Stack Tecnológica

- **Linguagem & Runtime**: Python 3.12 gerenciado via `uv`
- **Framework Web**: FastAPI com Pydantic v2
- **Banco de Dados**: PostgreSQL 16 com extensão espacial PostGIS 3.4
- **ORM & Driver**: SQLAlchemy 2 (síncrono), GeoAlchemy2, `psycopg` v3 binary
- **Migrações**: Alembic com suporte a upgrade e downgrade bidirecional
- **Segurança**: Criptografia Argon2id, mitigação de enumeração, proteção CSRF e cabeçalhos de segurança
- **Contratos**: OpenAPI 3.1 determinístico e tipagens TypeScript (`contracts/`)
- **Qualidade de Código**: Ruff (linter e formatter) e Mypy (modo estrito)

---

## 🏛️ Princípios Arquiteturais Obrigatórios

1. **Integridade no Banco**: Regras essenciais são impostas por Foreign Keys (`ON DELETE RESTRICT`), Check Constraints e Índices Únicos (incluindo índices parciais no PostgreSQL). Validação em Python é uma camada de conveniência, nunca a única garantia.
2. **Isolamento de Domínio**: Nenhum acesso ao banco de dados ocorre durante o import de módulos. Testado com `backend/tests/unit/test_domain_isolation.py`.
3. **Unidades Físicas Explícitas**: Todos os nomes de campos possuem unidades explícitas (`map_length_m`, `measured_length_m`, `slack_length_m`, `loss_db`, `tx_power_dbm`, `wavelength_nm`, `attenuation_db_per_km`).
4. **Concorrência Otimista**: Mutações em recursos de inventário e conectividade exigem controle de versão via cabeçalho `If-Match: "<version>"`. Ausência retorna HTTP 428 (`Precondition Required`) e versão divergente retorna HTTP 412 (`Precondition Failed`).
5. **Erros RFC 7807**: Todas as respostas de erro seguem rigorosamente o padrão RFC 7807 (`application/problem+json`).
6. **Contratos Honestos**: Endpoints das etapas ainda não implementadas retornam HTTP 501 Problem Details (`endpoint_pending_implementation`), sem simulações falsas de sucesso.

---

## 🚀 Como Executar Localmente

### 1. Pré-requisitos
- Docker ou Podman com Compose
- Python 3.12 e [`uv`](https://github.com/astral-sh/uv)

### 2. Iniciar o Banco de Dados PostGIS
```bash
docker compose up -d db
# ou com podman:
podman compose up -d db
```

### 3. Configurar o Ambiente e Migrações
```bash
cd backend
uv sync
uv run alembic upgrade head
```

### 4. Criar ou Redefinir Usuário Administrador (CLI)
```bash
uv run python -m app.cli.bootstrap_admin --username admin --password "Admin@123456" --email admin@example.com --reset
```

### 5. Iniciar o Servidor de Desenvolvimento
```bash
uv run uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --reload
```

---

## 🧪 Testes e Qualidade

O projeto conta com suíte automatizada de testes cobrindo unidades, integração com banco de dados real e validação de contratos OpenAPI:

```bash
cd backend

# Executar suíte completa de testes
uv run pytest

# Verificação de lint e formatação
uv run ruff check .
uv run ruff format --check .

# Verificação estrita de tipagem estática
uv run mypy .
```

---

## 📂 Documentação e ADRs

- [`backend.md`](file:///home/bruno/projects/ftth_tiiv/backend.md): Especificação técnica e requisitos funcionais completos B01–B18.
- [`docs/progress-backend.md`](file:///home/bruno/projects/ftth_tiiv/docs/progress-backend.md): Registro contínuo de entregas, critérios de aceite atendidos e comandos executados.
- [`docs/adr/`](file:///home/bruno/projects/ftth_tiiv/docs/adr/): Architecture Decision Records formais:
  - `0001-stack-and-environment-decisions.md`
  - `0002-api-contracts-and-pydantic-v2.md`
  - `0003-authentication-sessions-and-rbac.md`
  - `0004-inventory-data-model-and-constraints.md`
  - `0005-gis-geodetic-lengths-and-map-features.md`
  - `0006-cables-fibers-and-segment-splitting.md`
