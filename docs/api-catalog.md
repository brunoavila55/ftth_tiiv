# Catálogo da API RESTful (FTTH Manager)

Este documento é a referência canônica dos endpoints, protocolos de segurança, contratos de concorrência e padrões de integração HTTP da API do **FTTH Manager** (`v1`).

---

## 1. Convenções Globais de Integração

- **Prefixo de Roteamento**: `/api/v1`
- **Formato de Carga Útil**: `application/json` (ou `multipart/form-data` para uploads de anexos).
- **Tratamento de Erros**: RFC 7807 Problem Details (`Content-Type: application/problem+json`).
- **Rastreabilidade Distribuída**: Cabeçalho `X-Request-ID` propagado em todas as respostas e logs estruturados.
- **Convenção de Unidades**: Sufixos explícitos em todas as grandezas (`*_m`, `*_db`, `*_dbm`, `wavelength_nm`, `_ms`, `_bytes`).

---

## 2. Autenticação, Sessões e RBAC

### 2.1. Sessões Seguras e CSRF
A API adota sessões baseadas em cookies criptograficamente opacos, imunes a ataques XSS quando configurados com `HttpOnly`:
- **Cookie de Sessão**: `ftth_session_id` (`HttpOnly`, `SameSite=Lax`, `Path=/api/v1`).
- **Proteção CSRF**: Cookie duplo com `ftth_csrf_token` e exigência de envio do cabeçalho `X-CSRF-Token` em todos os métodos mutantes (`POST`, `PUT`, `PATCH`, `DELETE`).
- **Validação de Origem**: Verificação em tempo constante do cabeçalho `Origin` contra o host configurado da aplicação.
- **Expiração**: 7 dias absolutos e expiração por inatividade após 24 horas.
- **Rate Limiting**: Máximo de 5 tentativas consecutivas de login por IP/usuário a cada 15 minutos (persistido no PostgreSQL).

### 2.2. Matriz de Perfis e Permissões (RBAC)

| Permissão | Admin | Engineer | Technician | Viewer | Descrição |
|:---|:---:|:---:|:---:|:---:|:---|
| `network:read` | ✅ | ✅ | ✅ | ✅ | Consulta inventário físico, cabos, rotas e GIS |
| `network:write` | ✅ | ✅ | ❌ | ❌ | Criação e alteração de estruturas, cabos e portas |
| `connectivity:read` | ✅ | ✅ | ✅ | ✅ | Leitura de fusões, terminadores e splitters |
| `connectivity:write` | ✅ | ✅ | ✅ | ❌ | Execução e desativação de fusões e conexões |
| `optical:read` | ✅ | ✅ | ✅ | ✅ | Cálculo de orçamento óptico e rastreamento de atenuação |
| `optical:write` | ✅ | ✅ | ❌ | ❌ | Criação e alteração de perfis ópticos de tecnologia |
| `measurements:read` | ✅ | ✅ | ✅ | ✅ | Leitura de medições de campo |
| `measurements:write` | ✅ | ✅ | ✅ | ❌ | Registro de potências ópticas aferidas |
| `customers:read` | ✅ | ✅ | ✅ | ✅ | Consulta de dados cadastrais e vínculos de clientes |
| `customers:write` | ✅ | ✅ | ❌ | ❌ | Cadastro e alteração de clientes e atendimentos |
| `attachments:read` | ✅ | ✅ | ✅ | ✅ | Download de fotos e documentos técnicos |
| `attachments:write` | ✅ | ✅ | ✅ | ❌ | Upload de fotos de caixas e comprovantes |
| `reports:read` | ✅ | ✅ | ❌ | ❌ | Acesso aos relatórios gerenciais e inconsistências |
| `jobs:manage` | ✅ | ✅ | ❌ | ❌ | Disparo de exportações e importações massivas |
| `users:manage` | ✅ | ❌ | ❌ | ❌ | Gestão de operadores, troca de perfis e senhas |
| `system:manage` | ✅ | ❌ | ❌ | ❌ | Backups, restaurações e parametrização do sistema |

---

## 3. Concorrência Otimista e Controle de Versão

Para evitar sobrescritas cegas (*lost update problem*), todas as mutações em entidades de inventário e conectividade exigem validação de versão via cabeçalho HTTP:

- **Cabeçalho de Requisição**: `If-Match: "<version>"` (ou número inteiro da versão).
- **Sem precondição**: Retorna `428 Precondition Required`.
- **Versão defasada**: Retorna `412 Precondition Failed`.
- **Cabeçalho de Resposta**: `ETag: "<version>"`.

### Lotes de Fusão e Travessia Óptica
Em operações topológicas complexas (ex: fechamento de caixa de emenda ou análise de impacto), a requisição exige o campo `expected_topology_revision`. Caso a revisão do grafo tenha sido incrementada por outro operador, a API recusa com `409 Conflict` (`code: topology_revision_conflict`), preservando o rascunho de trabalho do operador no frontend.

---

## 4. Paginação e Filtros

Todos os endpoints de listagem aplicam paginação padronizada com limites estritos para proteção contra esgotamento de memória:
- `page`: Número da página (início em 1, default 1).
- `page_size`: Quantidade por página (mínimo 1, default 20, máximo restrito a 200).
- Envelope de resposta:
```json
{
  "items": [...],
  "total": 1420,
  "page": 1,
  "page_size": 20,
  "total_pages": 71
}
```

---

## 5. Formato de Erros (RFC 7807)

Erros HTTP utilizam a estrutura padronizada:
```json
{
  "type": "about:blank",
  "title": "Conflito de revisão topológica",
  "status": 409,
  "detail": "A revisão topológica esperada (14) diverge da revisão atual (15). O editor de fusão deve ser recarregado.",
  "code": "topology_revision_conflict",
  "request_id": "c7a8b9e1-2f3a-4b5c-6d7e-8f9a0b1c2d3e",
  "errors": null
}
```

---

## 6. Catálogo Resumido de Rotas por Família

### 6.1. Autenticação (`/auth`)
- `GET /api/v1/auth/csrf`: Obtém token CSRF criptograficamente assinado.
- `POST /api/v1/auth/login`: Autentica com e-mail/senha, inicia sessão e seta cookies protegidos.
- `POST /api/v1/auth/logout`: Revoga a sessão ativa no banco e limpa cookies.
- `GET /api/v1/auth/me`: Retorna os dados cadastrais e permissões do usuário logado.
- `POST /api/v1/auth/change-password`: Altera a própria senha exigindo a senha atual.

### 6.2. Gestão de Usuários (`/users`)
- `GET /api/v1/users`: Lista operadores com paginação e busca textual.
- `POST /api/v1/users`: Cria novo operador (requer `users:manage`).
- `GET /api/v1/users/{id}`: Detalha operador por ID.
- `PATCH /api/v1/users/{id}`: Atualiza perfil/status (com `If-Match` e proteção do último admin).

### 6.3. Inventário Físico (`/sites`, `/structures`, `/devices`, `/ports`)
- `GET /api/v1/sites`: Lista POPs e centrais de distribuição com paginação e busca.
- `POST /api/v1/sites`: Cadastra novo site com coordenadas WGS84.
- `GET /api/v1/structures`: Lista caixas de emenda (CEO), caixas de atendimento (CTO) e postes.
- `POST /api/v1/structures`: Cadastra estrutura física pontual.
- `GET /api/v1/devices`: Lista OLTs, ONUs, switches e DIOs.
- `POST /api/v1/devices`: Cadastra equipamento físico com validação da regra de localização exclusiva.
- `GET /api/v1/ports`: Lista portas físicas com filtros por `device_id` ou `structure_id`.
- `POST /api/v1/ports`: Provisiona porta óptica com regra de proprietário exclusivo.

### 6.4. Cabos e Fibras (`/cables`, `/cable-segments`)
- `GET /api/v1/cables`: Lista modelos de cabos ópticos e padrões de cores industriais.
- `POST /api/v1/cables`: Cadastra novo cabo com tubos loose e contagem de fibras.
- `GET /api/v1/cable-segments`: Lista trechos instalados de cabos.
- `POST /api/v1/cable-segments`: Cria trecho de cabo entre duas estruturas com geometria LineString.
- `POST /api/v1/cable-segments/{id}/split`: Divide trecho de cabo pela inserção de uma nova estrutura intermediária (CEO/CTO), recalculando distâncias e preservando continuidades.

### 6.5. Conectividade e Grafo (`/connectivity`, `/terminals`, `/splitters`, `/topology`)
- `GET /api/v1/connectivity/structures/{structure_id}`: Retorna toda a malha de terminais, fusões e splitters de uma estrutura física.
- `POST /api/v1/connectivity/batch`: Aplica lote atômico de criação/remoção de fusões com validação de `expected_topology_revision`.
- `POST /api/v1/topology/trace`: Executa travessia óptica determinística (downstream ou upstream) com retorno de perda acumulada e nós intermediários.
- `POST /api/v1/topology/impact`: Simulação virtual de corte de cabos, retornando clientes, CTOs e portas PON atingidas sem mutação no banco operacional.

### 6.6. Engenharia Óptica e Medições (`/optical`, `/measurements`)
- `GET /api/v1/optical/profiles`: Lista perfis de tecnologia óptica (GPON, XGS-PON, etc.).
- `POST /api/v1/optical/profiles`: Cadastra limites físicos de tecnologia.
- `POST /api/v1/optical/budgets`: Calcula o orçamento óptico teórico ponta a ponta com margem de engenharia e avaliação de conformidade (`pass`, `low_margin`, `fail`, `overload`).
- `POST /api/v1/optical/simulations`: Simulação de cenário what-if com substituição virtual de comprimentos ou razões de splitters.
- `GET /api/v1/measurements`: Lista medições ópticas de campo com filtros por data, atendimento e terminal.
- `POST /api/v1/measurements`: Registra medição de potência óptica com cálculo automático de perda excessiva.

### 6.7. Assinantes (`/customers`, `/customers/service-links`)
- `GET /api/v1/customers`: Lista clientes atendidos pelo provedor.
- `POST /api/v1/customers`: Cadastra novo cliente.
- `POST /api/v1/customers/service-links`: Ativa vínculo entre Cliente, Porta da CTO e ONU, com validação de exclusividade operacional.

### 6.8. Mapa Operacional e GIS (`/gis`)
- `GET /api/v1/gis/features`: Retorna FeatureCollection GeoJSON filtrada por Bounding Box (`bbox=min_lon,min_lat,max_lon,max_lat`) com truncamento em 500 feições e cabeçalhos de controle.
- `GET /api/v1/gis/revision`: Retorna a revisão monotônica atual da topologia para sincronização de cache de mapa.

### 6.9. Relatórios, Métricas e Jobs (`/reports`, `/dashboard`, `/metrics`, `/jobs`)
- `GET /api/v1/dashboard/summary`: Resumo operacional de inventário, ocupação de portas e alertas de degradação.
- `GET /api/v1/reports/cto-occupancy`: Relatório de capacidade e portas livres/ocupadas por CTO.
- `GET /api/v1/reports/cable-capacity`: Relatório de aproveitamento e ocupação de fibras por cabo.
- `GET /api/v1/reports/inconsistencies`: Detecção de inconsistências topológicas (pontas abertas, atenuações fora do padrão).
- `GET /api/v1/metrics`: Métricas de desempenho em formato Prometheus (`text/plain`) e JSON estruturado.
- `POST /api/v1/exports`: Enfileira exportação em segundo plano da rede (GeoJSON ou CSV).
- `GET /api/v1/jobs/{job_id}`: Consulta status e resultado de job assíncrono.
