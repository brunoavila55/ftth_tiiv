# ADR 0001: Fundação da Stack, Concorrência e Isolamento de Domínio

- **Status**: Aceito
- **Data**: 2026-09-17
- **Autores**: Equipe de Engenharia FTTH Manager

## Contexto

O **FTTH Manager** é uma aplicação open source, self-hosted, voltada para a documentação física e óptica de operações FTTH. O sistema lida com inventário de ativos, geolocalização (GIS), conexões fibra a fibra com integridade estrita, cálculo óptico de perdas e potência, e rastreamento de caminhos PON.

A especificação `backend.md` estabelece os requisitos arquiteturais:
1. Monólito modular com domínio óptico independente de HTTP e persistência.
2. Stack Python com FastAPI, Pydantic v2, SQLAlchemy 2 síncrono com driver `psycopg` (v3), GeoAlchemy2 e Alembic.
3. PostgreSQL 16 com extensão PostGIS 3.4.
4. Concorrência controlada por versão monotônica (`version`) nos recursos e precondição `If-Match: "<version>"`.
5. Gestão de pacotes reproduzível usando `uv` e arquivo de lock (`uv.lock`).
6. Trilha de auditoria append-only e controle de revisão topológica (`topology_revision`).

## Decisões

### 1. Linguagem e Gerenciamento de Dependências
- **Python 3.12**: Versão estável com suporte completo a bibliotecas GIS (GEOS/GDAL via Shapely/GeoAlchemy2) e drivers síncronos modernos.
- **Astral uv**: Utilizado para resolução ultrarrápida e determinística de dependências com `pyproject.toml` e `uv.lock`. Nenhuma instalação fora do lockfile é permitida em CI/CD ou produção.

### 2. SQLAlchemy Síncrono com psycopg (v3)
- Adotamos SQLAlchemy 2.0 com `psycopg` (v3) no modelo síncrono.
- Os endpoints FastAPI executam operações de banco em pool de threads worker gerenciado pelo Starlette/FastAPI (rotas `def` normais) ou transações explícitas por caso de uso, evitando o bloqueio do event loop assíncrono.
- Desacoplamento: nenhum módulo de domínio importa conexões ou sessões de banco no nível de módulo.

### 3. Modelo de Tratamento de Erros e Problem Details
- Todos os erros estruturados seguem o padrão RFC 7807 (`application/problem+json`).
- Respostas incluem: `type`, `title`, `status`, `detail`, `code`, `request_id` e lista de `errors` para erros de validação (422).
- Códigos HTTP padronizados para concorrência:
  - `428 Precondition Required`: ausência do cabeçalho `If-Match`.
  - `412 Precondition Failed`: versão fornecida no `If-Match` diverge da versão atual do recurso.
  - `409 Conflict`: violação de regra de negócio ou conflito de topologia.

### 4. Isolamento e Testabilidade
- Nenhuma dependência com banco no momento de importação (`no database on import`).
- Testes unitários funcionam independentemente de um banco ativo.
- Endpoints de health:
  - `/health/live`: verificação de liveness imediata (sem tocar no banco).
  - `/health/ready`: verificação de readiness profunda (valida pool de conexões e migrations aplicadas sem expor credenciais).

## Consequências

- **Positivas**:
  - Determinismo e reprodutibilidade imediata do ambiente com `uv`.
  - Clareza nas transações e eliminação de deadlocks ou corrupção de estado graças à concorrência explícita.
  - Facilidade de diagnóstico de falhas em produção através do rastreamento unificado via `X-Request-ID` e logs JSON sanitizados.
- **Limitações / Mitigações**:
  - Exige rigor na definição de rotas e casos de uso para que transações não vazem entre chamadas.
  - Exige que o container ou serviço PostGIS esteja disponível para testes de integração espacial.
