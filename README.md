# FTTH Manager

Sistema open source e self-hosted para gestão técnica e operacional de redes de fibra óptica (FTTH), cobrindo inventário de infraestrutura, GIS geodésico, conectividade fibra a fibra, splitters, clientes, rastreamento óptico, cálculo de potência e auditoria completa.

---

## 🚀 Status do Projeto (Roadmap Backend B01–B18)

O backend foi construído seguindo as etapas de uma especificação inicial (`backend.md`, removida após a conclusão da auditoria de segurança; histórico no git).

| Etapa | Descrição | Status |
|---|---|:---:|
| **B01** | **Fundação reproduzível**: Configurações tipadas, logging JSON sanitizado, RFC 7807 Problem Details, healthchecks (`/health/live`, `/health/ready`), Compose e isolamento de domínio. | ✅ Concluído |
| **B02** | **Contrato e schemas**: Schemas Pydantic v2, paginação estrita, enums, garantia automatizada de ausência de stubs 501, exportador determinístico para `contracts/openapi.json` e tipos TypeScript em `contracts/api-types.d.ts`. | ✅ Concluído |
| **B03** | **Sessões, usuários e permissões**: Hashing Argon2id, mitigação de enumeração de timing, CSRF com double submit cookie, rate limiting distribuído no PostgreSQL, sessões com expiração absoluta e inatividade, RBAC granular e CLI de bootstrap de admin. | ✅ Concluído |
| **B04** | **Inventário e migrações**: Sites, Estruturas (Postes, Caixas CEO/CTO, POPs), Dispositivos (OLT, Switch, DIO), Portas com regras de propriedade estrita, Perfis Ópticos com check constraints de limites físicos e integridade referencial. | ✅ Concluído |
| **B05** | **GIS e comprimentos confiáveis**: SRID 4326, GeoJSON, validação estrita de geometrias e bounding box, comprimentos geodésicos em metros via PostGIS geography, regra óptica contra dupla contagem de reserva, tolerância de rotas (5m), índice GiST espacial e controle monotônico de `topology_revision`. | ✅ Concluído |
| **B06** | **Cabos, tubos, fibras e segmentação**: Cabos multitubo e monotubo com agrupamento lógico, catálogos flexíveis de cores (ABNT NBR 14106, TIA-598, DIN), geração de $2N$ terminais normalizados por trecho, divisão atômica de segmento em estrutura intermediária com preservação de continuidade óptica para fibras passantes (0.0 dB) e conexões externas pré-existentes. | ✅ Concluído |
| **B07** | **Motor de conectividade e fusões**: Modelos de banco de dados, migração `0006_connectivity_engine`, `connection_endpoints` com índice único parcial no Postgres, reservas de terminais, arestas internas de DIO sem fan-out, auditoria append-only, serviço com bloqueio determinístico anti-deadlock, endpoints `/connectivity` e `/connectivity/batch` (editor de fusão) e testes de integração com 100% de cobertura. | ✅ Concluído |
| **B08** | **Splitters, CTOs e atendimento**: Splitters balanceados e desbalanceados 1:N, mapeamento de saídas, ocupação em tempo real, cadastro de clientes e vínculos de atendimento com drop (migração 0007). | ✅ Concluído |
| **B09** | **Rastreamento óptico**: Motor determinístico de travessia PON→ONU e ONU→PON no grafo de rede, sem corte em passagens diretas, ramificação correta em splitters e detecção de ciclos/pontas abertas. | ✅ Concluído |
| **B10** | **Cálculo óptico independente**: Módulo puro de cálculo de atenuação acumulada, perdas de inserção, conectores acoplados, margem de engenharia, limiares de sensibilidade e sobrecarga (caso canônico -20,68 dBm). | ✅ Concluído |
| **B11** | **Medições e comparação com previsão**: Registro de medições manuais (migração 0008), snapshots de topologia, cálculo canônico de perda excedente (`previsto - medido = +6,1 dB`), tolerâncias e concorrência otimista. | ✅ Concluído |
| **B12** | **Impacto de rompimento e simulações**: Simulações com overrides em memória (perda pontual, comprimento, razão de splitter), cálculo de deltas e análise de impacto virtual de rompimento de cabos (`POST /api/v1/topology/impact`). | ✅ Concluído |
| **B13** | **Fotos, anexos e auditoria**: Anexos privados em volume persistente (migração 0009), validação de magic bytes (JPEG/PNG/WebP/PDF), sanitização de path traversal, thumbnails seguros, auditoria append-only com rollback atômico e reconciliação de órfãos. | ✅ Concluído |
| **B14** | **Importação e exportação confiáveis**: Importadores GeoJSON/KML/CSV com prévia/commit idempotente, mitigação de formula injection e exportações com jobs em background no PostgreSQL. | ✅ Concluído |
| **B15** | **Busca global, painel e relatórios**: Métricas consolidadas, buckets reais de ocupação de CTOs, busca RBAC com proteção LGPD e relatórios paginados de CTOs, cabos e inconsistências. | ✅ Concluído |
| **B16** | **Desempenho e observabilidade**: Datasets sintéticos de alta escala (10k+ estruturas, 100k+ fibras), benchmarks de latência p95 < 12ms e métricas estruturadas Prometheus/JSON sem inanição. | ✅ Concluído |
| **B17** | **Implantação, backup e manutenção**: Docker Compose multi-serviço de produção com Caddy, banco PostGIS em rede privada, rotinas de backup atômico com manifesto SHA256 e Restore Drill 100% aprovado. | ✅ Concluído |
| **B18** | **Auditoria final e entrega open source**: Teste transversal de ciclo completo (10 etapas), seed CLI determinístico, pipeline de CI no GitHub Actions, matriz de rastreabilidade e governança. | ✅ Concluído |

---

## 🎨 Status do Projeto (Roadmap Frontend F01–F20)

O frontend foi construído seguindo as etapas de uma especificação inicial (`frontend.md`, removida após a conclusão da auditoria de segurança; histórico no git).

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
| **F16** | **Importação e exportação**: Assistentes de importação/exportação CSV/KML/GeoJSON com preview de validação e isolamento. | ✅ Concluído |
| **F17** | **Relatórios e capacidade**: Relatórios de ocupação de CTOs, balanço de fibras em cabos e diagnóstico de inconsistências técnicas. | ✅ Concluído |
| **F18** | **Hardening, acessibilidade e performance**: Acessibilidade WCAG 2.2 AA, alvos de toque $\ge 44 \times 44$ px, alto contraste e performance móvel. | ✅ Concluído |
| **F19** | **Testes integrados e qualidade**: Suíte de 183 testes Vitest sem regressões em todos os 24 arquivos de teste. | ✅ Concluído |
| **F20** | **Entrega e revisão de produto**: Validação funcional contínua e ausência de dead-ends ou mocks estáticos. | ✅ Concluído |

---

## 🛠️ Stack Tecnológica

### Backend
- **Linguagem & Runtime**: Python 3.12 gerenciado via `uv`
- **Framework Web**: FastAPI com Pydantic v2
- **Banco de Dados**: PostgreSQL 16 com extensão espacial PostGIS 3.4
- **ORM & Driver**: SQLAlchemy 2 (síncrono), GeoAlchemy2, `psycopg` v3 binary
- **Migrações**: Alembic com controle de versão e integridade
- **Segurança**: Criptografia Argon2id, mitigação de enumeração, proteção CSRF e cabeçalhos de segurança
- **Contratos**: OpenAPI 3.1 determinístico e tipagens TypeScript sincronizadas (`contracts/`)
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
6. **Contratos Honestos**: Ausência de mocks ocultos; todos os endpoints implementados executam lógica real no banco de dados e no motor óptico.

---

## 🚀 Como Executar Localmente

### 1. Pré-requisitos
- Docker ou Podman com Compose
- Python 3.12 e [`uv`](https://github.com/astral-sh/uv)
- Node.js 20 e [`pnpm`](https://pnpm.io/)

### 2. Iniciar o Banco de Dados PostGIS
```bash
docker compose up -d db
```

### 3. Configurar o Ambiente e Migrações
```bash
cd backend
uv sync
uv run alembic upgrade head
```

### 4. Provisionar o Cenário de Demonstração (Opt-in)
```bash
uv run python scripts/seed_demo.py --clean
```
A senha do admin de demonstração (`admin@provedor.com.br`) é gerada aleatoriamente e **exibida uma única vez** na saída. O seed (assim como `generate_synthetic_load.py` e `benchmark_endpoints.py`) aborta com código 2, sem tocar no banco, se `ENVIRONMENT=production` ou se o banco não for local (este último só com `--i-know-this-is-not-prod`).

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

### Backend (564 testes: 563 aprovados e 1 pulado conforme disponibilidade de `pg_dump`)
```bash
cd backend

# Executar suíte completa de testes
uv run pytest

# Verificação de lint e formatação
uv run ruff check .
uv run ruff format --check .

# Verificação estrita de tipagem estática
uv run mypy app
```

### Frontend (183 testes aprovados em 24 arquivos)
```bash
cd frontend

# Executar suíte completa de testes
pnpm test

# Verificação estrita de tipos TypeScript
pnpm typecheck

# Verificação de lint
pnpm lint

# Build de produção otimizado
pnpm build
```

---

## 📦 Implantação em Produção com Docker Compose

A aplicação conta com arquitetura de contêineres completa em `compose.yaml`:
```bash
# 1. Configurar variáveis de ambiente de produção
cp compose.override.yaml.example compose.override.yaml # se necessário

# 2. Subir a stack completa (Caddy + Frontend + Backend + Worker + PostGIS)
docker compose up -d
```
Consulte o guia completo em [`docs/runbooks/deployment-and-maintenance.md`](docs/runbooks/deployment-and-maintenance.md).

---

## 📂 Documentação e Governança

- [`docs/entity-relationship-model.md`](docs/entity-relationship-model.md): Modelo entidade-relacionamento e semântica do grafo óptico.
- [`docs/api-catalog.md`](docs/api-catalog.md): Catálogo completo de endpoints, convenções de sessão, CSRF e RBAC.
- [`docs/requirement-test-matrix.md`](docs/requirement-test-matrix.md): Matriz de rastreabilidade ligando requisitos a testes automatizados.
- [`docs/audit-b18.md`](docs/audit-b18.md): Relatório de auditoria formal da fase B18 com checklist PASS/FAIL.
- [`docs/benchmark-b16.md`](docs/benchmark-b16.md): Resultados dos benchmarks de alta escala (10k nós e 100k fibras).
- [`docs/runbooks/deployment-and-maintenance.md`](docs/runbooks/deployment-and-maintenance.md): Runbook operacional para produção, backup e restore drill.
- [`CONTRIBUTING.md`](CONTRIBUTING.md): Guia para contribuidores do projeto open source.
- [`SECURITY.md`](SECURITY.md): Política de segurança, reporte responsável e controles de proteção.
- [`docs/adr/`](docs/adr/): Architecture Decision Records (ADRs 0001 a 0007).

---

## 📄 Licença

Recomendada a licença **AGPL-3.0 (GNU Affero General Public License v3)** para manter a infraestrutura livre e comunitária mesmo quando operada como serviço de nuvem (SaaS). Alternativamente, consulte as recomendações em [`docs/audit-b18.md`](docs/audit-b18.md).
