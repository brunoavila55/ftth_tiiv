# ADR 0007: Escala Horizontal (várias réplicas do backend e do worker)

- **Status**: Aceito (implementação parcial — ver "Decisão" e "Épico pendente")
- **Data**: 2026-09-19
- **Origem**: auditoria de segurança/estrutura/performance, achado EST-14 (issue 21)

## Contexto — estado atual

| Componente | Situação |
|---|---|
| API | uvicorn com `WEB_CONCURRENCY` workers (padrão 2), SQLAlchemy síncrono; pool **por processo** (5+5) |
| Worker de jobs | 1 container; fila em PostgreSQL (`SELECT … FOR UPDATE SKIP LOCKED`), lease renovada por heartbeat |
| Banco | PostgreSQL/PostGIS único (sem réplica) |
| Storage | volume Docker local (`backend_storage`) montado em `backend` e `worker` |
| Proxy | Caddy; upstream do backend por DNS de serviço |
| Métricas | snapshot por processo em `METRICS_DIR` (agregado no scrape) |
| Backup | script manual/`--profile backup` (assinado, criptografia opcional) |

## O que quebra com 2+ réplicas

| Tema | Comportamento com N processos | Situação |
|---|---|---|
| `container_name` fixo | `--scale` falha ("nome já em uso") | **Corrigido** (removido de backend, worker e frontend) |
| Balanceamento no proxy | hostname estático resolvia uma vez; réplicas novas não recebiam tráfego | **Corrigido** (`dynamic a` do Caddy, `least_conn`, refresh 5 s) — verificado com 2 réplicas |
| Métricas em memória | cada processo mostra só o seu | **Corrigido** (R16: agregação por snapshots) |
| Rate limit de rotas caras | contador em memória por processo: teto efetivo = N × limite | **Pendente**: interface `RateLimiter` pronta para backend compartilhado (Postgres/Redis) |
| Rate limit de login | está no PostgreSQL (`login_attempts`) | Compartilhado, ok |
| Sessões / CSRF | sessão opaca no banco; CSRF assinado (stateless) | Compartilhado, ok |
| Fila de jobs | `SKIP LOCKED` + lease: vários workers já são seguros | Ok (R12) |
| Limpeza periódica | cada worker executa; idempotente | Ok |
| Migrações | serviço `migrate` (one-shot) antes do backend | Ok; em rolling deploy execute-as antes de subir a nova versão |
| Storage de anexos/exportações/importações | volume local: só funciona com réplicas **no mesmo host** | **Pendente** (limite real da escala multi-host) |
| Banco único | ponto único de falha | **Pendente** (HA fora do escopo do produto) |

## Decisão

1. **Curto prazo (feito)**: permitir `docker compose up -d --scale backend=N --scale worker=M` num único host — sem `container_name` fixo, Caddy balanceando entre réplicas, healthcheck do worker, métricas agregadas, pool dimensionado por processo, agendamento de backup opt-in (`--profile backup`). Testado com `--scale backend=2` (ambas saudáveis, readiness 200 via Caddy, `/metrics` externo 404, `ftth_processes` por papel).
2. **Multi-host**: exige storage compartilhado. Recomendação: **abstrair o storage (interface `StorageBackend`) e oferecer S3/MinIO**, mantendo o volume local como padrão. NFS funciona, mas herda problemas de lock/latência e não elimina o ponto único de falha; só é aceitável como ponte.
3. **Rate limit distribuído**: implementar um `RateLimiter` em Postgres (tabela + `INSERT … ON CONFLICT`) só quando houver >1 réplica em produção; Redis apenas se já existir na infraestrutura (nova dependência).
4. **HA do banco**: fora do escopo do aplicativo; recomendar PostgreSQL gerenciado ou Patroni/streaming replication, com backup assinado e restore testado (drill no CI).

## Opções e custo

| Opção | Ganho | Custo |
|---|---|---|
| Mais workers uvicorn (`WEB_CONCURRENCY`) | CPU do host | Nenhum; ajustar pool (conexões = workers × 10) |
| Réplicas no mesmo host (`--scale`) | Isolamento de falha, rolling restart | Baixo (já feito) |
| S3/MinIO para anexos/exportações | Multi-host, durabilidade | Médio: interface + migração de caminhos + reconciliador por prefixo; MinIO é 1 container extra |
| NFS | Multi-host sem código | Baixo em código, alto operacional (latência, locks, SPOF) |
| Rate limit em Postgres | Teto global correto | Baixo/médio: 1 tabela + índice, ~1 query por requisição limitada |
| HA do banco | Disponibilidade | Alto (operação), independente do app |

## Épico pendente — tarefas para priorizar

1. `StorageBackend` (interface: `put/get/delete/exists/stream`, chaves relativas) + implementação `LocalStorage` (padrão) sem mudança de comportamento.
2. `S3Storage` (boto3/MinIO), configuração por `STORAGE_BACKEND=s3`, URLs pré-assinadas para download opcional.
3. Migrar anexos/exportações/importações para a interface (hoje: `attachments/service.py`, `exports/service.py`, `imports/service.py`, `core/storage.py`).
4. Reconciliador e retenção operando por prefixo/idade no backend escolhido; backup incluir o bucket (ou exigir versionamento/replicação do bucket).
5. `PostgresRateLimiter` atrás da interface `RateLimiter`.
6. Guia de HA do PostgreSQL e teste de failover no runbook.

## Consequências

- Escalar no mesmo host já é suportado e testado; escalar entre hosts depende do épico de storage.
- O modo padrão (1 host, volume local) continua simples e sem novas dependências.
