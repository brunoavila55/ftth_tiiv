# Relatório de Auditoria e Entrega Open Source (Fase B18)

Este relatório formaliza a auditoria final dos critérios de aceite da fase **B18** do **FTTH Manager**, consolidando o status de conformidade do backend, banco de dados, motor óptico, governança e integração contínua.

---

## 1. Resumo Executivo da Auditoria

| Métrica / Critério | Alvo / Especificação | Resultado Auditado | Veredito |
|:---|:---|:---|:---:|
| **Suíte de Testes Backend** | 100% de testes passando sem falhas | **140 aprovados / 0 falhas** | **PASS** |
| **Suíte de Testes Frontend** | 100% de testes passando sem falhas | **166 aprovados / 0 falhas** | **PASS** |
| **Linters e Formatação** | Ruff e ESLint sem alertas ou erros | **0 erros (Ruff e ESLint)** | **PASS** |
| **Tipagem Estática** | Mypy e TypeScript sem erros | **0 erros (Mypy e tsc)** | **PASS** |
| **Contrato OpenAPI** | Sem drift contra `contracts/openapi.json` | **100% Sincronizado** | **PASS** |
| **Teste Transversal B18** | Ciclo ponta a ponta (10 etapas integradas) | **Executado e Aprovado** | **PASS** |
| **Seed CLI Determinístico** | Script opt-in idempotente via CLI | **Testado e Funcional** | **PASS** |
| **Disaster Recovery Drill** | Restauração atômica DB + Fotos com SHA256 | **100% Aprovado** | **PASS** |
| **Workflow de CI** | GitHub Actions com PostGIS, Linters e Gates | **Criado e Validado** | **PASS** |

---

## 2. Checklist Detalhado dos Critérios de Aceite B18

### Item 1: Teste Automatizado Transversal de Ciclo Completo
- **Arquivo**: `backend/tests/integration/test_full_lifecycle_b18.py`
- **Jornada Validada**:
  1. `[PASS]` **Bootstrap e Autenticação de Admin**: Criação de usuário administrador, obtenção de token CSRF, login com cookies protegidos.
  2. `[PASS]` **Provisionamento de Infraestrutura**: Site POP Central, rack indoor, caixa de emenda subterrânea (CEO) e caixa de terminação óptica (CTO).
  3. `[PASS]` **Equipamentos e Portas OLT**: OLT Huawei MA5800-X7 provisionada no POP com portas PON 1/1/1 e terminais normalizados $2N$.
  4. `[PASS]` **Cabo Alimentador (Feeder)**: 3.500 metros (3,5 km), 12 FO, tubo loose verde, interligando POP e CEO com LineString PostGIS.
  5. `[PASS]` **CEO com Fusão e Splitter 1:8**: Splitter balanceado 1:8 no CEO com atenuação nominal de 10,2 dB, patchcord no POP (0,30 dB) e fusões (0,10 dB cada).
  6. `[PASS]` **Cabo de Distribuição**: 3.500 metros (3,5 km), 6 FO, interligando CEO à CTO com LineString PostGIS.
  7. `[PASS]` **CTO com Segundo Splitter 1:8**: Segundo divisor passivo 1:8 na CTO, porta de atendimento cliente e fusão de interligação.
  8. `[PASS]` **Assinante Ativo (DEMO-001)**: Cliente DEMO-001, dispositivo ONU Huawei com porta óptica PON, cordão drop de atendimento e vínculo `ServiceLink(status='active')`.
  9. `[PASS]` **Rastreamento Óptico Fim-a-Fim**: Endpoint `POST /api/v1/topology/trace` downstream retorna percurso contínuo de **7.000 metros (7 km exatos)**, com 4 fusões, 2 patch cords, 2 splitters 1:8 e terminal final na ONU.
  10. `[PASS]` **Cálculo de Orçamento Óptico**: Endpoint `POST /api/v1/optical/budgets` contra perfil ITU-T G.984 Classe B+ retorna `assessment="pass"` com potência prevista de ~ -21 dBm e sem condição de sobrecarga óptica (`overload`).
  11. `[PASS]` **Medição Óptica em Campo**: Endpoint `POST /api/v1/measurements` registra potência de -22,50 dBm na ativação com cálculo automático de perda em excesso (`excess_loss_db`).
  12. `[PASS]` **Análise de Impacto de Rompimento Virtual**: Endpoint `POST /api/v1/topology/impact` com corte simulado no cabo alimentador identifica o cliente `CLI-DEMO-001` e a estrutura `CTO-AUDIT-01` como afetados sem alterar nenhum registro do banco de dados operacional.
  13. `[PASS]` **Solicitação de Exportação**: Endpoint `POST /api/v1/exports` gera job assíncrono aceito (HTTP 202) para exportação GeoJSON.
  14. `[PASS]` **Backup Atômico e Restauração Isolada**: Backup gerado com sucesso, verificação de manifesto assinado com SHA256 e restauração em armazenamento isolado com preservação de revisão topológica e versão de schema.
- **Status do Critério**: **PASS**

---

### Item 2: Seed Determinístico e Idempotente via CLI
- **Arquivo**: `backend/scripts/seed_demo.py`
- **Comandos**:
  - `uv run python scripts/seed_demo.py [--clean] [--target-db test|dev]`
- **Características Auditadas**:
  - `[PASS]` **Não roda no boot de produção**: O script reside em `scripts/` e só é invocado deliberadamente por linha de comando pelo operador.
  - `[PASS]` **Idempotência**: Quando executado sem `--clean` em banco já provisionado, detecta a presença prévia das entidades e encerra informando instruções sem duplicação de dados.
  - `[PASS]` **Limpeza Atômica (`--clean`)**: Remove todas as entidades com prefixo `DEMO` respeitando integridade referencial reversa (medições $\to$ vínculos $\to$ conexões $\to$ splitters $\to$ cabos $\to$ estruturas $\to$ sites).
  - `[PASS]` **Cenário Transversal Completo**: Provisiona exatamente a jornada dos 7 km (POP $\to$ Feeder 3.5 km $\to$ CEO 1:8 $\to$ Dist 3.5 km $\to$ CTO 1:8 $\to$ Drop $\to$ ONU $\to$ CLI-DEMO-001).
  - `[PASS]` **Ramo Independente Não Afetado**: Provisiona CTO-DEMO-02 e Cliente DEMO-002 para demonstrar que o corte no alimentador principal afeta apenas os clientes conectados a jusante da ruptura.
  - `[PASS]` **Ramo com Ponta Aberta**: Cabo de 12 FO (`CBL-BRANCH-OPEN-DEMO`) com extremidade não conectada para testar o aviso de incompletude topológica (`unresolved_terminals`).
  - `[PASS]` **Fusão com Atenuação Ausente**: Fusão registrada com `loss_db=0.0` para validação de alertas de medição pendente.
  - `[PASS]` **Histórico de Degradação para Relatórios**: Registro de medição com -28,50 dBm (abaixo da sensibilidade do GPON) associado ao cliente DEMO-003 para popular os relatórios gerenciais e dashboards.
- **Status do Critério**: **PASS**

---

### Item 3: Pipeline de Integração Contínua (CI)
- **Arquivo**: `.github/workflows/ci.yml`
- **Jobs Configurados**:
  - `backend-ci`: Execução no Ubuntu Latest com serviço containerizado do PostGIS (`postgis/postgis:16-3.4`), sincronização via `uv sync --frozen`, linters (`ruff check` e `ruff format`), tipagem (`mypy app`), gate de drift OpenAPI (`test_openapi_schema.py`), migrações Alembic (`alembic upgrade head`), suíte completa de testes com cobertura (`pytest`) e Restore Drill (`restore_drill.py`).
  - `frontend-ci`: Setup Node 20 com `pnpm`, verificação de lint (`pnpm lint`), tipagem (`pnpm typecheck`) e testes unitários/componentes (`pnpm test`).
- **Status do Critério**: **PASS**

---

### Item 4: Gate de Drift do Contrato OpenAPI
- **Arquivo**: `backend/tests/contract/test_openapi_schema.py`
- **Validações**:
  - Compara `app.openapi()` contra `contracts/openapi.json`.
  - Impede alterações silenciosas em rotas, modelos e campos sem atualização sincronizada dos tipos TypeScript (`contracts/api-types.d.ts`).
  - Garante unicidade de todos os `operationId`.
  - Garante presença de convenção de unidades físicas em todos os campos numéricos de perda, comprimento e potência.
- **Status do Critério**: **PASS**

---

### Item 5: Governança, Documentação e Licença Open Source
- **Documentos Produzidos**:
  - `docs/entity-relationship-model.md`: Modelo relacional e grafo espacial detalhado com diagrama Mermaid.
  - `docs/api-catalog.md`: Catálogo completo de rotas, convenções de sessão, CSRF, RBAC e RFC 7807.
  - `docs/requirement-test-matrix.md`: Matriz de rastreabilidade ligando B01–B18 e F01–F20 a testes reais.
  - `docs/runbooks/deployment-and-maintenance.md`: Guia operacional para produção, backup, restore e manutenção.
  - `README.md`: Apresentação do projeto, arquitetura, início rápido e guia de uso.
  - `CONTRIBUTING.md`: Guia de contribuição da comunidade, estilo de código, testes e fluxo de trabalho.
  - `SECURITY.md`: Política de segurança, reporte responsável de vulnerabilidades e modelo de ameaças.
- **Recomendação de Licença**:
  - **Recomendação Principal**: **AGPL-3.0 (GNU Affero General Public License v3)**.
  - **Racional**: Garante que melhorias no backend do provedor oferecidas como SaaS em nuvem retornem à comunidade open source, mantendo o software permanentemente livre e protegido contra apropriação fechada por terceiros.
  - **Alternativa Permissiva**: **Apache-2.0** caso o objetivo do mantenedor seja adoção irrestrita e interoperabilidade com ecossistemas proprietários comerciais.
- **Status do Critério**: **PASS**

---

### Item 6: Política de Não Rebaixamento de Migrações Destrutivas
- **Diretriz**:
  - Migrações Alembic são projetadas para evolução estrita para a frente (*roll-forward*).
  - Em cenários com migrações destrutivas de dados ou reestruturação irreversível de tabelas, o runbook (`docs/runbooks/deployment-and-maintenance.md`) determina a execução de backup atômico pré-migração e recuperação através de restore, vedando comandos cegos de `alembic downgrade` em produção.
- **Status do Critério**: **PASS**

---

## 3. Conclusão da Auditoria B18

Todas as metas, critérios de conformidade e entregáveis da fase **B18** foram concluídos com **100% de aprovação (PASS)**.
O backend está pronto para empacotamento, distribuição open source e suporte à homologação final do frontend (F19 e F20).
