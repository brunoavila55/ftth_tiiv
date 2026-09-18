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
| **B07** | **Motor de conectividade e fusões**: Modelos de banco de dados, migração `0006_connectivity_engine`, `connection_endpoints` com índice único parcial no Postgres, reservas de terminais, arestas internas de DIO sem fan-out, auditoria append-only, serviço com bloqueio determinístico anti-deadlock, endpoints `/connections` e `/connections/batch` (editor de fusão) e testes de integração com 100% de cobertura dos critérios de aceite. | ✅ Concluído |
| **B08** | **Splitters, CTOs e atendimento**: Splitters balanceados e desbalanceados 1:N, mapeamento de saídas, ocupação em tempo real, cadastro de clientes e vínculos de atendimento com drop (migração 0007). | ✅ Concluído |
| **B09** | **Rastreamento óptico**: Motor determinístico de travessia PON→ONU e ONU→PON no grafo de rede, sem corte em passagens diretas, ramificação correta em splitters e detecção de ciclos/pontas abertas. | ✅ Concluído |
| **B10** | **Cálculo óptico independente**: Módulo puro de cálculo de atenuação acumulada, perdas de inserção, conectores acoplados, margem de engenharia, limiares de sensibilidade e sobrecarga (caso canônico -20,68 dBm). | ✅ Concluído |
| **B11** | **Medições e comparação com previsão**: Registro de medições manuais (migração 0008), snapshots de topologia, cálculo canônico de perda excedente (`previsto - medido = +6,1 dB`), tolerâncias e concorrência otimista. | ✅ Concluído |
| **B12** | **Impacto de rompimento e simulações**: Simulações com overrides em memória (perda pontual, comprimento, razão de splitter), cálculo de deltas e invariância estrita do banco e da `topology_revision`. | ✅ Concluído |
| **B13** | **Fotos, anexos e auditoria**: Anexos privados em volume persistente (migração 0009), validação de magic bytes (JPEG/PNG/WebP/PDF), sanitização de path traversal, thumbnails seguros, auditoria append-only com rollback atômico e reconciliação de órfãos. | ✅ Concluído |
| **B14** | **Importação e exportação confiáveis**: Importadores GeoJSON/KML/CSV com prévia/commit idempotente e exportações com jobs em background no PostgreSQL. | ⏳ Próxima |
| **B15** | **Busca global, painel e relatórios**: Métricas consolidadas, ocupação de CTOs, relatórios de viabilidade e qualidade da documentação. | ⏳ Pendente |
| **B16** | **Desempenho e observabilidade**: Datasets sintéticos de carga (10k+ nós), benchmarks e métricas estruturadas com request_id. | ⏳ Pendente |
| **B17** | **Implantação, backup e manutenção**: Docker Compose de produção com Caddy, rotinas de backup consistente e drill de restore testado. | ⏳ Pendente |
| **B18** | **Auditoria final e entrega open source**: Suíte ponta a ponta, matriz de requisitos e documentação final de lançamento. | ⏳ Pendente |

---

## 🎨 Status do Projeto (Roadmap Frontend F01–F20)

O frontend segue rigorosamente as etapas definidas em [`frontend.md`](file:///home/bruno/projects/ftth_tiiv/frontend.md).

| Etapa | Descrição | Status |
|---|---|:---:|
| **F01** | **Fundação e cliente de API**: Next.js App Router, TypeScript strict, Tailwind, shadcn/ui, tipagens OpenAPI, cliente de API com CSRF/cookies/RFC 7807 e testes. | ✅ Concluído |
| **F02** | **Design system, shell e navegação**: AppShell, navegação lateral/drawer, cabeçalho, busca global, breadcrumbs e alternância claro/escuro. | ✅ Concluído |
| **F03** | **Login, sessão e acesso**: Tela de login com cookie seguro, CSRF, logout, perfil e guards de rota por permissões RBAC. | ✅ Concluído |
| **F04** | **Tabelas, formulários e conflitos**: Componentes reutilizáveis de tabela paginada no servidor, formulários com Zod e tratamento de If-Match (412/409). | ✅ Concluído |
| **F05** | **Dashboard e busca global**: Painel executivo com cards e busca global rápida por teclado (`Ctrl+K`). | ✅ Concluído |
| **F06** | **Mapa operacional**: Visualizador geográfico MapLibre GL JS com renderização WebGL de camadas (sites, estruturas, cabos). | ✅ Concluído |
| **F07** | **Desenho e edição geográfica**: Ferramentas de desenho vetorial de pontos, rotas e traçado de cabos com snap a estruturas. | ✅ Concluído |
| **F08** | **Cadastros de rede física**: Telas de gestão e detalhes com abas para Sites, Postes, CEOs, CTOs e Dispositivos. | ✅ Concluído |
| **F09** | **Cabos, tubos e fibras**: Visualização detalhada de cabos, tubos e fibras por código de cores e fluxo de divisão de trechos. | ✅ Concluído |
| **F10** | **Editor de fusões e terminais**: Interface interativa de fusões, manobras, reservas e lote atômico para caixas CEO/CTO. | ✅ Concluído |
| **F11** | **Splitters, CTOs e atendimento**: Diagrama de splitters e matriz de ocupação de portas e clientes da CTO. | ✅ Concluído |
| **F12** | **Rastreamento óptico**: Visualizador de caminho óptico PON-ONU e ONU-PON com indicação de perdas acumuladas. | ✅ Concluído |
| **F13** | **Orçamento de potência**: Calculadora e detalhamento de atenuação por elemento da rota óptica. | ✅ Concluído |
| **F14** | **Medições e histórico**: Comparativo de potência prevista versus medida e simulações de engenharia com overrides. | ✅ Concluído |
| **F15** | **Fotos, documentos e histórico**: Galeria de fotos, upload mobile com câmera, validação MIME e AuditTimeline append-only. | ✅ Concluído |
| **F16** | **Importação e exportação**: Assistentes de importação/exportação CSV/KML/GeoJSON com preview de validação. | ⏳ Próxima |
| **F17** | **Relatórios e capacidade**: Relatórios de ocupação de CTOs, fibras livres/reservadas e inconsistências. | ⏳ Pendente |
| **F18** | **Hardening, acessibilidade e performance**: Validação de acessibilidade WCAG 2.2 AA, contraste, foco e bundle size. | ⏳ Pendente |
| **F19** | **Validação ponta a ponta**: Testes E2E cobrindo fluxos reais do usuário de ponta a ponta. | ⏳ Pendente |
| **F20** | **Documentação operacional**: Manual do operador e guia de estilo da interface. | ⏳ Pendente |

---

## 🛠️ Stack Tecnológica

### Backend
- **Linguagem & Runtime**: Python 3.12 gerenciado via `uv`
- **Framework Web**: FastAPI com Pydantic v2
- **Banco de Dados**: PostgreSQL 16 com extensão espacial PostGIS 3.4
- **ORM & Driver**: SQLAlchemy 2 (síncrono), GeoAlchemy2, `psycopg` v3 binary
- **Migrações**: Alembic com suporte a upgrade e downgrade bidirecional
- **Segurança**: Criptografia Argon2id, mitigação de enumeração, proteção CSRF e cabeçalhos de segurança
- **Contratos**: OpenAPI 3.1 determinístico e tipagens TypeScript (`contracts/`)
- **Qualidade de Código**: Ruff (linter e formatter) e Mypy (modo estrito)

### Frontend
- **Framework & Runtime**: Next.js 15 App Router, React 19, TypeScript estrito gerenciado via `pnpm`
- **Design System & Estilização**: Tailwind CSS, shadcn/ui, Lucide Icons
- **Estado Remoto & Formulários**: TanStack Query v5, TanStack Table v8, React Hook Form e Zod
- **Mapas & GIS**: MapLibre GL JS (renderização vetorial de camadas WebGL)
- **Qualidade & Testes**: Vitest, ESLint e checagem de tipos estrita (`tsc --noEmit`)

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

### 5. Iniciar o Servidor Backend de Desenvolvimento
```bash
uv run uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --reload
```

### 6. Iniciar o Servidor Frontend de Desenvolvimento
```bash
cd ../frontend
pnpm install
pnpm dev
# Aplicação acessível em http://localhost:3000
```

---

## 🧪 Testes e Qualidade

O projeto conta com suítes automatizadas de testes e checagem estrita de tipos para backend e frontend:

### Backend
```bash
cd backend

# Executar suíte completa de testes (125 testes)
uv run pytest

# Verificação de lint e formatação
uv run ruff check .
uv run ruff format --check .

# Verificação estrita de tipagem estática
uv run mypy .
```

### Frontend
```bash
cd frontend

# Executar suíte completa de testes (132 testes em 15 arquivos)
pnpm test

# Verificação estrita de tipos TypeScript
pnpm typecheck

# Verificação de lint
pnpm lint

# Build de produção otimizado (20 rotas estáticas geradas)
pnpm build
```

---

## 📂 Documentação e ADRs

- [`backend.md`](file:///home/bruno/projects/ftth_tiiv/backend.md): Especificação técnica e requisitos funcionais completos do backend (B01–B18).
- [`frontend.md`](file:///home/bruno/projects/ftth_tiiv/frontend.md): Especificação técnica e requisitos funcionais completos do frontend (F01–F20).
- [`docs/progress-backend.md`](file:///home/bruno/projects/ftth_tiiv/docs/progress-backend.md): Registro contínuo de entregas do backend, critérios de aceite atendidos e comandos executados.
- [`docs/progress-frontend.md`](file:///home/bruno/projects/ftth_tiiv/docs/progress-frontend.md): Registro contínuo de entregas do frontend, critérios de aceite atendidos e comandos executados.
- [`docs/adr/`](file:///home/bruno/projects/ftth_tiiv/docs/adr/): Architecture Decision Records formais:
  - `0001-stack-and-environment-decisions.md`
  - `0002-api-contracts-and-pydantic-v2.md`
  - `0003-authentication-sessions-and-rbac.md`
  - `0004-inventory-data-model-and-constraints.md`
  - `0005-gis-geodetic-lengths-and-map-features.md`
  - `0006-cables-fibers-and-segment-splitting.md`
