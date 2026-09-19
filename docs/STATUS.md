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

Resultado da re-auditoria: **50 achados corrigidos, 3 parciais, 0 pendentes**; rotas sem autenticação de 18 para 8 (todas intencionais). Backend: 534 testes passando localmente; frontend: 180.

## 2. O que está acontecendo agora

**CI do GitHub Actions na `master` ainda não está verde.** Situação do último PR (#2):

| Job | Situação |
|---|---|
| Frontend (lint, typecheck, vitest, build) | verde |
| Security (pip-audit, pnpm audit, gitleaks) | verde (após dar `pull-requests: read` ao job) |
| Docker (compose build + Trivy) | verde (após incluir `BACKUP_SIGNING_KEY` no ambiente do job) |
| Backend (ruff, mypy, migrações, pytest) | **falha em 5 testes no runner** (abaixo) |
| CodeQL (python e javascript-typescript) | análise roda; o upload do resultado falhava por permissão — foi adicionado `actions: read`; **resultado da correção ainda não verificado** (em repositório privado, o CodeQL pode exigir GitHub Advanced Security) |

Testes do backend que falham só no CI (todos passam localmente, inclusive contra a mesma imagem `postgis/postgis:16-3.4`):

- `test_gis_map_features.py::test_spatial_bbox_query_and_gist_index` e três de `test_import_pipeline.py` (`…resolves_endpoints_by_proximity`, `…match_structures_already_in_the_database`, `…without_resolvable_structures…`): HTTP 500 com `no spatial operator found for 'st_intersects': opfamily … type …` numa consulta `ST_Intersects(sites.location, …)`. Não reproduzido isoladamente; depende de estado acumulado na execução completa (`--cov -v`). Próximo passo: rodar a suíte inteira contra um Postgres idêntico ao do CI e comparar os índices de `sites`.
- `test_import_export_scale.py::test_import_preview_does_not_block_health_probe`: 0,22 s contra limite de 0,1 s — teste de tempo sensível ao runner lento; folgar o limite ou torná-lo relativo.

A `master` já tinha CI falhando antes das correções (o job de backend parava no `ruff`), então esses testes nunca haviam rodado no GitHub.

Dependabot: as atualizações de versão foram **desligadas** (`open-pull-requests-limit: 0`) para manter só a branch principal. Alertas de segurança seguem nas configurações do repositório.

## 3. O que ficou para trás

**Achados parciais**

- PERF-09 — o `UPDATE network_topology_state` (linha única) ainda serializa escritas de topologia; mitigado (é o último passo antes do commit; `statement_timeout`), sem advisory lock/sequence.
- EST-14 — escala horizontal: ADR + compose escalável prontos; falta storage compartilhado de anexos (S3/MinIO/NFS) para multi-réplica de verdade.
- EST-17 — `SECRET_KEY` continua declarada/validada mas sem uso; comentário em `backend/app/core/config.py:52-53` desatualizado. Remover ou usar.

**Bugs e riscos encontrados (fora dos 53)**

- `DELETE /customers/{id}` responde 500 quando há vínculos históricos (FK não tratada).
- Diálogo de dividir segmento envia o número da fibra em vez do UUID em `cut_fiber_ids` (agora vira 422).
- Permissões definidas sem rota que as exija (`cables:*`, `connectivity:*`, `topology:*`, `map:read`) — decisão de produto.
- `generate_thumbnail_image`/`inspect_file_content` não limitam pixels sozinhas (o limite está no upload).
- Rate limit em memória por processo (efetivo ×2 com `WEB_CONCURRENCY=2`, zera a cada restart).

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
