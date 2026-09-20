# Matriz de Rastreabilidade: Requisitos vs Testes Automatizados

Esta matriz mapeia cada fase de desenvolvimento (Backend B01–B18 e Frontend F01–F20) aos respectivos arquivos de teste unitário, de integração, de contrato e scripts de validação automatizada.

---

## 1. Matriz de Requisitos Backend (B01 – B18)

| Fase | Requisito Principal | Testes e Scripts de Validação | Status | Cobertura / Verificação |
|:---|:---|:---|:---:|:---|
| **B01** | Fundação, runtime e concorrência | `tests/unit/test_config.py`<br>`tests/unit/test_logging.py`<br>`tests/unit/test_domain_isolation.py`<br>`tests/integration/test_health_real_db.py` | ✅ PASS | Healthchecks `/health/live` e `/health/ready`, isolamento de camadas sem DB, redaction de dados sensíveis e JSON logging estruturado. |
| **B02** | Contrato compartilhado e OpenAPI | `tests/contract/test_openapi_schema.py`<br>`tests/contract/test_request_id.py`<br>`tests/contract/test_synthetic_examples.py` | ✅ PASS | Detecção de drift contra `contracts/openapi.json`, unicidade de `operationId`, conformidade RFC 7807 e validação de unidades físicas (`*_m`, `*_db`, etc.). |
| **B03** | Sessões, usuários, permissões e configurações | `tests/integration/test_auth.py`<br>`tests/integration/test_users.py`<br>`tests/integration/test_splitters_settings_occupancy.py`<br>`tests/unit/test_cli_bootstrap.py` | ✅ PASS | Login/logout seguro, proteção CSRF dupla, mitigação de enumeração por tempo, rate limiting PostgreSQL, configurações persistidas/versionadas, proteção do último admin e CLI de bootstrap. |
| **B04** | Inventário físico e migrações | `tests/integration/test_inventory_sites.py`<br>`tests/integration/test_inventory_structures.py`<br>`tests/integration/test_inventory_devices_ports.py`<br>`tests/integration/test_optical_profiles.py`<br>`tests/integration/test_migration_lifecycle.py` | ✅ PASS | Check constraints de localização de Device e proprietário de Port, limites de OpticalProfile, concorrência otimista `If-Match` e rollback bidirecional de migrações. |
| **B05** | Motor GIS e malha de mapas | `tests/integration/test_gis_map_features.py`<br>`tests/unit/test_gis_helpers.py` | ✅ PASS | Consultas espaciais GiST com bounding box, fórmula de Haversine, validação de tolerância de ancoragem e cabeçalhos de truncamento espacial. |
| **B06** | Cabos, fibras e segmentação | `tests/integration/test_cables_segments.py`<br>`tests/unit/test_cable_catalogs.py` | ✅ PASS | Segmentação de cabos, divisão com preservação de continuidade (split), catálogos industriais ABNT NBR, TIA-598-C e DIN VDE. |
| **B07** | Conectividade e motor de fusões | `tests/integration/test_connectivity_engine.py` | ✅ PASS | Normalização de terminais $2N$, lote atômico de fusões, validação de `expected_topology_revision` com 409 Conflict, reversão de reservas de terminais. |
| **B08** | Splitters, CTOs e atendimento | `tests/integration/test_splitters_settings_occupancy.py`<br>`tests/integration/test_customers_service_links.py` | ✅ PASS | CRUD de splitters com terminais e perdas por comprimento de onda, ocupação de estruturas/CTOs e vínculos de atendimento. |
| **B09** | Clientes, atendimentos e drops | `tests/integration/test_customers_service_links.py` | ✅ PASS | Vínculo operacional Cliente-Porta-ONU, exclusividade de portas ativas via índice único condicional e relatório de ocupação de CTOs. |
| **B10** | Orçamento óptico teórico | `tests/integration/test_optical_budget.py`<br>`tests/unit/test_optical_calculator.py` | ✅ PASS | Cálculo ponta a ponta segundo ITU-T G.984/G.9807, atenuação acumulada, detecção de sobrecarga óptica (`overload`) e margem de engenharia. |
| **B11** | Medições ópticas de campo | `tests/integration/test_optical_measurements.py` | ✅ PASS | CRUD de medições, concorrência otimista, cálculo de perda excessiva (`excess_loss_db`) e isolamento por comprimento de onda. |
| **B12** | Simulações e análise de corte | `tests/integration/test_optical_simulations.py`<br>`tests/integration/test_full_lifecycle_b18.py` | ✅ PASS | Simulações what-if com substituição virtual de parâmetros e endpoint `/api/v1/topology/impact` com identificação precisa de clientes e CTOs afetados. |
| **B13** | Relatórios, ocupação e busca | `tests/integration/test_reports_dashboard_search.py` | ✅ PASS | Dashboard com alertas de degradação, relatórios de ocupação de CTOs e cabos, detecção de inconsistências topológicas e busca textual global. |
| **B14** | Exportação, importação e jobs | `tests/integration/test_imports_exports_jobs.py` | ✅ PASS | Exportação assíncrona GeoJSON/CSV, importação com detecção e rejeição atômica de colisões e processamento de jobs assíncronos via worker. |
| **B15** | Fotos, anexos e trilha de auditoria | `tests/integration/test_attachments_audit.py` | ✅ PASS | Validação de magic bytes de imagens/documentos, sanitização de path traversal, isolamento RBAC de download e auditoria append-only com antes/depois. |
| **B16** | Carga sintética e benchmark | `backend/scripts/benchmark_endpoints.py`<br>`tests/integration/test_performance_observability.py`<br>`docs/benchmark-b16.md` | ✅ PASS | Benchmark com 10.000 estruturas e 100.000 fibras: BBox p95 < 11ms (meta < 1s), Trace p95 < 12ms (meta < 2s), métricas Prometheus/JSON e sem inanição. |
| **B17** | Implantação, backup e manutenção | `backend/scripts/restore_drill.py`<br>`backend/scripts/backup.py`<br>`backend/scripts/restore.py`<br>`compose.yaml` | ✅ PASS | Compose multi-serviço com PostGIS em rede privada, migração atômica, backup consistente com manifesto SHA256 e Restore Drill 100% aprovado. |
| **B18** | Auditoria final e entrega open source | `tests/integration/test_full_lifecycle_b18.py`<br>`backend/scripts/seed_demo.py`<br>`docs/audit-b18.md` | ✅ PASS | Jornada transversal ponta a ponta (10 passos), seed CLI idempotente e determinístico, CI workflow com PostGIS e catálogo completo de documentação. |

---

## 2. Matriz de Requisitos Frontend (F01 – F20)

| Fase | Requisito Principal | Arquivos de Teste Vitest | Status | Verificação |
|:---|:---|:---|:---:|:---|
| **F01** | Setup Next.js, layout e design system | `tests/app-shell-navigation.test.tsx` | ✅ PASS | AppShell, tema escuro/claro, tokens Tailwind e layout responsivo. |
| **F02** | Contrato e cliente de API tipado | `tests/api-client.test.ts` | ✅ PASS | Cliente fetch com tipagem do OpenAPI, injeção de CSRF e tratamento de RFC 7807. |
| **F03** | Autenticação, sessão e RBAC UI | `tests/auth-rbac.test.tsx` | ✅ PASS | Login/logout, controle de permissões por perfil, desabilitação/ocultação de ações restritas. |
| **F04** | Navegação, feedback e banner offline | `tests/app-shell-navigation.test.tsx` | ✅ PASS | Banner de conectividade, indicador de rascunhos pendentes e navegação fluida. |
| **F05** | CRUD de inventário de rede | `tests/network-inventory-crud.test.tsx` | ✅ PASS | Listagem, formulários com validação Zod e concorrência otimista com If-Match. |
| **F06** | Mapa operacional MapLibre GL | `tests/operational-map.test.tsx` | ✅ PASS | Renderização de camadas GeoJSON (sites, estruturas, cabos) e filtros por status. |
| **F07** | Ferramentas de desenho geográfico | `tests/drawing-geographic-editor.test.tsx` | ✅ PASS | Modos de desenho pontual e linear com snapping a estruturas existentes. |
| **F08** | Cabos, tubos e código de cores | `tests/cables-fibers-segmentation.test.tsx` | ✅ PASS | Visualização de tubos e fibras com cores conforme norma ABNT NBR 14106. |
| **F09** | Diálogo de divisão de cabos (split) | `tests/cables-fibers-segmentation.test.tsx` | ✅ PASS | Inserção de estrutura intermediária e preservação de continuidades de fibra. |
| **F10** | Editor de fusões e lotes | `tests/fusion-connectivity-editor.test.tsx` | ✅ PASS | Rascunho local de fusões, submissão em lote com `expected_topology_revision` e tratamento de 409. |
| **F11** | Rastreamento óptico visual | `tests/topology-path-tracing.test.tsx` | ✅ PASS | Destaque geográfico da rota óptica no mapa e painel com tabela de perdas acumuladas. |
| **F12** | Clientes e atendimentos | `tests/customers-service-links.test.tsx` | ✅ PASS | Ativação/desativação de vínculos de clientes e status de ocupação das portas da CTO. |
| **F13** | Painel de orçamento óptico | `tests/optical-budget.test.tsx` | ✅ PASS | Badges de conformidade (Pass, Low Margin, Overload), margem de engenharia e gráficos. |
| **F14** | Medições e simulações ópticas | `tests/optical-measurements-and-simulations.test.tsx` | ✅ PASS | Formulário de medição de campo e simulador what-if com delta de perda. |
| **F15** | Fotos, documentos e auditoria | `tests/attachments-and-audit.test.tsx` | ✅ PASS | Galeria de fotos, visualizador modal de anexos e timeline de auditoria antes/depois. |
| **F16** | Dashboard executivo e relatórios | `tests/dashboard-search.test.tsx`<br>`tests/reports-capacity.test.tsx` | ✅ PASS | Indicadores operacionais, gráficos de ocupação de CTOs e cabos, e busca global. |
| **F17** | Assistentes de import/export, configurações e usuários | `tests/imports-exports-wizard.test.tsx`<br>`tests/settings-users.test.tsx`<br>`tests/splitters-management.test.tsx` | ✅ PASS | Wizard de exportação GeoJSON/CSV, importação com preview, parâmetros persistidos, gestão de splitters e usuários. |
| **F18** | Acessibilidade e modo campo | `tests/field-accessibility-performance.test.tsx` | ✅ PASS | Contraste elevado, alvos de toque $\ge 44 \times 44$ px, teclado acessível e performance. |
| **F19** | Testes integrados e qualidade frontend | Todas as suítes (24 arquivos, 183 testes) | ✅ PASS | Execução limpa e determinística do Vitest sem regressões. |
| **F20** | Entrega e validação de produto | Revisão funcional e ausência de dead-ends | ✅ PASS | Todos os botões, diálogos e navegações conectados a APIs reais ou mocks fiéis. |
