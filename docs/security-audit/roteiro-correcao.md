# Roteiro de correção — FTTH Manager

> **Confidencial** (descreve vulnerabilidades reais). Base: `docs/security-audit/` — 53 achados, 29 issues em `issues.md`, evidências em `findings.json`.
> Este roteiro transforma cada issue em uma **etapa (R01…R28)** com um prompt pronto para colar no Claude Code.

## 1. Como usar

1. Faça a **Fase 0** (manual) uma vez.
2. Para cada etapa, na ordem da seção 3: crie uma branch (`fix/R03-auth-por-padrao`), abra uma sessão nova do Claude Code na raiz do repositório, cole o **Prompt-base** (seção 2) e depois o **prompt da etapa**.
3. Ao final de cada etapa: leia o diff, rode `/code-review high` (e `/security-review` nas etapas de segurança), rode a suíte completa e só então faça o merge.
4. Marque a etapa no checklist da seção 6 e atualize `docs/security-audit/resolucao.md` (a etapa R28 cria esse arquivo).

Regras do processo: **uma etapa = uma branch = um PR pequeno**; teste que falha antes e passa depois; nada de refatoração fora do escopo; nunca colar segredos em prompts.

## 2. Prompt-base (colar no início de TODA sessão)

```text
Contexto: repositório FTTH Manager (backend FastAPI/SQLAlchemy síncrono/PostgreSQL+PostGIS em backend/, frontend Next.js em frontend/, Caddy + docker compose).
Uma auditoria está em docs/security-audit/ (issues.md = texto das issues numeradas; findings.json = achados com arquivo:linha, trecho, correção sugerida e critérios de aceite; inventario-rotas.md = as 110 rotas).
Vou pedir a correção de uma ou mais issues. Regras obrigatórias:

1. Antes de editar, rode `git status` e `git branch --show-current`. Se houver mudanças não relacionadas à tarefa, PARE e me avise.
2. Leia a(s) issue(s) citada(s) em docs/security-audit/issues.md e os achados correspondentes em findings.json. As linhas citadas podem ter mudado por etapas anteriores: confirme cada trecho no código atual antes de alterar (não confie cegamente nos números de linha).
3. TDD: escreva PRIMEIRO os testes automatizados descritos nos "Critérios de aceite" e mostre-os FALHANDO no código atual (saída do pytest/vitest). Só depois implemente a correção e mostre-os PASSANDO.
4. Mudança mínima: só o necessário para a issue. Não refatore, não renomeie, não formate arquivos alheios. Se achar outro problema, anote no final; não corrija.
5. Backend (a partir de backend/): `uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest`. Frontend (a partir de frontend/): `pnpm lint && pnpm typecheck && pnpm test`. Tudo deve passar. Os testes de integração precisam de PostGIS: use um Postgres descartável (docker) — NUNCA um banco de produção.
6. Se o contrato da API mudar (schemas, status codes, headers), regenere contracts/openapi.json (backend/scripts/export_openapi.py) e contracts/api-types.d.ts e ajuste o frontend/testes de contrato.
7. Migrações Alembic: sempre com downgrade funcional; teste `alembic upgrade head` e `downgrade -1` em banco descartável.
8. Nunca escreva segredos reais em código, testes, logs ou mensagens de commit.
9. Não faça push nem merge. Ao terminar, entregue: (a) resumo do que mudou, (b) saída dos testes novos falhando-antes/passando-depois, (c) saída completa de lint/mypy/testes, (d) itens dos critérios de aceite marcados como atendidos ou não (com o motivo), (e) riscos/decisões que ficaram para mim.
10. Mensagem de commit: `fix(<área>): <resumo> (issue N / ID)`. Faça o commit apenas se eu pedir.
```

## 3. Ordem e dependências

| Fase | Etapa | Cobre (achados) | Issue | Depende de | Esforço |
|---|---|---|---|---|---|
| 0 | Preparação (manual) | — | — | — | 1–2 h |
| **1 — Onda 1 (dias)** | R01 Build do frontend | EST-15 | 22 | — | baixo |
| | R02 Worker de jobs | EST-01, EST-18 | 13 | — | baixo |
| | R03 Autenticação por padrão | EST-02, SEC-01 | 15/1 | — | baixo |
| | R04 PII de clientes | SEC-03, SEC-04 | 3 | R03 | baixo/médio |
| | R05 Segredos e configuração | SEC-05, SEC-02, EST-17 | 4/2 | — | baixo |
| | R06 Tetos de entrada e rate limit | EST-11 | 18 | — | médio |
| | R07 Upload de imagem | PERF-04 | 25 | — | baixo |
| | R08 Dashboard N+1 e índice de terminais | PERF-01, PERF-03 | 23/26 | R03 | baixo |
| **2 — Onda 2 (2–4 sem)** | R09 Login, sessões e CSRF | SEC-06/07/08/09/18 | 5/6 | R05 | médio |
| | R10 Cobertura de auditoria | EST-10, SEC-17 | 12 | R09 | alto |
| | R11 Exportações e jobs | SEC-13, SEC-14 | 10 | R02, R10 | médio |
| | R12 Pipeline de importação | EST-05/06/07/08 | 14 | R02 | médio |
| | R13 Concorrência otimista e split | EST-03, EST-04, EST-21 | 16 | — | médio |
| | R14 Impacto e rastreio óptico | PERF-02, PERF-14 | 24 | R08 | alto |
| | R15 Pool, timeouts e health | PERF-12/13/10/09 | 28 | R05 | médio |
| | R16 Métricas | EST-13 | 20 | R05 | baixo |
| | R17 Proxy: TLS, HSTS e CSP | SEC-11 | 8 | R06 | médio |
| | R18 Supply chain e CI | EST-16, SEC-15 | 11 | R01 | médio |
| | R19 Backup e restore | SEC-10, EST-19 | 7 | — | médio |
| | R20 Uploads: consistência | EST-09 | 17 | R07 | médio |
| **3 — Onda 3 / backlog** | R21 Escala horizontal | EST-14 | 21 | R15, R16 | alto |
| | R22 Importação/exportação em memória | PERF-05, PERF-08 | 27 | R12 | médio |
| | R23 Índices de busca e listagem | PERF-06, PERF-07 | 26 | — | médio |
| | R24 Retenção de dados | PERF-11 | 29 | R11 | baixo |
| | R25 Validação de UUID e tamanhos | EST-12 | 19 | — | baixo |
| | R26 seed_demo | SEC-12 | 9 | — | baixo |
| | R27 Permissões front × back | EST-20 | 15 | R04 | médio |
| — | R28 Re-auditoria final | todos | — | todas | médio |

**Cobertura:** SEC-01…18, EST-01…21 e PERF-01…14 aparecem ao menos uma vez (tabela por ID na seção 6). SEC-16 (cadeia) é resolvida pela soma de R03 + R08 + R15.

**Paralelismo (git worktrees):** podem andar em paralelo R01, R05, R18, R19, R26 (arquivos independentes). Serialize as que tocam os mesmos arquivos: `core/config.py` (R05→R06→R07→R09→R15), `identity/service.py` (R09→R10), `jobs/service.py` (R02→R11→R12→R22→R24), `cables/service.py` (R13→R20), `topology/service.py` (R14).

---

## 4. Fase 0 — Preparação (manual, uma vez)

O código auditado é o **working tree** (108 entradas ainda não commitadas), não o HEAD `e446c49`. Sem um ponto de partida limpo, os diffs das correções se misturam com o trabalho pendente.

```bash
# 1) Preserve o estado auditado
git switch -c chore/baseline-pre-auditoria
git add -A ':!docs/security-audit'          # docs/security-audit fica de fora do commit
git commit -m "chore: baseline do working tree antes das correções da auditoria"
printf '\n# Auditoria (confidencial)\ndocs/security-audit/\n' >> .gitignore && git add .gitignore && git commit -m "chore: ignora docs/security-audit"

# 2) Banco descartável para testes (troque USUARIO/SENHA por valores locais)
docker run -d --rm --name ftth-test-pg -e POSTGRES_USER=USUARIO -e POSTGRES_PASSWORD=SENHA -e POSTGRES_DB=ftth_manager_test \
  -p 127.0.0.1:55433:5432 postgis/postgis:16-3.4
export DATABASE_URL='postgresql+psycopg://USUARIO:SENHA@127.0.0.1:55433/ftth_manager_test' ENVIRONMENT=test

# 3) Linha de base verde (antes de mexer em qualquer coisa)
cd backend && uv sync --frozen && uv run alembic upgrade head && uv run pytest -q ; cd ..
cd frontend && pnpm install --frozen-lockfile && pnpm test ; cd ..
```

Se a linha de base já tiver testes vermelhos, registre-os: as etapas só devem ser cobradas por regressões novas. Para cada etapa: `git switch -c fix/Rxx-...` a partir de `chore/baseline-pre-auditoria` (ou da branch em que as etapas anteriores foram integradas).

---

## 5. Prompts por etapa

### Fase 1 — Onda 1

#### R01 — Build do frontend (EST-15 · Issue 22)

```text
Siga o Prompt-base. Tarefa: Issue 22 (EST-15).
frontend/Dockerfile faz `COPY --from=builder /app/public ./public`, mas frontend/public não existe, então o build falha com "/app/public: not found".
1. Reproduza: `docker build -f frontend/Dockerfile frontend` deve falhar hoje (mostre a saída).
2. Corrija da forma mais simples e robusta: criar frontend/public/.gitkeep OU remover/tornar opcional o COPY. Explique a escolha (o Next.js standalone não exige public).
3. Confirme que `docker build -f frontend/Dockerfile frontend` conclui e que `docker compose build frontend` funciona.
4. Não altere mais nada no Dockerfile. Adicione ao final um lembrete de que o job de CI `docker compose build` será criado na etapa R18.
Critério de aceite: build da imagem do frontend conclui a partir de um clone limpo.
```

#### R02 — Worker de jobs (EST-01, EST-18 · Issue 13)

```text
Siga o Prompt-base. Tarefa: Issue 13 (EST-01, EST-18).
backend/scripts/run_worker.py importa `process_claimed_job` de app.modules.jobs.service, mas a função existente é `process_next_job` (que faz o claim internamente). O worker morre com ImportError e importações/exportações nunca rodam.
1. Teste primeiro: um teste que carrega scripts/run_worker.py via importlib (o diretório scripts não é pacote) e não deve levantar exceção; mostre-o falhando com o ImportError atual.
2. Extraia de `process_next_job` a função `process_claimed_job(db, job, worker_id) -> bool` (executa um job já reivindicado) e faça `process_next_job` reutilizá-la. Mantenha o comportamento e os testes existentes de tests/integration/test_imports_exports_jobs.py.
3. EST-18: no worker use o mesmo setup_logging JSON do app (com job_id no contexto, sem quebrar por aspas), chame `metrics_collector.record_job` ao concluir/falhar e grave um heartbeat (ex.: toque em um arquivo/coluna a cada iteração do loop) com HEALTHCHECK no serviço `worker` do compose.yaml que falhe se o heartbeat ficar velho.
4. Teste E2E: POST /exports → executar uma iteração do loop do worker → job `succeeded` e arquivo gerado.
Critérios: o import do script funciona; E2E passa; compose.yaml tem healthcheck do worker; logs do worker são JSON válido (teste de parsing).
Não trate aqui lease/heartbeat de jobs longos (é a R12).
```

#### R03 — Autenticação por padrão (EST-02, SEC-01 · Issues 15 e 1)

```text
Siga o Prompt-base. Tarefa: parte de autenticação das Issues 15 (EST-02) e 1 (SEC-01).
Hoje 9 handlers não têm nenhuma dependência de auth (dashboard/summary, 5 stubs de /splitters, 2 de /settings, structures/{id}/occupancy) e /search e /metrics usam auth opcional (docs/security-audit/inventario-rotas.md).
1. Teste primeiro (falhando): teste de varredura BEHAVIORAL — leia os paths/métodos de app.openapi(), substitua parâmetros de path por um UUID qualquer, envie a requisição SEM cookie/Authorization e afirme 401 para TODAS as rotas, exceto uma allowlist explícita e comentada: /health/*, /api/v1/health/*, GET /api/v1/auth/csrf, POST /api/v1/auth/login, POST /api/v1/auth/logout e GET /api/v1/metrics (que aceita X-Metrics-Token; será endurecido na R05). Mostre-o falhando com as rotas atuais.
2. Implemente auth por padrão: em backend/app/api/v1/router.py inclua cada router protegido com `dependencies=[Depends(get_current_user)]` (auth/health ficam de fora ou tratados por rota). As rotas com require_permission continuam com a permissão específica. Nos stubs 501 (splitters, settings, occupancy) adicione as permissões corretas (`splitters:*`, `settings:*`, `network:read`) para que, quando implementados, já nasçam protegidos.
3. /dashboard/summary → exigir `reports:read`. /search → exigir autenticação (remova get_optional_current_user) e manter a regra: grupo `customers` só com `customers:read`.
4. Atualize backend/tests/integration/test_reports_dashboard_search.py: o teste que hoje afirma acesso anônimo (linha ~308) deve passar a afirmar 401 para anônimo.
DECISÃO HUMANA (me pergunte antes se algo destoar): se existir necessidade real de painel público, pare e me consulte; o padrão é NÃO ter.
Critérios: anônimo → 401 em /dashboard/summary e /search; teste de varredura passa e falha se uma rota nova nascer sem auth.
```

#### R04 — PII de clientes (SEC-03, SEC-04 · Issue 3)

```text
Siga o Prompt-base. Tarefa: Issue 3 (SEC-03, SEC-04). Pré-requisito: R03 integrada.
A permissão `customers:read/write` existe em core/permissions.py (engineer/admin) mas nenhuma rota a exige; as rotas /customers e /service-links usam `network:read/write`, então `viewer` lista nome/telefone/e-mail/endereço. Além disso technician (que tem attachments:read e audit:read, mas não customers:read) lê anexos de customer/service_link e o `changes` da auditoria com phone/email/address.
1. Testes primeiro (falhando): matriz papel×rota — viewer e technician recebem 403 em GET/POST/PATCH/DELETE de /customers e /service-links; technician não lista/baixa anexos com entity_type customer|service_link; GET /audit-events para technician não devolve phone/email/address.
2. Troque as dependências para customers:read/customers:write em todas as rotas de clientes e vínculos (avalie /structures/{id}/cto-occupancy: só mude se expuser dados pessoais).
3. Anexos: em list/get/download/thumbnail, se a entidade dona for customer/service_link exigir também customers:read (filtrar na listagem; 403 nos demais).
4. Auditoria: mascarar phone/email/address em `changes` para quem não tem customers:read (ou remover esses campos do payload gravado e guardar só as chaves alteradas — escolha e justifique; não reescreva eventos antigos sem me perguntar).
5. Adicione um teste "toda permissão declarada em ROLE_PERMISSIONS é exigida por ao menos uma rota" (lista de exceções explícita e comentada para as que só existirão depois).
Critérios: os do achado SEC-03/SEC-04 em findings.json. Não altere o frontend nesta etapa.
```

#### R05 — Segredos e configuração (SEC-05, SEC-02, EST-17 · Issues 4 e 2)

```text
Siga o Prompt-base. Tarefa: Issues 4 e 2 (SEC-05, SEC-02, EST-17).
Problemas: (a) defaults públicos de SECRET_KEY, CSRF_SECRET, METRICS_SECRET_TOKEN em config.py e no compose (`${VAR:-default}`), inclusive senha do banco, e nada rejeita isso em produção; (b) o compose injeta METRICS_TOKEN mas a config lê METRICS_SECRET_TOKEN, então o token efetivo é o default; a comparação usa ==; (c) SECRET_KEY, CSRF_SECRET, METRICS_ENABLED, MAX_TRACE_HOPS não são lidos por ninguém.
1. Testes primeiro (backend/tests/unit/test_config.py): com ENVIRONMENT=production, Settings() deve levantar erro se SECRET_KEY/CSRF_SECRET/METRICS_SECRET_TOKEN forem defaults conhecidos, curtos (<32) ou vazios; em test/development continua permitido. Teste que `Settings` aceita o nome usado no compose (METRICS_TOKEN via validation_alias) ou que o compose usa o nome canônico — escolha UM e deixe consistente.
2. Implemente um model_validator em Settings; use hmac.compare_digest no verify_metrics_access; /metrics só é registrado/servido se METRICS_ENABLED.
3. compose.yaml: segredos sem default (`${VAR:?defina VAR}`), inclusive POSTGRES_PASSWORD; ajuste .env.example para placeholders óbvios que a validação de produção rejeita; atualize docs/runbooks/deployment-and-maintenance.md.
4. Para as configs mortas: SECRET_KEY/CSRF_SECRET serão usadas na R09 (CSRF assinado) — deixe-as declaradas, mas comente isso; MAX_TRACE_HOPS será aplicada na R14. Remova só o que for realmente inútil (DEBUG?) e justifique.
5. Não exponha /metrics no Caddyfile nesta etapa (a R17 trata do proxy); apenas registre no PR que isso é pendência.
Critérios: produção recusa defaults; token de métricas do compose é efetivo; nenhum segredo literal novo no repo.
```

#### R06 — Tetos de entrada e rate limit (EST-11 · Issue 18)

```text
Siga o Prompt-base. Tarefa: Issue 18 (EST-11).
Problemas: CableCreate.fiber_count tem ge=1 sem teto (create_cable instancia uma linha ORM por fibra: medido 40 mil fibras = 5,9 s e +125 MiB); listas e textos sem max (cable_segment_ids, cut_fiber_ids, notes…); uploads são lidos inteiros em memória antes de checar o limite; nenhum limite de corpo no Caddy; só o login tem rate limit.
1. Testes primeiro: POST /cables com fiber_count=1_000_000 → 422; fiber_count/tube_count acima do teto → 422; listas acima do teto → 422; textos acima do teto → 422.
2. Defina tetos em schemas/cables.py e nos demais schemas (valores razoáveis para FTTH, configuráveis, ex.: fiber_count ≤ 1728, tube_count ≤ 144; listas ≤ 500; notes ≤ 5000; campos de Customer alinhados às colunas VARCHAR).
3. Caddyfile: `request_body { max_size }` coerente com MAX_UPLOAD_SIZE_BYTES e com o limite de importação (20 MB).
4. Rate limit: implemente uma dependência reutilizável `rate_limit(nome, limite, janela)` com 429 + Retry-After, aplicada a /topology/trace, /topology/impact, /optical/budgets, /optical/simulations, /search, uploads e exportações.
DECISÃO HUMANA: o backend roda hoje em 1 processo. Proponha (e implemente a mais simples) entre: limitador em memória por processo com interface substituível; limitador em Postgres; plugin de rate limit no Caddy. Documente a limitação (por réplica) e me peça confirmação antes de escolher se envolver nova dependência.
Não trate aqui a leitura em streaming do upload de imagem (R07).
Critérios: os do achado EST-11; 429 em teste de estouro de limite.
```

#### R07 — Upload de imagem (PERF-04 · Issue 25)

```text
Siga o Prompt-base. Tarefa: Issue 25 (PERF-04).
`upload_attachment` é `async def` mas executa Pillow/IO/DB síncronos (bloqueia o event loop). Medido: PNG 9400×9400 (100 KiB) → +339 MiB e 0,67 s; PNG 14000×14000 (23 KiB) → DecompressionBombError não capturado → HTTP 500 com o arquivo original já gravado em disco.
Use docs/security-audit/tools/measure4.py como medição antes/depois (não o modifique; copie se precisar).
1. Testes primeiro: (a) PNG com >25 Mpx (configurável) → 422 SEM decodificar (verifique via tracemalloc/RSS ou mock) e SEM criar arquivo em storage; (b) PNG de 14000×14000 → 422, não 500; (c) upload normal continua 201 com miniatura; (d) /health/live responde < 100 ms durante um upload grande (thread paralela).
2. Implemente: handler `def` (threadpool) ou run_in_threadpool para o trabalho pesado; ler o corpo em streaming com corte ao passar de MAX_UPLOAD_SIZE_BYTES (413); validar dimensões via Image.open(...).size antes de decodificar; capturar Image.DecompressionBombError/OSError/ValueError → 422; nada de gravar em disco antes de validar.
3. Reexecute measure4 e cole antes/depois.
A consistência disco×banco (arquivo temporário + os.replace após commit, reconciliador) é a R20 — não faça aqui.
```

#### R08 — Dashboard N+1 e índice de terminais (PERF-01, PERF-03 · Issues 23 e 26)

```text
Siga o Prompt-base. Tarefa: Issue 23 (PERF-01) e a parte PERF-03 da Issue 26.
1. PERF-01: calculate_dashboard_summary (modules/reports/service.py) faz 2 queries por CTO (medido: 2.514 statements, 1,0–1,5 s com 10.001 estruturas). Escreva primeiro um teste com contador de statements (event before_cursor_execute) que exija ≤ 10 queries com centenas de CTOs (falha hoje). Reescreva com agregação em SQL (COUNT/GROUP BY + LEFT JOIN de vínculos ativos), preservando EXATAMENTE os números atuais (teste de caracterização com o dataset do teste existente antes de mudar). Opcional: cache curto (15–30 s) invalidado pela topology_revision, se não complicar.
2. PERF-03: crie migração Alembic (com downgrade) para `CREATE INDEX CONCURRENTLY idx_terminals_entity ON terminals (entity_type, entity_id)` (use autocommit_block). Teste: o índice existe e, com enable_seqscan=off, o EXPLAIN das buscas de terminal por (entity_type, entity_id) usa Index Scan.
3. Meça antes/depois com docs/security-audit/tools/measure.py e measure2.py num Postgres descartável com o dataset sintético (backend/scripts/generate_synthetic_load.py --db-url <descartável>); cole os números.
Critérios: ≤ 10 statements; números do dashboard idênticos; índice criado e reversível.
```

### Fase 2 — Onda 2

#### R09 — Login, sessões e CSRF (SEC-06/07/08/09/18 · Issues 5 e 6)

```text
Siga o Prompt-base. Tarefa: Issues 5 e 6 (SEC-06, SEC-07, SEC-08, SEC-18, SEC-09). Pré-requisito: R05.
1. SEC-06: check_login_rate_limit conta falhas por IP OU e-mail e bloqueia antes de checar a senha → qualquer um trava a conta alheia (5 falhas) e IP compartilhado (CGNAT) bloqueia todos. Testes: 5 falhas do IP A para u@x não impedem login correto de u@x pelo IP B; sucesso reinicia a janela. Implemente limite por par (IP, e-mail) com backoff progressivo + teto por IP mais alto, sem bloquear senha correta de origem legítima.
2. SEC-07: respostas de login para inexistente, desativado e senha errada devem ser indistinguíveis (status e corpo); verifique a senha primeiro.
3. SEC-08: change_user_password e `bootstrap_admin --reset-password` devem revogar todas as outras sessões do usuário (manter a atual). Teste com 2 sessões.
4. SEC-18: só confiar em X-Forwarded-For de proxies configurados (setting, ex.: FORWARDED_ALLOW_IPS/TRUSTED_PROXIES); validar com `ipaddress`; valor inválido/longo é ignorado (usa request.client.host). Ajuste ProxyHeadersMiddleware(trusted_hosts=["*"]). Teste: XFF de 60 caracteres não gera 500.
5. SEC-09: validate_csrf deve comparar Origin por igualdade exata (esquema+host+porta), sem startswith; torne o token CSRF assinado (HMAC com CSRF_SECRET) mantendo o fluxo GET /auth/csrf + cookie + X-CSRF-Token do frontend funcionando (rode os testes do frontend). Testes: Origin `http://localhost:3000.evil.example` → 403.
Cuidado: não quebre frontend/src/lib/api/client.ts nem csrf.ts. Mudanças de contrato → regenerar contracts.
```

#### R10 — Cobertura de auditoria (EST-10, SEC-17 · Issue 12)

```text
Siga o Prompt-base. Tarefa: Issue 12 (EST-10, SEC-17). Pré-requisito: R09 (identity/service.py estável).
record_audit_event só é usado em attachments, connectivity, customers e jobs. Faltam: criar/editar/desativar usuário e mudança de papel, login/logout/troca de senha, CRUD de sites/estruturas/dispositivos/portas/cabos/segmentos, perfis e medições ópticas, settings, importações/exportações. Vários chamadores não propagam request_id.
1. Testes primeiro: teste parametrizado sobre TODAS as rotas mutantes reais (use openapi/inventario-rotas.md; exclua stubs 501 e os POSTs somente-leitura trace/impact/budgets/simulations/split-preview) exigindo exatamente 1 AuditEvent por chamada bem-sucedida, com actor_id, request_id e sem segredos/hash de senha no diff. Mostre falhando para as rotas não cobertas.
2. Desenhe um mecanismo central (dependência do FastAPI que registra ao concluir a transação, ou listener do SQLAlchemy por sessão) em vez de copiar chamadas em 40 handlers. Mostre a proposta em 10 linhas ANTES de implementar e aguarde meu OK se a abordagem for invasiva.
3. Eventos de identidade: user:created/updated/deactivated/role_changed, auth:login_succeeded/login_failed (sem gravar a senha), auth:logout, auth:password_changed.
4. Migração: tornar audit_events append-only no banco (trigger que bloqueia UPDATE/DELETE, ou REVOKE), com downgrade.
5. Atualize a descrição da rota /audit-events para refletir a cobertura real.
Pode dividir em 2 PRs (identity+exports primeiro, o resto depois). Sinalize o que ficou de fora.
```

#### R11 — Exportações e jobs (SEC-13, SEC-14 · Issue 10)

```text
Siga o Prompt-base. Tarefa: Issue 10 (SEC-13, SEC-14). Pré-requisitos: R02 e R10.
1. SEC-13: a UI afirma que exportar a camada `customers` é auditado, mas create_export_request não audita; o download exige só exports:read e não revalida o papel; arquivos em storage/exports nunca expiram (o job de retenção só limpa ImportPreview).
Testes primeiro: (a) criar exportação gera AuditEvent `export_requested` (camadas, formato, ator) e o download gera `export_downloaded`; (b) exportação com camada customers só é baixável por admin, mesmo por engineer com o job_id; (c) arquivo mais antigo que EXPORT_TTL é removido pelo worker e o download devolve 410.
Implemente com TTL configurável (default 7 dias — peça confirmação do prazo) e limpeza no loop do worker; guarde no payload do job quem pediu e as camadas.
2. SEC-14: o worker grava `job.error_message = str(e)` e /jobs/{id} o devolve a qualquer autenticado. Grave um código/mensagem sanitizada para o cliente e o detalhe só em log com job_id; GET /jobs/{id} exige exports:read ou imports:read conforme o tipo do job (viewer → 403). Teste: provocar IntegrityError e verificar que a resposta não contém SQL, nome de tabela ou caminho.
```

#### R12 — Pipeline de importação (EST-05/06/07/08 · Issue 14)

```text
Siga o Prompt-base. Tarefa: Issue 14 (EST-05, EST-06, EST-07, EST-08). Pré-requisito: R02.
1. EST-05: execute_import_commit cria `Cable(...)` mas descarta a geometria (a geometria vive em CableSegment; a tabela cables não tem geometria) e o CSV injeta coordenadas fictícias de São Paulo quando faltam. Testes primeiro: após import_commit com 1 cabo, existe ≥1 CableSegment com a geometria do arquivo; CSV de cabo sem `coordinates` → validation_status=error.
DECISÃO HUMANA: como resolver origem/destino do segmento — (a) exigir colunas/propriedades origin_code/destination_code, (b) casar por proximidade das pontas com estruturas usando ROUTE_ENDPOINT_TOLERANCE_M (como create_cable_segment faz), ou (c) rejeitar cabos sem estruturas resolvíveis. Proponha e me peça para escolher antes de implementar. Remova SEMPRE o default de coordenadas.
2. EST-06: idempotência do commit: substitua o check-then-insert por INSERT ... ON CONFLICT (idempotency_key) e compare payload.import_id (mesma chave com outro import_id → 409); escopo por usuário; limite de tamanho da chave. Teste concorrente: duas requisições simultâneas retornam o mesmo job_id, sem 500.
3. EST-07: heartbeat() nunca é chamado. Renove a lease a cada N entidades (ou thread de heartbeat) e verifique lease_owner antes de gravar o status final. Teste: job simulado de 120 s mantém lease no futuro e roda uma só vez com 2 workers.
4. EST-08: imports/service.py e exports/service.py leem settings.STORAGE_DIR (não existe). Use Path(settings.STORAGE_PATH)/'imports'|'exports' e persista caminhos relativos ao storage root. Teste com STORAGE_PATH=tmp_path.
Faça migração/script de compatibilidade se já houver caminhos relativos gravados em async_jobs/import_previews (pergunte antes se houver dados).
```

#### R13 — Concorrência otimista e split (EST-03, EST-04, EST-21 · Issue 16)

```text
Siga o Prompt-base. Tarefa: Issue 16 (EST-03, EST-04, EST-21).
1. EST-03: a validação de If-Match é check-then-act (compara em Python e depois faz version += 1; o UPDATE não tem WHERE version). Teste de concorrência primeiro (2 sessões/threads, mesmo If-Match em PATCH /sites/{id}): exatamente um 200 e um 412 — hoje ambos 200. Estenda a outros recursos (usuário, estrutura, dispositivo, porta, cabo, cliente, medição, perfil óptico) via teste parametrizado.
2. EST-21: crie um único módulo (ex.: app/core/concurrency.py) com a verificação de versão + atualização atômica (`UPDATE ... WHERE id=:id AND version=:v` verificando rowcount, ou version_id_col do SQLAlchemy) e substitua as 6 cópias (`_validate_if_match` em inventory, customers, connectivity, measurements, optical; `_check_optimistic_lock` em cables). Um teste deve falhar se surgir definição duplicada.
3. EST-04: split_cable_segment não trava o segmento, não exige If-Match nem expected_topology_revision. Teste de concorrência primeiro (2 splits no mesmo segmento): apenas um sucesso, o outro 409/412, contagem final de segmentos = 2. Implemente SELECT ... FOR UPDATE no segmento (e fibras) e exigência de If-Match OU expected_topology_revision (siga o padrão do editor de fusão). Atualize o contrato OpenAPI, api-types e frontend/src/features/cables/components/split-segment-dialog.tsx + testes do frontend.
Mantenha todas as respostas 412/428 existentes compatíveis com o frontend.
```

#### R14 — Impacto e rastreio óptico (PERF-02, PERF-14 · Issue 24)

```text
Siga o Prompt-base. Tarefa: Issue 24 (PERF-02, PERF-14). Pré-requisito: R08 (índice em terminals) e, de preferência, R06 (rate limit).
Medido: POST /topology/impact executa 62 statements por vínculo ativo (carrega todos os clientes e faz um trace completo por vínculo); trace_optical_path faz ≥5 queries por salto e copia listas por ramo.
1. PRIMEIRO escreva testes de caracterização com resultados idênticos ao atual para trace e impact (use os cenários de tests/integration/test_optical_path_tracing.py e do impacto existente); eles devem passar antes e depois.
2. Testes novos falhando: statements de /topology/impact não dependem do nº de clientes (≤ 30 com 1 e com 50 vínculos); statements do trace independem de max_hops (≤ 10 fixos).
3. Reimplemente: carregar terminais/conexões/arestas internas/fibras/splitters do subconjunto relevante em poucas queries (ou CTE recursiva) e fazer a travessia em memória; no impacto, uma travessia única a partir dos segmentos rompidos. Aplique min(max_hops, settings.MAX_TRACE_HOPS); limite max_length em cable_segment_ids; considere job assíncrono para bases grandes (só proponha).
4. Meça antes/depois com docs/security-audit/tools/measure2.py num dataset com centenas de clientes (gere no banco descartável).
Não mude o formato das respostas.
```

#### R15 — Pool, timeouts e health (PERF-12/13/10/09 · Issue 28)

```text
Siga o Prompt-base. Tarefa: Issue 28 (PERF-12, PERF-13, PERF-10, PERF-09). Pré-requisito: R05.
1. PERF-12: sem statement_timeout, 1 processo uvicorn, pool 10+20. Teste: uma query com pg_sleep(60) é cancelada em ≤ statement_timeout. Configure `connect_args` com statement_timeout e connect_timeout (settings; o worker usa valor maior/separado para importações). uvicorn com `--workers` via variável (ex.: WEB_CONCURRENCY) no CMD do backend/Dockerfile; dimensione o pool por worker e documente. ATENÇÃO: com >1 worker as métricas em memória ficam por processo (trate na R16).
   DECISÃO HUMANA: valores de statement_timeout/workers/pool — proponha e peça confirmação.
2. PERF-13: /health/ready não deve ler o diretório do Alembic a cada chamada (cacheie o head esperado no startup) e não deve depender do pool da aplicação (use conexão curta dedicada com timeout). Teste: readiness responde < 500 ms com o pool saturado.
3. PERF-10: GET /auth/me deve executar 1 SELECT (joinedload/contains_eager de UserSession.user) e last_activity_at deve ser atualizado com throttle. Teste com contador de statements.
4. PERF-09: apenas verifique que bump_topology_revision é o último passo antes do commit nas transações longas (split/import) e registre o resultado; não altere se já estiver certo.
Meça antes/depois com docs/security-audit/tools/measure5.py e cole os números.
```

#### R16 — Métricas (EST-13 · Issue 20)

```text
Siga o Prompt-base. Tarefa: Issue 20 (EST-13). Pré-requisito: R05.
RequestIDMiddleware registra request.url.path quando a rota não foi resolvida (404) e normalize_route_path só troca UUIDs/números: cada path distinto cria chaves novas para sempre em _http_requests/_http_durations (medido: +300 chaves com 300 paths). Além disso as métricas são por processo e o worker não aparece.
1. Teste primeiro: 10.000 paths 404 distintos deixam len(_http_requests) constante (falha hoje).
2. Use o rótulo fixo `__unmatched__` quando não houver rota; limite defensivo do nº de chaves.
3. Se a R15 introduziu >1 worker, implemente o modo multiprocess do prometheus_client (ou agregação equivalente) e exponha as métricas do worker de jobs; caso contrário, documente a limitação. Confirme que /metrics continua protegido (R05).
```

#### R17 — Proxy: TLS, HSTS e CSP (SEC-11 · Issue 8)

```text
Siga o Prompt-base. Tarefa: Issue 8 (SEC-11). Pré-requisito: R06 (request_body).
Hoje o Caddy escuta só em :80 com auto_https off e publica 443; o CSP tem `'unsafe-inline' 'unsafe-eval'` em script-src; não há HSTS; SECURITY.md e o runbook prometem CSP estrito e terminação TLS. O backend marca cookies Secure em produção, então sem TLS o login falha fora de localhost.
DECISÃO HUMANA (pergunte primeiro): TLS terminado no Caddy (domínio + Let's Encrypt) ou em balanceador externo? Implemente a opção escolhida e documente a outra.
1. Caddyfile parametrizado por variável (ex.: {$SITE_ADDRESS}); com TLS no Caddy: remova `auto_https off`, adicione Strict-Transport-Security; sem TLS no Caddy: documente e teste o cabeçalho X-Forwarded-Proto.
2. CSP sem unsafe-inline/unsafe-eval em script-src: gere nonce no Next.js (middleware.ts) e aplique o CSP por resposta; mantenha worker-src blob: e os hosts de tiles. Valide que MapLibre e a UI funcionam (rode o frontend em modo produção e navegue login → mapa → cabos).
3. Não exponha /api/v1/metrics no Caddy (handle dedicado retornando 404 para o exterior).
4. Alinhe SECURITY.md e o runbook ao comportamento real.
Critérios: `curl -sI` mostra CSP sem unsafe-* e HSTS (em HTTPS); UI funcional.
```

#### R18 — Supply chain e CI (EST-16, SEC-15 · Issue 11)

```text
Siga o Prompt-base. Tarefa: Issue 11 (EST-16, SEC-15). Pré-requisito: R01.
1. Frontend: `pnpm audit --json` aponta 7 advisories (maplibre-gl 5.24.0 ≤6.4.0 — crítico, alcançável só via Popup.setHTML, que o código não usa; postcss via next; vitest). Atualize maplibre-gl (≥6.4.1), next/postcss e vitest para versões corrigidas; rode testes e faça um smoke do mapa (arrastar, camadas, desenho). Liste breaking changes encontrados.
2. CI (.github/workflows/ci.yml): adicionar jobs `security` com pip-audit (uv export → pip-audit), `pnpm audit --audit-level high`, gitleaks, CodeQL, `docker compose build` e trivy nas imagens; `permissions: contents: read` no topo; fixar actions por SHA (com comentário da versão); Dependabot (.github/dependabot.yml) para pip, npm e github-actions.
3. Teste "vermelho antes": comente na PR como cada gate falharia com o estado antigo (ex.: pnpm audit com maplibre 5.24.0).
Se o upgrade de maplibre exigir mudanças grandes, pare e me mostre o custo antes.
```

#### R19 — Backup e restore (SEC-10, EST-19 · Issue 7)

```text
Siga o Prompt-base. Tarefa: Issue 7 (SEC-10, EST-19).
backend/app/core/backup_restore.py: tar.extractall sem filter em 3 pontos (path traversal), `TRUNCATE TABLE {table_name}` com o nome vindo do arquivo (SQL injection), manifesto/checksums dentro do próprio arquivo (não autenticam); fallback psycopg sem snapshot consistente; pacote sem criptografia.
1. Testes primeiro (falhando): tar com membro `../evil` → recusado; .bin com nome fora da allowlist de tabelas (`a;drop table users.bin`) → recusado antes de qualquer SQL; manifesto adulterado (assinatura inválida) → recusado; backup com escritas concorrentes restaura sem violação de FK.
2. Implemente: extractall(filter='data') + validação de nomes; allowlist via information_schema e psycopg.sql.Identifier; snapshot com transação REPEATABLE READ READ ONLY (ou exigir pg_dump -Fc); assinatura do manifesto (HMAC com chave dedicada BACKUP_SIGNING_KEY) verificada ANTES de extrair.
DECISÃO HUMANA: criptografia do pacote — age/gpg (binário externo) ou biblioteca Python? Proponha e peça confirmação.
3. Rode scripts/restore_drill.py (CI) e o backup/restore manual em banco descartável.
```

#### R20 — Uploads: consistência (EST-09 · Issue 17)

```text
Siga o Prompt-base. Tarefa: Issue 17 (EST-09). Pré-requisito: R07.
save_attachment escreve o original e a miniatura antes de db.commit(); qualquer exceção deixa arquivo órfão; reconcile_storage_orphans apaga qualquer arquivo fora do snapshot lido do banco, inclusive o de um upload ainda não commitado.
1. Testes primeiro: falha na geração da miniatura ou no commit não deixa arquivo em originals/thumbnails; reconciliador não remove arquivo com mtime < N minutos (configurável, default 15).
2. Grave em arquivo temporário e faça os.replace para o destino final somente após o commit (compensação em caso de erro); registre no banco antes do arquivo definitivo, ou GC por idade — escolha a mais simples e justifique.
```

### Fase 3 — Onda 3 / backlog

#### R21 — Escala horizontal (EST-14 · Issue 21)

```text
Siga o Prompt-base. Tarefa: Issue 21 (EST-14). Pré-requisitos: R15 e R16.
Escopo: análise + mudanças de baixo risco; NÃO implemente storage em objeto sem minha aprovação.
1. Escreva um ADR (docs/adr/0007-escala-horizontal.md) com: estado atual (1 uvicorn, container_name fixo, volume local, PostgreSQL único, métricas por processo), o que quebra com 2+ réplicas e as opções (workers, réplicas, storage S3/MinIO/NFS, backup agendado, HA do banco), recomendação e custo.
2. Implemente só o seguro: remover `container_name` do backend/worker no compose para permitir `--scale`, healthcheck do worker (se a R02 ainda não fez), agendamento de backup documentado (serviço/cron) e teste manual `docker compose up --scale backend=2`.
3. Liste o épico de storage (interface StorageBackend + backend S3) como tarefas para eu priorizar.
```

#### R22 — Importação/exportação em memória (PERF-05, PERF-08 · Issue 27)

```text
Siga o Prompt-base. Tarefa: Issue 27 (PERF-05, PERF-08). Pré-requisito: R12.
1. PERF-05: `preview_import` é async def e parseia até 20 MB de forma síncrona (bloqueia o event loop); o commit faz `db.refresh(job)` + flush por entidade. Testes primeiro: /imports/preview não bloqueia /health/live (latência < 100 ms durante o parse); import de 50 mil pontos faz ≤ 2 statements por lote de 500 (contador de statements).
   Implemente handler `def`/threadpool, limite de nº de features, checagem de cancelamento a cada N entidades e inserção em lote (bulk_insert_mappings/COPY), mantendo a semântica all-or-nothing.
2. PERF-08: exports carregam camadas inteiras com `.all()` e json.dump(indent=2). Teste: RSS do worker durante o export ≤ 2× o tamanho do arquivo (tracemalloc). Use yield_per/cursor do servidor e escrita incremental (GeoJSON/KML/CSV em streaming).
Meça antes/depois e cole os números.
```

#### R23 — Índices de busca e listagem (PERF-06, PERF-07 · Issue 26)

```text
Siga o Prompt-base. Tarefa: parte PERF-06/PERF-07 da Issue 26 (PERF-03 já foi feita na R08).
1. PERF-06: buscas `ILIKE '%q%'` em sites, estruturas, cabos, dispositivos, clientes, usuários e ports.notes. Migração com `CREATE EXTENSION IF NOT EXISTS pg_trgm` e índices GIN (gin_trgm_ops) em code/name/serial_number/notes conforme as consultas reais; escape de %, _ e \ no termo (ilike(..., escape="\\")); mínimo de 3 caracteres na busca global. Teste: as buscas retornam o mesmo resultado; plano usa Bitmap Index Scan (com enable_seqscan=off em tabela populada).
2. PERF-07: índice (created_at DESC, id) nas tabelas listadas; avalie paginação keyset SEM quebrar o contrato atual (page/page_size): se for preciso mudar o contrato, PARE e me consulte.
Meça antes/depois com docs/security-audit/tools/measure.py num dataset de 100 mil linhas.
```

#### R24 — Retenção de dados (PERF-11 · Issue 29)

```text
Siga o Prompt-base. Tarefa: Issue 29 (PERF-11). Pré-requisito: R11.
Nada remove login_attempts, sessões revogadas/expiradas nem (após R11) arquivos de exportação vencidos. Implemente no loop do worker uma rotina idempotente de retenção configurável (login_attempts 30 dias, user_sessions inválidas 7 dias — confirme os prazos comigo) e um índice composto (email, attempted_at) para o rate limit. Testes com relógio simulado: registros acima do TTL são removidos, os demais permanecem. NÃO apague audit_events.
```

#### R25 — Validação de UUID e tamanhos (EST-12 · Issue 19)

```text
Siga o Prompt-base. Tarefa: Issue 19 (EST-12).
`uuid.UUID(param)` sem tratamento em 17 pontos/14 rotas (customers, service-links, connections, structures/{id}/connectivity|cto-occupancy, topology/trace, create_service_link) causa HTTP 500; CustomerUpdate.phone/email/address não têm max_length e as colunas são VARCHAR.
1. Teste primeiro parametrizado: cada rota com ID malformado retorna 422 (hoje 500); strings acima da coluna retornam 422.
2. Tipe os parâmetros como uuid.UUID nos handlers/schemas (o FastAPI valida) e ajuste os serviços; acrescente max_length alinhado às colunas. Cuidado com o contrato OpenAPI (format uuid) e o frontend (api-types).
```

#### R26 — seed_demo (SEC-12 · Issue 9)

```text
Siga o Prompt-base. Tarefa: Issue 9 (SEC-12).
backend/scripts/seed_demo.py cria o admin admin@provedor… com senha literal do repositório e não verifica o ambiente. Faça o script abortar (exit ≠ 0, sem tocar o banco) quando ENVIRONMENT=production ou quando a URL do banco não for local sem a flag explícita `--i-know-this-is-not-prod`; gere a senha aleatoriamente e imprima-a uma única vez. Atualize a docstring e o runbook. Teste unitário primeiro (falha hoje). Faça o mesmo cheque nos outros scripts que assumem credenciais fixas (benchmark_endpoints.py, generate_synthetic_load.py) sem alterar seus fluxos de teste.
```

#### R27 — Permissões front × back (EST-20 · Issue 15)

```text
Siga o Prompt-base. Tarefa: parte EST-20 da Issue 15. Pré-requisito: R04.
A matriz de permissões está duplicada em backend/app/core/permissions.py e frontend/src/lib/permissions/rbac.ts (com divergência: `telemetry:write` só no frontend); AuthGuard/PermissionGate e o campo `permission` da navegação nunca são usados.
1. Teste de paridade primeiro (backend gera JSON da matriz; teste do frontend compara com rbac.ts) — falha hoje.
2. Gere rbac.ts a partir do backend (script) ou consuma `permissions` de /auth/me como única fonte.
3. Aplique PermissionGate nas ações de escrita (criar/editar/excluir), oculte itens de navegação sem permissão e proteja páginas administrativas com AuthGuard requiredPermission. O servidor continua sendo a autoridade: nenhuma mudança de segurança depende da UI.
```

#### R28 — Re-auditoria final (todos)

```text
Siga o Prompt-base, exceto as regras 3 e 4 (não é uma correção). Tarefa: verificar o que foi resolvido, sem editar código do projeto.
1. Escreva somente em docs/security-audit/ (arquivo novo resolucao.md).
2. Reexecute: docs/security-audit/tools/enum_routes.py e gen_inventory.py (110+ rotas: quantas ainda sem auth?), pip-audit e `pnpm audit`, e as medições docs/security-audit/tools/measure.py … measure6.py em Postgres descartável com o dataset sintético. Compare com docs/security-audit/evidencias/medicoes.md.
3. Para CADA um dos 53 IDs de findings.json: status (corrigido/parcial/pendente), commit/PR, teste que o cobre, e o novo arquivo:linha verificado no código atual. Não use verify_fidelity.py (as linhas mudaram); confirme manualmente cada trecho.
4. Liste regressões e achados novos, e as decisões humanas em aberto. Atualize o checklist da seção 6 do roteiro.
5. Confirme com `git status --porcelain` que só docs/security-audit/ foi alterado.
```

---

## 6. Checklist e cobertura por ID

**Etapas:** `[ ] R01` `[ ] R02` `[ ] R03` `[ ] R04` `[ ] R05` `[ ] R06` `[ ] R07` `[ ] R08` `[ ] R09` `[ ] R10` `[ ] R11` `[ ] R12` `[ ] R13` `[ ] R14` `[ ] R15` `[ ] R16` `[ ] R17` `[ ] R18` `[ ] R19` `[ ] R20` `[ ] R21` `[ ] R22` `[ ] R23` `[ ] R24` `[ ] R25` `[ ] R26` `[ ] R27` `[ ] R28`

| ID | Etapa | ID | Etapa | ID | Etapa |
|---|---|---|---|---|---|
| SEC-01 | R03 | EST-01 | R02 | PERF-01 | R08 |
| SEC-02 | R05 | EST-02 | R03 | PERF-02 | R14 |
| SEC-03 | R04 | EST-03 | R13 | PERF-03 | R08 |
| SEC-04 | R04 | EST-04 | R13 | PERF-04 | R07 |
| SEC-05 | R05 | EST-05 | R12 | PERF-05 | R22 |
| SEC-06 | R09 | EST-06 | R12 | PERF-06 | R23 |
| SEC-07 | R09 | EST-07 | R12 | PERF-07 | R23 |
| SEC-08 | R09 | EST-08 | R12 | PERF-08 | R22 |
| SEC-09 | R09 | EST-09 | R20 | PERF-09 | R15 |
| SEC-10 | R19 | EST-10 | R10 | PERF-10 | R15 |
| SEC-11 | R17 | EST-11 | R06 | PERF-11 | R24 |
| SEC-12 | R26 | EST-12 | R25 | PERF-12 | R15 |
| SEC-13 | R11 | EST-13 | R16 | PERF-13 | R15 |
| SEC-14 | R11 | EST-14 | R21 | PERF-14 | R14 |
| SEC-15 | R18 | EST-15 | R01 | | |
| SEC-16 | R03 + R08 + R15 | EST-16 | R18 | | |
| SEC-17 | R10 (+ R09) | EST-17 | R05 | | |
| SEC-18 | R09 | EST-18 | R02 | | |
| | | EST-19 | R19 | | |
| | | EST-20 | R27 | | |
| | | EST-21 | R13 | | |

## 7. Decisões humanas antes de começar

| Etapa | Decisão |
|---|---|
| R03 | Existe algum caso legítimo de painel/busca público? (padrão do roteiro: não) |
| R06 | Rate limit: em memória por processo, em Postgres ou no Caddy? |
| R10 | Mecanismo central de auditoria (dependência vs listener do ORM) e escopo por PR |
| R11 | Prazo de retenção das exportações (sugestão: 7 dias) |
| R12 | Como resolver origem/destino dos cabos importados (colunas, proximidade ou rejeitar) |
| R15 | Valores de `statement_timeout`, nº de workers e pool |
| R17 | TLS no Caddy ou em balanceador externo |
| R18 | Aceitar o custo do upgrade major do maplibre-gl |
| R19 | Ferramenta de criptografia do backup (age/gpg/biblioteca) |
| R21 | Storage de anexos para multi-réplica (S3/MinIO/NFS) |
| R24 | Prazos de retenção de `login_attempts` e sessões |

## 8. Dicas de execução

- **Sessões curtas:** uma etapa por sessão evita contexto misturado; se o prompt ficar grande demais, divida a etapa (R10 já prevê 2 PRs).
- **Revisão:** `/code-review high` no diff da branch e `/security-review` nas etapas de segurança (R03–R05, R09–R11, R17, R19).
- **Se um teste da issue não puder falhar antes** (ex.: comportamento já corrigido por outra etapa), o Claude deve dizer isso explicitamente em vez de inventar um teste.
- **Pontos de fusão:** ao integrar R05→R06→R07→R09→R15 (todos tocam `core/config.py`), resolva os conflitos na ordem da tabela da seção 3.
- **Não pule a R28:** ela é o único jeito de provar, com evidência atual, que os 53 achados foram tratados.
