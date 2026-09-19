# Estado do projeto — auditoria de segurança, estrutura e performance

> Atualizado em 19/09/2026. Detalhe técnico por achado: `docs/security-audit/resolucao.md`.
> Procedimentos de operação das mudanças: `docs/runbooks/deployment-and-maintenance.md` (seções 9–28).

## 1. O que foi feito

A auditoria (`docs/security-audit/`) apontou 53 achados (18 de segurança, 21 de estrutura, 14 de performance). Todos foram tratados em 28 etapas (R01–R28), com teste escrito antes da correção, migrações com `downgrade` e contratos (`contracts/`) regenerados. **Tudo está na `master`** (PR #2 mesclado); é a única branch do repositório.

| Área | Principais entregas |
|---|---|
| Autenticação e acesso | Todas as rotas de negócio exigem login por padrão; PII de clientes exige `customers:read/write` (rotas, anexos e auditoria mascarada); rate limit de login por (IP, e-mail), erros indistinguíveis, revogação de sessões ao trocar senha, proxies confiáveis, CSRF assinado com Origin exato |
| Configuração e segredos | Produção recusa segredos padrão; compose exige as variáveis (`${VAR:?}`); token de `/metrics` comparado em tempo constante; scripts de demonstração recusam produção/banco remoto e usam senha aleatória; a tela de login deixou de exibir credenciais |
| Rede/proxy | TLS e HSTS pelo Caddy (`SITE_ADDRESS`), CSP com nonce sem `unsafe-*`, `/metrics` fora do proxy, limite de corpo |
| Dados e consistência | Auditoria central de todas as mutações (append-only no banco); `If-Match` atômico (`version_id_col`); divisão de segmento serializada; importação de cabos com geometria, idempotente, com lease renovada; upload de anexo consistente com o disco; exportações auditadas, com TTL de 7 dias |
| Worker e operação | Worker de jobs corrigido (não subia), com healthcheck e logs JSON; métricas agregadas entre processos; backup assinado (HMAC) e cifrado (AES-256-GCM); ADR 0007 e compose escalável (`--scale`); retenção de `login_attempts` e sessões |
| Performance | Dashboard 2.514 → 7 queries; trace/impacto em memória com queries fixas (impacto de 300 clientes 8.366 → 14 queries); importação e exportação em lotes/fluxo; índices trigram e de listagem; timeouts e pool por processo; readiness independente do pool |
| Supply chain / CI | `pip-audit`, `pnpm audit` (7 → 0 avisos), gitleaks, Trivy, CodeQL; imagens endurecidas; maplibre-gl 6 |
| Entrada de dados | Tetos de tamanho em todos os schemas; identificadores validados como UUID (422 em vez de 500) |
| Frontend | Matriz de permissões gerada do backend (`contracts/permissions.json`), menu/rotas/ações escondidos por permissão |

Resultado: **52 achados corrigidos, 1 parcial (PERF-09), 0 pendentes**; rotas sem autenticação de 18 para 8 (todas intencionais). Backend: 554 testes localmente (553 passam sem `pg_dump`/`pg_restore` no PATH + 1 pulado; 531 antes desta sessão + 23 novos de `StorageBackend`/S3); frontend: 181.

**Sessão de 19/09/2026 (depois do adendo acima): EST-14 resolvido.** Storage de anexos/importações/exportações abstraído em `StorageBackend` (`backend/app/core/storage_backend.py`): `LocalStorage` (padrão, disco/volume, sem mudança de comportamento) e `S3Storage` (boto3, S3-compatível — MinIO escolhido pelo operador). `attachments/service.py`, `exports/service.py`, `imports/service.py`, `jobs/service.py` e os endpoints de download migrados; `core/storage.py` removido. Testado com `moto` (21 testes novos, rodam no CI) e manualmente contra um MinIO real (upload, hash, miniatura, delete, exportação em fluxo — todos OK; imagem `quay.io/minio/minio`, pois `minio/minio` saiu do Docker Hub em 2025). MinIO local em `compose.s3.yaml`, arquivo **separado** de propósito: `docker compose up` (só `compose.yaml`) não pode passar a exigir `MINIO_ROOT_USER`/`PASSWORD` de quem nunca vai usar S3 (testado: `docker compose config` falha na interpolação de variáveis mesmo com o serviço atrás de `profiles`, porque o compose valida o arquivo inteiro antes de aplicar o profile). Detalhe: `docs/adr/0007-escala-horizontal.md`.

## 2. Situação do CI (`master`, 19/09/2026)

| Workflow | Situação |
|---|---|
| CI (backend, frontend, security, docker) | **verde** |
| CodeQL | **removido** (`.github/workflows/codeql.yml`) — repositório privado sem GitHub Advanced Security, então o upload do SARIF sempre falhava ("Code scanning is not enabled for this repository"), mesmo com a análise em si não encontrando problema. `pip-audit`, `pnpm audit`, gitleaks e Trivy continuam rodando no CI |

Nenhum PR aberto. Dependabot: atualizações de versão desligadas (`open-pull-requests-limit: 0`); alertas de segurança seguem nas configurações do repositório.

O CI vermelho anterior tinha uma causa real de código: `restore_backup` usava `pg_restore --clean`, que recria a extensão PostGIS e quebra as conexões já abertas (`no spatial operator found … opfamily`). Corrigido (`_write_restore_list`); detalhe em `docs/security-audit/resolucao.md` §7.

## 3. O que falta fazer (checklist para retomar)

### 3.1 Só você consegue (conta, domínio, infraestrutura)

1. **Confirmar as decisões assumidas** (seção 4 abaixo).

**TLS/domínio — decisão de projeto (não pendência):** projeto open source/self-hosted (`README.md`); cada instalação tem seu próprio domínio, então configurar `SITE_ADDRESS` com o domínio real e verificar CSP/HSTS em produção fica a cargo de quem instala. O Caddy já faz TLS automático (Let's Encrypt) a partir dessa variável, sem código adicional — procedimento documentado em `docs/runbooks/deployment-and-maintenance.md`.

### 3.2 Posso fazer numa próxima sessão (sem depender de infraestrutura)

- **Backup do bucket S3/MinIO** — `scripts/backup.py`/`restore.py` só cobrem o volume local (`STORAGE_PATH`); quem ligar `STORAGE_BACKEND=s3` em produção depende só da durabilidade própria do MinIO/S3 (versionamento/replicação do bucket) até isso ser feito. Ver item 4 do épico em `docs/adr/0007-escala-horizontal.md`.
- **URLs pré-assinadas do S3** — hoje todo download com `STORAGE_BACKEND=s3` passa pelo backend (`StreamingResponse`); pré-assinar a URL evitaria essa carga em arquivos grandes. Item 2 do mesmo épico.
- **N-03 — permissões sem rota**: `cables:*`, `connectivity:*`, `topology:*` e `map:read` existem no RBAC, mas as rotas exigem `network:*`. Caminho seguro: remover as permissões mortas e regenerar `contracts/` (`scripts/export_permissions.py` + OpenAPI). Muda o retorno de `/auth/me`.
- **Smoke do mapa com `maplibre-gl` 6** em navegador headless (Playwright) contra o compose local.
- **PERF-09** — o `UPDATE network_topology_state` (linha única) serializa escritas de topologia. Mitigado (último passo antes do commit + `statement_timeout`). Advisory lock/sequence só se a medição mostrar contenção; não é urgente.
- **N-05** — rate limit em memória por processo (efetivo ×2 com `WEB_CONCURRENCY=2`, zera a cada restart). Aceito; a interface `RateLimiter` (`core/rate_limit.py`) permite trocar por Postgres/Redis.
- **N-08** — `docs/security-audit/tools/*.py` têm caminhos absolutos; não regerar `inventario-rotas.md` sem revisar.
- **Revisão do diff** — `/code-review` e `/security-review` sobre as 28 etapas + adendo, recomendado antes de considerar a auditoria concluída.

### 3.3 Como rodar tudo localmente

```bash
# Banco descartável (NÃO use o ftth_db de desenvolvimento nos testes)
docker run -d --name ftth-test-pg -p 127.0.0.1:55433:5432 \
  -e POSTGRES_USER=ftth_test -e POSTGRES_PASSWORD=ftth_test_pw -e POSTGRES_DB=ftth_manager_test \
  postgis/postgis:16-3.4
export TEST_DATABASE_URL=postgresql+psycopg://ftth_test:ftth_test_pw@127.0.0.1:55433/ftth_manager_test
cd backend && uv sync --extra dev && DATABASE_URL=$TEST_DATABASE_URL uv run alembic upgrade head
uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest   # ~10 min
cd ../frontend && pnpm install --frozen-lockfile && pnpm lint && pnpm typecheck && pnpm test
```

- **Instale `pg_dump`/`pg_restore` (cliente PostgreSQL 16) na máquina.** Sem eles os testes de backup caem no dump binário do psycopg e **não exercitam o caminho que roda no CI** — foi por isso que o bug do PostGIS não aparecia localmente. `test_backup_security.py` tem dois testes mutuamente exclusivos por `pg_dump`/`pg_restore` (um só roda com eles, outro só sem); nas duas situações: 553 passam e 1 é pulado (verificado nesta sessão sem `pg_dump`/`pg_restore` no PATH).
- Sem `TEST_DATABASE_URL` a suíte usa `127.0.0.1:5432/ftth_manager_test` (o mesmo servidor do `ftth_db`).
- Containers descartáveis desta sessão, se ainda existirem: `docker rm -f ftth-test-pg ftth-audit-pg`.

## 4. Decisões assumidas (confirmar)

Sem painel/busca públicos; rate limit em memória por processo (interface trocável); auditoria por listeners da Session; exportações expiram em 7 dias; cabos importados resolvem pontas por código → proximidade → erro; 2 workers, pool 5+5 e `statement_timeout` 30 s (worker 10 min); TLS no Caddy (balanceador externo documentado); upgrade do maplibre-gl 6; backup cifrado por `cryptography` (AES-256-GCM); retenção de 30 dias (`login_attempts`) e 7 dias (sessões inválidas), `audit_events` sem retenção; R21 só ADR.

## 5. Incidente de processo (registrado por transparência)

Durante a R26, um teste meu executou `benchmark_endpoints.py` **antes** de ele ter a guarda de ambiente e ele gravou 1 usuário e 3 sessões no banco de desenvolvimento local (container `ftth_db`, porta 5432). Os registros foram removidos e o banco voltou ao estado anterior (vazio). A guarda atual impede a repetição. Além disso, sem `TEST_DATABASE_URL` a suíte de testes usa `127.0.0.1:5432/ftth_manager_test` por padrão — defina a variável para apontar para um banco descartável.
