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

Resultado: **51 achados corrigidos, 2 parciais (PERF-09, EST-14), 0 pendentes**; rotas sem autenticação de 18 para 8 (todas intencionais). Backend: 531 testes localmente (530 passam com `pg_dump`/`pg_restore` no PATH + 1 que só roda sem eles; 534 antes do adendo, menos 7 casos de `SECRET_KEY` removidos e mais 4 novos); frontend: 181.

## 2. O que está acontecendo agora

Fechamento das pendências que não dependiam de decisão de produto, mesclado na `master` em 19/09/2026 (branch `fix/pendencias-auditoria`, fast-forward). Detalhe em `docs/security-audit/resolucao.md` §7.

**CI vermelho na `master` — causa encontrada e corrigida.** Os 4 testes espaciais falhavam porque `restore_backup` usava `pg_restore --clean`, que **recria a extensão PostGIS** e deixa as conexões já abertas com o cache de tipos antigo (`no spatial operator found … opfamily`). Só aparecia no GitHub porque a máquina local não tem `pg_dump`/`pg_restore` e caía no dump binário do psycopg. Como afetava também a restauração real com a API no ar, a correção está no código (`_write_restore_list` filtra a extensão do sumário), não só no teste. O teste de tempo do health probe ganhou margem (1,5 s de bloqueio simulado, teto 0,5 s).

**Falta:** conferir o resultado do CI desta `master` (ainda não executado no GitHub após a correção) e confirmar o CodeQL (em repositório privado pode exigir GitHub Advanced Security). Dependabot: atualizações de versão desligadas (`open-pull-requests-limit: 0`); alertas de segurança seguem nas configurações do repositório.

## 3. O que ficou para trás

**Achados parciais (dependem de decisão)**

- PERF-09 — o `UPDATE network_topology_state` (linha única) ainda serializa escritas de topologia; mitigado (é o último passo antes do commit; `statement_timeout`), sem advisory lock/sequence.
- EST-14 — escala horizontal: ADR + compose escalável prontos; falta storage compartilhado de anexos (S3/MinIO/NFS) para multi-réplica de verdade.

**Riscos conhecidos**

- Permissões definidas sem rota que as exija (`cables:*`, `connectivity:*`, `topology:*`, `map:read`) — decisão de produto (N-03).
- Rate limit em memória por processo (efetivo ×2 com `WEB_CONCURRENCY=2`, zera a cada restart) — aceito (N-05).

**Verificações que exigem ambiente real (não feitas)**

- Smoke manual do mapa com `maplibre-gl` 6 no navegador.
- CSP/nonce e HSTS num navegador com domínio e TLS reais.
- `docker compose --scale` com storage compartilhado.
- Revisão de código/segurança do diff (`/code-review`, `/security-review`), recomendada antes de considerar concluído.

## 4. Decisões assumidas (confirmar)

Sem painel/busca públicos; rate limit em memória por processo (interface trocável); auditoria por listeners da Session; exportações expiram em 7 dias; cabos importados resolvem pontas por código → proximidade → erro; 2 workers, pool 5+5 e `statement_timeout` 30 s (worker 10 min); TLS no Caddy (balanceador externo documentado); upgrade do maplibre-gl 6; backup cifrado por `cryptography` (AES-256-GCM); retenção de 30 dias (`login_attempts`) e 7 dias (sessões inválidas), `audit_events` sem retenção; R21 só ADR.

## 5. Incidente de processo (registrado por transparência)

Durante a R26, um teste meu executou `benchmark_endpoints.py` **antes** de ele ter a guarda de ambiente e ele gravou 1 usuário e 3 sessões no banco de desenvolvimento local (container `ftth_db`, porta 5432). Os registros foram removidos e o banco voltou ao estado anterior (vazio). A guarda atual impede a repetição. Além disso, sem `TEST_DATABASE_URL` a suíte de testes usa `127.0.0.1:5432/ftth_manager_test` por padrão — defina a variável para apontar para um banco descartável.

## 6. Ambiente local

Containers descartáveis ainda ativos na máquina: `ftth-test-pg` (porta 55433, testes) e `ftth-audit-pg` (55432, medições). Podem ser removidos com `docker rm -f`.
