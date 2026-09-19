# Runbook de Implantação, Backup, Manutenção e Recuperação (B17)

Este documento estabelece as diretrizes e procedimentos operacionais padronizados para o **FTTH Manager** em conformidade com o marco **B17**.

---

## 1. Arquitetura de Implantação e Topologia Docker Compose

A pilha de produção do FTTH Manager é orquestrada via Docker Compose com separação estrita de redes, privilégios mínimos (não-root) e volumes persistentes:

| Serviço | Imagem / Base | Rede | Porta Host Exposta | Função |
|---|---|---|---|---|
| `db` | `docker.io/postgis/postgis:16-3.4` | `internal` | Nenhuma (privada) | Banco relacional e espacial PostGIS |
| `migrate` | `backend:runner` (Python 3.12 non-root) | `internal` | Nenhuma | Execução atômica e única das migrações Alembic (`alembic upgrade head`) antes de subir o backend/workers |
| `backend` | `backend:runner` (Python 3.12 non-root) | `internal`, `public` | Nenhuma (via Caddy) | API FastAPI, endpoints REST, telemetria e documentação |
| `worker` | `backend:runner` (Python 3.12 non-root) | `internal` | Nenhuma | Consumo concorrente de jobs de importação/exportação via `SKIP LOCKED` |
| `frontend` | `frontend:runner` (Node 22 Alpine non-root) | `public` | Nenhuma (via Caddy) | Interface Web Next.js App Router standalone |
| `caddy` | `docker.io/caddy:2.8.4-alpine` | `public` | `80:80`, `443:443` | Reverse proxy com compressão, terminação TLS opcional (`SITE_ADDRESS`), HSTS e bloqueio de `/metrics` (o CSP com nonce vem do frontend) |

### Invariantes de Infraestrutura:
1. **Rede Privada do Banco**: A porta `5432` do PostgreSQL **não** é publicada no host por padrão. Somente containers na rede `internal` têm acesso direto. Para desenvolvimento local, utilize `compose.override.yaml` (baseado em `compose.override.yaml.example`).
2. **Migração Sequencial Única**: O serviço `migrate` roda como tarefa pontual (`restart: "no"`) com bloqueio transacional do Alembic, impedindo corrida concorrente de migrações em réplicas de workers ou da API.
3. **Usuários Não-Root**: Os containers da API, Worker (`ftthuser`, UID 1000) e Web (`nextjs`, UID 1001) rodam com privilégios reduzidos.
4. **Volumes Persistentes**:
   - `pgdata`: Dados do PostgreSQL.
   - `backend_storage`: Fotos e documentos enviados do campo.
   - `caddy_data` / `caddy_config`: Certificados TLS e estado do proxy.

---

## 2. Instalação Limpa (Fresh Install)

### 2.1 Pré-requisitos
- Docker Engine 24+ e Docker Compose v2+
- Mínimo de 2 vCPU e 4 GB de RAM
- Portas de entrada 80/TCP e 443/TCP liberadas no firewall

### 2.2 Configuração Inicial de Variáveis
Copie o modelo de variáveis de ambiente:
```bash
cp .env.example .env
```

Edite o arquivo `.env` gerando credenciais criptográficas fortes:
```bash
# Gerar chave de sessão (mínimo 32 caracteres)
openssl rand -hex 32

# Gerar segredo CSRF
openssl rand -hex 32

# Gerar token para endpoint de métricas Prometheus (METRICS_SECRET_TOKEN; mínimo de 32 caracteres)
openssl rand -hex 16

# Senha do PostgreSQL (POSTGRES_PASSWORD) — sem valor padrão
openssl rand -base64 24
```
> [!IMPORTANT]
> **Sem credenciais padrão**: com `ENVIRONMENT=production` o backend **recusa subir** (erro de validação na inicialização, sem ecoar os valores) se `SECRET_KEY`, `CSRF_SECRET` ou `METRICS_SECRET_TOKEN` forem valores de exemplo/padrão, tiverem menos de 32 caracteres ou baixa variedade de caracteres, ou se a senha do `DATABASE_URL` for a de exemplo. O `compose.yaml` também exige `SECRET_KEY`, `CSRF_SECRET`, `METRICS_SECRET_TOKEN` e `POSTGRES_PASSWORD` (`${VAR:?...}`): sem elas o `docker compose up` falha antes de subir. Os placeholders do `.env.example` (`change-me-...`) são rejeitados de propósito.
>
> **Métricas**: o nome canônico da variável é `METRICS_SECRET_TOKEN` (aceito pelo backend e injetado pelo compose). O endpoint `/api/v1/metrics` aceita o cabeçalho `X-Metrics-Token` (comparação em tempo constante) ou sessão de administrador; `METRICS_ENABLED=false` o desliga (404). Ele **não** é publicado pelo Caddy (responde 404 externamente); o Prometheus o acessa pela rede interna.

### 2.3 Inicialização da Pilha
```bash
docker compose up -d --build
```
Acompanhe os healthchecks até que todos os serviços estejam saudáveis:
```bash
docker compose ps
```

### 2.4 Bootstrap do Primeiro Administrador
O bootstrap do administrador exige credenciais fornecidas explicitamente pelo operador, sem senhas predefinidas ou inseguras:
```bash
docker compose exec backend python -m app.cli.bootstrap_admin \
  --email "admin@provedor.com.br" \
  --name "Administrador Geral"
# O terminal solicitará a senha de forma interativa e oculta (mínimo 8 caracteres)
```

---

## 3. Procedimento Operacional de Backup Consistente

O FTTH Manager implementa backup atômico e determinístico contemplando tanto o banco relacional/espacial quanto os arquivos de mídia armazenados.

### 3.1 Execução Manual
```bash
# Via script bash
./scripts/backup.sh

# Ou diretamente no contêiner backend
docker compose exec backend python scripts/backup.py --target-dir /app/storage/backups --retention-count 7
```

### 3.2 Anatomia do Arquivo de Backup (`.tar.gz`)
Cada arquivo gerado (ex: `ftth_backup_20260918_142030.tar.gz`) contém:
- `manifest.json`: Manifesto assinado contendo ID do backup, timestamp UTC, versão de schema Alembic, revisão da topologia óptica (`topology_revision`), quantidade de anexos e dicionário de hashes SHA256 para verificação de integridade de cada arquivo.
- `database.dump`: Dump binário nativo de alta performance das tabelas relacionais e espaciais.
- `attachments/`: Diretório contendo todas as fotos e documentos técnicos armazenados.

### 3.3 Política de Retenção
Por padrão, o parâmetro `--retention-count 7` mantém os 7 backups mais recentes, expurgando de forma segura arquivos legados para evitar exaustão de disco.

---

## 4. Teste de Restauração em Ambiente Isolado (Restore Drill)

> [!NOTE]
> Conforme exigência de aceite de **B17**, um backup sem teste de restauração comprovado não é considerado válido. O script automatizado `scripts/restore_drill.py` executa todo o ciclo de validação fim-a-fim.

### 4.1 O que o Restore Drill Valida
1. Criação de base de teste isolada e injeção de cenário com POP, OLT, cabos, fusões, CTO e uma foto real em formato JPEG com assinatura de magic bytes (`\xFF\xD8\xFF`).
2. Execução do backup consistente com geração de manifesto criptográfico.
3. Criação de um segundo banco isolado e diretório de storage limpo.
4. Restauração do backup no ambiente de teste com conferência de checksums SHA256.
5. Validação pós-restauração:
   - Rastreamento óptico (`trace_optical_path`) idêntico ao original e com mesma revisão topológica.
   - Restauração byte-a-byte do anexo fotográfico mantendo SHA256 e magic bytes JPEG intactos.
   - Contagem exata de inventário (sites e estruturas).

### 4.2 Executando o Drill
```bash
uv run --directory backend python scripts/restore_drill.py
```
Saída esperada:
```text
================================================================================
 RESTORE DRILL B17: SUCESSO ABSOLUTO (PASS 100%)
================================================================================
```

---

## 5. Restauração em Produção e Recuperação de Desastres

Para restaurar um backup existente:
```bash
# 1. Parar serviços que realizam mutação
docker compose stop backend worker

# 2. Executar restauração
docker compose exec -T db ... # ou via script:
./scripts/restore.sh ./backups/ftth_backup_YYYYMMDD_HHMMSS.tar.gz

# 3. Reiniciar serviços
docker compose start backend worker
```

---

## 6. Estratégia de Migração: Roll-Forward vs. Downgrade

> [!WARNING]
> O FTTH Manager **não** suporta downgrade automático para migrações destrutivas (remoção de colunas ou tabelas, truncamento de dados espaciais). 
> Em caso de falha de release:
> 1. Restaure o backup consistente imediatamente anterior à atualização.
> 2. Implemente a correção via **Roll-Forward** (nova migração corretiva `00XX_fix_...`).

---

## 7. Rotação de Segredos Operacionais

1. **SECRET_KEY**:
   - Atualize `SECRET_KEY` no `.env`.
   - Reinicie `backend` e `worker`.
   - *Impacto*: hoje a `SECRET_KEY` é apenas validada (a sessão é um token opaco em banco); ela passará a assinar o CSRF/sessões na etapa R09 da auditoria, quando a rotação invalidará esses tokens.
2. **Senha do Banco (`POSTGRES_PASSWORD`)**:
   - Altere a senha no PostgreSQL: `ALTER USER ftth_user WITH PASSWORD 'nova_senha';`
   - Atualize `POSTGRES_PASSWORD` e `DATABASE_URL` no `.env`.
   - Reinicie os containers.
3. **METRICS_SECRET_TOKEN**:
   - Atualize `METRICS_SECRET_TOKEN` no `.env`.
   - Reinicie `backend`. Atualize o scraper Prometheus correspondente.

---

## 8. Servidor de Tiles Cartográficos e Requisitos de Rede

### 8.1 Provedores de Tiles Suportados
O mapa operacional do FTTH Manager utiliza MapLibre GL JS e requer acesso a um servidor de tiles raster ou vetoriais:
- **Padrão OpenStreetMap**: `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`
- **CartoDB Positron / Dark**: `https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png`
- **Servidor Próprio / Offline (TileServer-GL)**: Para operações em rede fechada ou sem internet, configure o endpoint interno via configuração da organização (`/settings`).

### 8.2 Requisitos de Firewall (Egress / Ingress)
- **Ingress**: Portas `80/TCP` e `443/TCP` para acesso dos técnicos e administradores ao Caddy.
- **Egress**:
  - Acesso HTTPS (`443/TCP`) aos domínios de tiles configurados (`*.tile.openstreetmap.org`, `*.basemaps.cartocdn.com`).
  - Nenhuma outra porta de saída é requerida para a operação segura do sistema.

---

## 9. Limites de entrada e rate limit

- **Tamanho de corpo (Caddy)**: `/api/v1/imports/preview` e `/api/v1/attachments` aceitam até 25 MB (maior arquivo permitido + overhead do multipart); demais rotas `/api/*` até 2 MB. O backend aplica o limite exato por rota: anexos `MAX_UPLOAD_SIZE_BYTES` (10 MB) e importações `MAX_IMPORT_SIZE_BYTES` (20 MB), respondendo `413`.
- **Tetos de schema**: campos numéricos, textos e listas dos corpos JSON têm limites (ex.: `fiber_count ≤ 1728`, `tube_count ≤ 144`, listas ≤ 500, `notes ≤ 5000`); valores acima retornam `422`. Um teste (`tests/unit/test_request_caps.py`) impede rotas novas sem teto.
- **Imagens**: anexos de imagem acima de `MAX_IMAGE_PIXELS` (25 Mpx) ou com cabeçalho inválido/corrompido retornam `422` sem decodificar a imagem (proteção contra bombas de descompressão); o upload roda no threadpool e o corpo é cortado em `MAX_UPLOAD_SIZE_BYTES` (`413`).
- **Rate limit** (`429` + `Retry-After`, janela de 1 minuto, por usuário autenticado): `RATE_LIMIT_COMPUTE_PER_MINUTE` (trace/impact/budgets/simulations, 30), `RATE_LIMIT_SEARCH_PER_MINUTE` (60), `RATE_LIMIT_UPLOAD_PER_MINUTE` (anexos e prévia de importação, 20), `RATE_LIMIT_EXPORT_PER_MINUTE` (10); `RATE_LIMIT_ENABLED=false` desliga.
  > [!WARNING]
  > O limitador é **em memória, por processo**. Com mais de um worker do uvicorn ou mais de uma réplica do backend, o teto efetivo é multiplicado pelo número de processos, e reiniciar o processo zera os contadores. A interface `RateLimiter` (`app/core/rate_limit.py`) permite trocar por um backend compartilhado (Postgres/Redis) quando houver escala horizontal (ver R21).

---

## 10. Login, sessões, CSRF e proxy reverso

- **Rate limit de login**: por par (IP, e-mail) — 5 falhas iniciam um backoff progressivo (30 s, dobrando a cada nova falha, teto de 15 min) — e teto por IP de 50 falhas/15 min (password spraying). Falhas de um IP **não** bloqueiam o mesmo e-mail vindo de outro IP; um login bem-sucedido reinicia a contagem do par. Bloqueios respondem `429` com `Retry-After`.
- **Respostas indistinguíveis**: conta inexistente, desativada ou senha errada retornam o mesmo `401 invalid_credentials`.
- **Sessões**: `POST /auth/change-password` e `python -m app.cli.bootstrap_admin --reset-password` revogam as outras sessões do usuário (a atual é mantida na troca; o reset derruba todas).
- **Proxies confiáveis (`TRUSTED_PROXIES`)**: `X-Forwarded-For`/`X-Forwarded-Proto` só são respeitados quando o par TCP está na lista (IPs/CIDRs em JSON). O IP do cliente é a entrada mais à direita do XFF que não seja um proxy confiável; cabeçalho inválido/longo é ignorado. Padrão do compose: redes privadas do Docker. Fora do compose, **defina** a variável, ou o IP visto será o do proxy.
- **CSRF**: token assinado (HMAC-SHA256 com `CSRF_SECRET`; rotacionar o segredo invalida os tokens em circulação, o cliente obtém outro em `GET /auth/csrf`). O cabeçalho `Origin` é comparado por igualdade exata de esquema+host+porta contra `CORS_ORIGINS` e a própria origem da requisição. **Em produção inclua a origem pública (https) em `CORS_ORIGINS`.**

---

## 11. Trilha de auditoria

- **Cobertura**: toda mutação da API (cadastros, cabos/segmentos, conexões, medições, anexos, importação/exportação, usuários) e a autenticação (`auth:login_succeeded`, `auth:login_failed` — sem senha nem e-mail digitado —, `auth:logout`, `auth:password_changed`) geram **exatamente um** `AuditEvent` com `actor_id`, `request_id` (o `X-Request-ID` da resposta) e o diff da alteração. Serviços com evento próprio mais rico (ex.: `customer:created`, `connection_batch_applied`) substituem o genérico.
- **Mecanismo** (`app/modules/audit/hooks.py`): a dependência `audit_mutation` prepara o contexto (ator, request_id, rota) na Session da requisição; listeners `after_flush`/`before_commit` acumulam o que foi criado/alterado/removido e gravam o evento **na mesma transação** da operação (rollback descarta o evento). Rotas somente-leitura (trace/impact/budgets/simulações/split-preview) e stubs 501 não geram evento.
- **Imutabilidade**: um trigger no PostgreSQL (`trg_audit_events_append_only`, migração 0012) bloqueia `UPDATE`/`DELETE` em `audit_events`, inclusive para o usuário da aplicação. `TRUNCATE` continua permitido a quem administra o banco. Nunca inclua `audit_events` em rotinas de retenção.

---

## 12. Exportações e jobs

- **Auditoria**: criar uma exportação grava `export_requested` (formato, camadas, ator) e cada download grava `export_downloaded`.
- **Dados pessoais**: exportações com a camada `customers` só são baixáveis por `admin` — o papel é revalidado no download (`exports:read` + conhecer o `job_id` não basta).
- **Retenção (`EXPORT_TTL_DAYS`, padrão 7)**: o worker remove os arquivos de exportação vencidos (o registro do job permanece) e o download responde `410 Gone` após o prazo, mesmo antes da limpeza.
- **Erros de job**: `GET /jobs/{id}` devolve só mensagens seguras (validações de negócio) ou uma mensagem genérica; o detalhe técnico (SQL, caminhos, traceback) fica no log do worker com o `job_id`. A leitura exige `exports:read` (jobs de exportação) ou `imports:read` (importação).

---

## 13. Pipeline de importação

- **Cabos**: um cabo importado gera `Cable` + `CableSegment` com a geometria do arquivo (tubos, fibras e terminais incluídos). As pontas são resolvidas por (a) `origin_code`/`destination_code` (propriedade GeoJSON ou coluna CSV) e, na falta deles, (b) proximidade com estruturas do próprio arquivo ou já cadastradas, dentro de `ROUTE_ENDPOINT_TOLERANCE_M` (5 m). Se uma ponta não resolve, o item vira **erro na prévia** e o commit é recusado (All-or-Nothing). Nunca há coordenadas padrão: CSV de cabo sem coluna `coordinates` é erro.
- **Idempotência**: `POST /imports/{id}/commit` insere o job com `INSERT … ON CONFLICT (idempotency_key)`; a chave (até 128 caracteres) é escopada por usuário. Mesma chave + mesma prévia devolve o mesmo job; mesma chave com outra prévia, ou a mesma prévia com outra chave, responde `409`.
- **Lease**: `JOB_LEASE_SECONDS` (60) é renovada a cada lease/3 por uma thread de heartbeat enquanto o job roda (o heartbeat do worker no healthcheck também). Antes de gravar o resultado o worker trava a linha do job e confere que ainda é o dono; se perdeu a lease, descarta tudo (inclusive entidades importadas) e o outro worker prevalece.
- **Storage**: importações/exportações ficam em `STORAGE_PATH/imports|exports` e os caminhos são gravados **relativos** a essa raiz. Registros antigos (caminho absoluto ou relativo ao diretório de trabalho, ex.: `storage/exports/…`) continuam sendo resolvidos sem migração de dados.

---

## 14. Concorrência otimista

- **If-Match atômico**: toda entidade versionada usa `version_id_col`: o `UPDATE`/`DELETE` é `… WHERE id = :id AND version = :versão_lida`. Duas requisições com o mesmo `If-Match` resultam em exatamente um `200` e um `412`; qualquer gravação defasada em outro fluxo também vira `412` (nunca `500`). A validação do cabeçalho é única (`app/core/concurrency.py`).
- **Divisão de trecho** (`POST /cable-segments/{id}/split`): exige `If-Match` (versão do trecho) **ou** `expected_topology_revision` no corpo (padrão do editor de fusão); a linha de estado da topologia e o trecho são travados (`FOR UPDATE`). Sem nenhum dos dois: `428`; revisão divergente: `409`; versão defasada: `412`; divisões simultâneas do mesmo trecho: só uma vence.

---

## 15. Rastreio óptico e análise de impacto

- **Trace** (`POST /topology/trace`) e **impacto** (`POST /topology/impact`) carregam o subgrafo relevante em um número fixo de queries (CTE recursiva com `LATERAL` + uma query por tipo de elemento) e percorrem o grafo em memória (`app/modules/topology/graph.py`). O impacto carrega o grafo de todos os vínculos ativos uma única vez; o nº de statements não depende do nº de clientes nem de `max_hops`.
- **Teto de saltos**: efetivo = `min(max_hops, MAX_TRACE_HOPS)` (padrão 300).
- **Índices**: `idx_terminals_entity` (0011) e `idx_splitters_input_terminal` (0013), ambos `CREATE INDEX CONCURRENTLY`.
- `tests/legacy_topology_service.py` guarda a implementação anterior apenas como **oráculo** dos testes de caracterização (mesmos resultados em grafos aleatórios); não é usada em produção.

---

## 16. Banco de dados: pool, timeouts e health

Valores adotados (decisão de capacidade; ajuste por variável de ambiente):

| Variável | Padrão | Observação |
|---|---|---|
| `WEB_CONCURRENCY` | `2` | processos uvicorn da API (Dockerfile) |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | `5` / `5` | **por processo**: API = workers × (5+5) = 20 conexões; PostgreSQL padrão aceita 100 (folga para worker, migrate e ferramentas) |
| `DB_STATEMENT_TIMEOUT_MS` | `30000` | qualquer query da API é cancelada em 30 s |
| `DB_WORKER_STATEMENT_TIMEOUT_MS` | `600000` | teto separado do worker de jobs (importações longas) |
| `DB_CONNECT_TIMEOUT_SECONDS` | `10` | banco inalcançável falha em ≤ 10 s |
| `HEALTH_DB_TIMEOUT_SECONDS` | `2` | conexão dedicada e curta da readiness |

- `/health/ready` usa uma conexão própria (sem pool, timeouts de 2 s) e a head do Alembic é lida uma única vez (cache): responde mesmo com a API saturada.
- Com mais de um worker, as **métricas em memória** e o **rate limit em memória** são por processo (ver R16/R21).
- `GET /auth/me` executa 1 SELECT; `last_activity_at` só é gravado após 60 s de inatividade da sessão.
- A revisão topológica (`bump_topology_revision`) é o último passo antes do commit nas transações longas (divisão de trecho e importação): o lock da linha de estado dura só até o commit.

---

## 17. Métricas (`/api/v1/metrics`)

- **Cardinalidade limitada**: requisições sem rota resolvida (404/405) usam o rótulo fixo `path="__unmatched__"` — nunca o caminho bruto — e há um teto de 1000 combinações de rótulos por processo (`__overflow__` além disso). Scans/bots não crescem a memória nem as séries.
- **Agregação entre processos**: com `METRICS_DIR` definido (o compose usa `/app/storage/metrics`, volume compartilhado entre `backend` e `worker`) cada processo — workers da API e o worker de jobs — publica um snapshot JSON (a cada ≥ 5 s, escrita atômica) e o scrape soma tudo: contadores, histogramas e `background_jobs` do worker aparecem em qualquer resposta. `ftth_processes{role="api|worker"}` mostra quantos processos estão publicando.
- Cada processo republica o snapshot a cada `METRICS_PUBLISH_INTERVAL_SECONDS` (10 s, thread de heartbeat — inclusive ocioso); snapshots parados há mais de `METRICS_SNAPSHOT_TTL_SECONDS` (60) deixam de contar (processo morto → seus contadores "resetam", como um restart no Prometheus) e arquivos com mais de 1 h são apagados. Sem `METRICS_DIR`, o modo é processo único (métricas em memória).
- O endpoint segue restrito (`X-Metrics-Token` ou sessão admin; `METRICS_ENABLED=false` → 404) e **não** é publicado pelo Caddy (ver R17).

---

## 18. Proxy: TLS, HSTS e CSP

- **TLS no Caddy** (recomendado quando o servidor tem IP público): defina `SITE_ADDRESS=ftth.exemplo.com.br` no `.env`, aponte o DNS para o host e mantenha 80/443 abertas; o Caddy emite/renova o certificado (volume `caddy_data`), redireciona HTTP→HTTPS e envia HSTS. Inclua `https://ftth.exemplo.com.br` em `CORS_ORIGINS` (o `Origin` das escritas é comparado por igualdade exata) e mantenha `TRUSTED_PROXIES` cobrindo a rede do Docker.
- **TLS em balanceador externo** (alternativa): deixe `SITE_ADDRESS=:80`; o balanceador termina o TLS e **deve** enviar `X-Forwarded-Proto: https` (o Caddy emite HSTS nesse caso e o backend enxerga `https` via `TRUSTED_PROXIES`). Não publique a porta 80 do Caddy diretamente na internet.
- **CSP**: definido pelo Next.js com nonce por resposta (`script-src` sem `unsafe-inline`/`unsafe-eval`); a página raiz é renderizada dinamicamente por isso. Novas origens de tiles/APIs externas exigem ajustar `frontend/src/middleware.ts`.
- Verificação: `curl -sI https://<domínio>/login` deve mostrar `content-security-policy` sem `unsafe-*` e `strict-transport-security`; `curl -s -o /dev/null -w '%{http_code}' https://<domínio>/api/v1/metrics` deve retornar `404`.

---

## 19. Supply chain e CI

- **Dependências**: `pnpm audit` e `pip-audit` sem vulnerabilidades conhecidas. `maplibre-gl` 5.24 → 6.10 (a v6 removeu o export default: `import * as maplibregl from "maplibre-gl"`), `vitest` 3 → 4.1.11 e override de `postcss ^8.5.28` em `frontend/pnpm-workspace.yaml` (o `next` fixa 8.4.31, vulnerável). A versão do pnpm vem do campo `packageManager` (Dockerfile e CI usam a mesma).
- **CI** (`.github/workflows/ci.yml`): `permissions: contents: read`; actions fixadas por SHA (comentário com a versão; o Dependabot atualiza); jobs: backend (ruff/mypy/contrato/migrações/pytest/restore drill), frontend (lint/typecheck/vitest/build), **security** (pip-audit, `pnpm audit --audit-level high`, gitleaks) e **docker-build** (`docker compose build` + Trivy CRITICAL/HIGH nas imagens). CodeQL roda em `codeql.yml` (python e javascript-typescript, semanalmente também).
- **Imagens**: o build aplica os patches da distro (`apt-get upgrade`/`apk upgrade`) e a imagem do frontend não leva npm/corepack. Reexecute `docker compose build` + Trivy ao atualizar a imagem base.
- **Smoke manual pendente**: o upgrade major do MapLibre foi validado por typecheck, testes e build, mas não por navegador; abra o mapa (arrastar, camadas, desenho de rota) antes de publicar.

---

## 20. Backup e restore seguros

- **Chaves** (guarde-as **fora** do servidor de backup; sem elas o pacote não é restaurável):
  - `BACKUP_SIGNING_KEY` (obrigatória em produção, `openssl rand -hex 32`): assina o `manifest.json` com HMAC-SHA256. O restore verifica a assinatura **antes de extrair qualquer arquivo**; pacote adulterado, sem assinatura ou de outra instalação é recusado. Rotacionar a chave invalida os backups antigos (restaure-os com a chave da época).
  - `BACKUP_ENCRYPTION_KEY` (opcional, **recomendada**; 32 bytes em hex/base64): criptografa o pacote com AES-256-GCM em blocos autenticados (`ftth_backup_*.tar.gz.enc`); o texto claro não permanece em disco. Chave errada, bit adulterado ou pacote truncado falham na autenticação. Se ela ficar de fora, o backup segue sem criptografia (com aviso).
- **Arquivos** gerados com permissão `0600`. Restauração ignora/recusa entradas de tar com `..`, caminho absoluto, links ou devices (`filter="data"`), e nomes de tabela fora de `^[a-z_][a-z0-9_]*\.bin$` ou inexistentes no schema (allowlist via `information_schema`); os nomes nunca são interpolados em SQL (`psycopg.sql.Identifier`).
- **Consistência**: o dump usa **um snapshot** (`pg_dump -Fc`, ou COPY binário em transação `REPEATABLE READ` somente leitura) — escritas durante o backup não geram filhos sem pai. A restauração carrega tudo numa transação e **revalida todas as chaves estrangeiras antes do commit**; qualquer violação reverte a carga.
- **Criptografia escolhida**: biblioteca Python (`cryptography`, AES-256-GCM em fluxo) em vez de `age`/`gpg`, para não depender de binário externo na imagem. Se preferir `age`, criptografe o `.tar.gz` gerado e mantenha `BACKUP_SIGNING_KEY`.
- **Drill**: `python scripts/restore_drill.py` (roda no CI) exercita backup → restore isolado → verificação; rode-o também com `BACKUP_ENCRYPTION_KEY` definida.

---

## 21. Consistência dos anexos (banco × disco)

- O upload grava em arquivos temporários (`*.uploading`), monta a linha e a auditoria na sessão, **promove** os arquivos ao caminho final com `os.replace` e só então faz o `commit`. Qualquer falha (miniatura, auditoria, commit, queda de conexão) remove temporários e finais e reverte a sessão: nenhum arquivo órfão fica em `originals/` ou `thumbnails/`.
- Escolha: promover antes do commit e compensar na falha. O pior caso (queda do processo entre os dois passos) deixa um arquivo órfão, que o reconciliador remove — nunca um registro apontando para arquivo inexistente.
- `POST /attachments/reconcile-orphans` só remove arquivos sem registro **mais antigos que `ATTACHMENT_ORPHAN_GRACE_MINUTES` (padrão 15)**; arquivos recentes podem ser de um upload em andamento. Restos `*.uploading` antigos também são limpos. `?dry_run=true` lista sem apagar.

---

## 22. Escala horizontal e backup agendado

- **Réplicas no mesmo host**: `docker compose up -d --scale backend=2 --scale worker=2`. O Caddy balanceia entre as réplicas (`dynamic a`, `least_conn`, DNS a cada 5 s); o pool de conexões é por processo (ver seção 16). Cada réplica do worker consome a fila com segurança (`SKIP LOCKED` + lease). O storage é o volume local compartilhado — por isso **todas as réplicas devem estar no mesmo host** (multi-host exige storage compartilhado: ver `docs/adr/0007-escala-horizontal.md`).
- **Limitação**: o rate limit das rotas caras é em memória por processo (teto efetivo = N × limite).
- **Backup agendado**: `docker compose --profile backup up -d backup` gera um pacote a cada `BACKUP_INTERVAL_SECONDS` (24 h) em `/app/backups` (volume `backups`), mantém os últimos `BACKUP_RETENTION_COUNT` (7) e usa `BACKUP_SIGNING_KEY` (obrigatória) e `BACKUP_ENCRYPTION_KEY` (recomendada). **Copie o volume para fora do servidor** (rsync/rclone/objeto): backup no mesmo disco não protege contra perda do host. Restaure com `python scripts/restore.py <arquivo>` (assinatura verificada antes de extrair).
- Alternativa sem o serviço: cron no host com `docker compose exec -T backend python scripts/backup.py --target-dir /app/backups`.
