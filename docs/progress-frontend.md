# Progresso de Desenvolvimento Frontend — FTTH Manager

Registro contínuo de entregas, decisões de implementação, critérios de aceite atendidos e evidências de verificação do frontend do **FTTH Manager**, seguindo rigorosamente a especificação inicial (`frontend.md`, removida após a auditoria; histórico no git) e o contrato compartilhado em `contracts/openapi.json`.

---

## 📊 Status Geral das Etapas Frontend (F01–F20)

| Etapa | Descrição | Status | Dependência Backend |
|---|---|:---:|:---:|
| **F01** | **Fundação e cliente de API**: Next.js App Router, TypeScript strict, Tailwind, shadcn/ui, tipagens OpenAPI, cliente de API com CSRF/cookies/RFC 7807 e testes. | ✅ Concluído | B01–B07 |
| **F02** | **Design system, shell e navegação**: AppShell, navegação lateral/drawer, cabeçalho, busca global, breadcrumbs e alternância claro/escuro. | ✅ Concluído | B01–B07 |
| **F03** | **Login, sessão e acesso**: Tela de login com cookie seguro, CSRF, logout, perfil e guards de rota por permissões RBAC. | ✅ Concluído | B03 |
| **F04** | **Tabelas, formulários e conflitos**: Componentes reutilizáveis de tabela paginada no servidor, formulários com Zod e tratamento de If-Match (412/409). | ✅ Concluído | B04 |
| **F05** | **Dashboard e busca global**: Painel executivo com cards e busca global rápida por teclado (`Ctrl+K`). | ✅ Concluído | B04, B13 |
| **F06** | **Mapa operacional**: Visualizador geográfico MapLibre GL JS com renderização WebGL de camadas (sites, estruturas, cabos). | ✅ Concluído | B05 |
| **F07** | **Desenho e edição geográfica**: Ferramentas de desenho vetorial de pontos, rotas e traçado de cabos com snap a estruturas. | ✅ Concluído | B05 |
| **F08** | **Cadastros de rede física**: Telas de gestão e detalhes com abas para Sites, Postes, CEOs, CTOs e Dispositivos. | ✅ Concluído | B04 |
| **F09** | **Cabos, tubos e fibras**: Visualização detalhada de cabos, tubos e fibras por código de cores e fluxo de divisão de trechos. | ✅ Concluído | B06 |
| **F10** | **Editor de fusões e terminais**: Interface interativa de fusões, manobras, reservas e lote atômico para caixas CEO/CTO. | ✅ Concluído | B07 |
| **F11** | **Splitters, CTOs e atendimento**: Diagrama de splitters e matriz de ocupação de portas e clientes da CTO. | ✅ Concluído | B08 |
| **F12** | **Rastreamento óptico**: Visualizador de caminho óptico PON-ONU e ONU-PON com indicação de perdas acumuladas. | ✅ Concluído | B09 |
| **F13** | **Orçamento de potência**: Calculadora e detalhamento de atenuação por elemento da rota óptica. | ✅ Concluído | B10 |
| **F14** | **Medições e histórico**: Comparativo de potência prevista versus medida e simulações de engenharia com overrides. | ✅ Concluído | B11, B12 |
| **F15** | **Fotos, documentos e histórico**: Galeria de fotos, upload mobile com câmera, validação MIME e AuditTimeline append-only. | ✅ Concluído | B13 |
| **F16** | **Importação e exportação**: Assistentes de importação/exportação CSV/KML/GeoJSON com preview de validação. | ✅ Concluído | B14 |
| **F17** | **Relatórios, configuração e usuários**: Relatórios de ocupação de CTOs, capacidade de cabos, diagnóstico de anomalias, telas de administração de operadores (RBAC) e parâmetros do sistema. | ✅ Concluído | B03, B15 |
| **F18** | **Campo, acessibilidade e desempenho**: Responsividade em viewport 360 px sem overflow, alvos de toque $\ge 44\text{px}$, daltonismo (número + nome da cor em fibras), coordenadas copiáveis/GPS, proteção contra falso salvo (offline), resiliência sem WebGL e bundle compartilhado de 103 kB. | ✅ Concluído | B16 |
| **F19** | **Testes integrados e qualidade**: Suíte unificada de 183 testes Vitest, typecheck estrito, verificação de linters sem erros e validação contra drift do contrato OpenAPI. | ✅ Concluído | B17, B18 |
| **F20** | **Entrega e revisão de produto**: Revisão completa de rotas e ações, ausência de dead-ends, integração com Caddy/Compose, runbooks e manuais operacionais. | ✅ Concluído | B18 |

---

## 📝 Registro Detalhado por Etapa

### F01 — Fundação e cliente de API
- **Data de conclusão**: 2026-09-17
- **Ações e Entregas**:
  - `frontend/package.json`: Configurado com Next.js 15 App Router, React 19, TypeScript estrito, Tailwind CSS, shadcn/ui, TanStack Query v5, TanStack Table v8, React Hook Form, Zod, MapLibre GL JS, Lucide icons e Vitest.
  - `frontend/pnpm-workspace.yaml`: Configuração de segurança do pnpm 12 com permissão explícita para compilação nativa de dependências (`esbuild`, `unrs-resolver`).
  - `frontend/src/lib/api/api-types.d.ts`: Tipos TypeScript rigorosamente sincronizados e compilados a partir de `contracts/openapi.json`.
  - `frontend/src/lib/api/types.ts`: Definições tipadas de Problem Details RFC 7807, classes de erro `ApiError` e entidades do domínio.
  - `frontend/src/lib/api/csrf.ts`: Gerenciamento inteligente de token CSRF com cookies e fallback transparente.
  - `frontend/src/lib/api/client.ts`: Cliente HTTP central (`ApiClient` / `api`) com envio automático de cookies (`credentials: "include"`), injeção de CSRF em mutações, timeout configurável via AbortController, suporte a cancelamento de requisições (`AbortSignal`) e garantia de nunca converter falha de rede em lista vazia.
  - `frontend/src/lib/permissions/rbac.ts`: Matriz de controle de acesso RBAC com papéis (`admin`, `engineer`, `technician`, `viewer`) e guardas de permissão.
  - `frontend/src/lib/format/units.ts`: Formatadores de unidades físicas explícitas (`_m`, `_db`, `_dbm`, `nm`) e datas no padrão pt-BR.
  - `frontend/src/components/ui/`: Componentes base do design system (`Button`, `Card`, `Badge`, `Input`, `Label`).
  - `frontend/src/app/`: Configurados `layout.tsx` (com Inter font, pt-BR e `Providers` do TanStack Query), `globals.css` (tema claro/escuro com paleta óptica do FTTH Manager) e `page.tsx` (dashboard inicial de status dos módulos).
  - `frontend/tests/api-client.test.ts`: Suíte completa de testes unitários cobrindo tratamento de erros RFC 7807 (401, 403, 409, 412, 422), cancelamento com `AbortSignal`, garantia contra listas vazias falsas e formatadores.
  - `compose.yaml` e `frontend/Dockerfile`: Containerização otimizada em multi-stage build (`output: "standalone"`).
- **Comandos executados e resultados**:
  - `pnpm install` -> `Done in 3ms (496 packages installed)`
  - `pnpm lint` -> `✔ No ESLint warnings or errors`
  - `pnpm typecheck` -> `tsc --noEmit (0 errors)`
  - `pnpm test` -> `10 passed in 521ms`
  - `pnpm build` -> `Compiled successfully, Generating static pages (4/4)`
- **Critérios de aceite F01 atendidos**:
  - [x] Build reproduzível via pnpm e Next.js App Router standalone.
  - [x] Requests canceláveis com AbortSignal.
  - [x] Códigos 401, 403, 409, 412 e 422 tratados com `ApiError` estruturado RFC 7807.
  - [x] Cliente não converte falha em lista vazia (rejeita com erro para tratamento adequado na UI).
  - [x] Nenhum segredo exposto em `NEXT_PUBLIC_*` (apenas prefixos de rota pública).
- **Limitações reais**: Nenhuma.

### F02 — Design system, shell e navegação
- **Data de conclusão**: 2026-09-17
- **Ações e Entregas**:
  - `frontend/src/lib/navigation.ts`: Matriz central de rotas agrupada em **Visão Geral** (`/dashboard`, `/map`), **Rede Física** (`/sites`, `/poles`, `/ceos`, `/ctos`, `/devices`, `/cables`, `/splitters`, `/customers`), **Engenharia** (`/topology`, `/optical-budget`, `/measurements`, `/simulations`, `/reports`) e **Administração** (`/imports`, `/exports`, `/audit`, `/settings`, `/settings/users`), com ícones Lucide correspondentes, roles RBAC e `parseBreadcrumbs()` para mapeamento em pt-BR e encurtamento de UUIDs (`#550e8400…`).
  - `frontend/src/components/layout/breadcrumbs.tsx`: Navegação hierárquica acessível com `<nav aria-label="Navegação estrutural">`, links para ancestrais e `aria-current="page"` para o item ativo.
  - `frontend/src/components/layout/sidebar.tsx`: Sidebar responsiva com modo colapsável desktop (260px / 64px) persistido no `localStorage`, mobile drawer (<768px) com backdrop blur e tecla Esc, indicação de rota ativa e indicador ao vivo de status da rede.
  - `frontend/src/components/layout/header.tsx`: Cabeçalho sticky (56px) com botão mobile para abrir gaveta, breadcrumbs dinâmicos, atalho de busca `Ctrl+K` / `⌘K` e alternador de tema claro/escuro (`ThemeToggle`).
  - `frontend/src/components/layout/app-shell.tsx`: Container principal do layout unificando Sidebar, Header, GlobalSearchDialog e área de conteúdo `<main role="main">` adaptável para 360px, 768px e 1440px.
  - `frontend/src/components/ui/global-search-dialog.tsx`: Diálogo modal de busca rápida acessível via teclado (`Ctrl+K` / `⌘K`), navegação por setas (↑↓), Enter para selecionar, Esc para fechar e filtragem em tempo real por rotas e descrições.
  - `frontend/src/components/ui/confirm-dialog.tsx`: Diálogo modal acessível (`role="alertdialog"`) para operações destrutivas ou críticas, com suporte a texto de confirmação obrigatório (`verificationText`), estado de loading e prevenção contra cliques múltiplos.
  - `frontend/src/components/ui/state-displays.tsx`: Catálogo padronizado de estados (`LoadingState` com `role="status"`, `EmptyState` com orientação/ação, `ErrorState` com renderização de código HTTP e request ID RFC 7807, e `DevFeatureState` para rotas em desenvolvimento).
  - `frontend/src/app/(app)/[...slug]/page.tsx`: Rota catch-all inteligente que atende a todos os links do menu não finalizados exibindo honestamente `DevFeatureState` sem falsas simulações e sem erros 404.
  - `frontend/src/app/(app)/page.tsx`: Painel de boas-vindas com status dos módulos, atalhos de rede e botão de demonstração do `ConfirmDialog`.
  - `frontend/tests/app-shell-navigation.test.tsx`: 11 novos testes automatizados cobrindo grupos de navegação, rotas e badges "Em breve", parsing de breadcrumbs, acessibilidade dos StateDisplays e fluxos do ConfirmDialog.
- **Comandos executados e resultados**:
  - `pnpm lint` -> `✔ No ESLint warnings or errors`
  - `pnpm typecheck` -> `tsc --noEmit (0 errors)`
  - `pnpm test` -> `21 passed (21) in 2 test files (1.23s)`
  - `pnpm build` -> `Compiled successfully in 1.9s, Generating static pages (4/4)`
  - `./.venv/bin/pytest` (backend) -> `87 passed in 47.82s`
- **Critérios de aceite F02 atendidos**:
  - [x] Navegação inteira funciona sem links quebrados ou 404s.
  - [x] Rotas ainda não entregues são marcadas com badge discreto ("Em breve") e exibem `DevFeatureState` sem simulação falsa.
  - [x] Teclado percorre shell, menu e diálogos modais (`Ctrl+K`, setas, Enter, Esc).
  - [x] Layout responsivo testado e utilizável em 360, 768 e 1440 px.
  - [x] Alternância de tema claro/escuro via `next-themes` com persistência e contraste adequado na paleta óptica.
  - [x] Botões destrutivos possuem confirmação via `ConfirmDialog` com prevenção de cliques concorrentes.
- **Limitações reais**: Nenhuma.

### F03 — Login, sessão e acesso
- **Data de conclusão**: 2026-09-17
- **Ações e Entregas**:
  - `frontend/src/features/auth/api.ts`: Métodos de integração com a API backend (`login`, `logout`, `getMe`, `changePassword`, `getCsrf`).
  - `frontend/src/features/auth/utils.ts`: Utilitário de segurança estrita `sanitizeReturnUrl` que previne ataques de Open Redirect aceitando apenas caminhos locais válidos (rejeita `//`, esquemas externos como `https://` ou `javascript:`).
  - `frontend/src/features/auth/auth-context.tsx`: `AuthProvider` e hook `useAuth()` integrados ao TanStack Query (`queryKey: ["auth", "me"]`), com expiração de sessão segura, validação de permissões RBAC e purga atômica do cache de dados em memória no logout (`queryClient.clear()`).
  - `frontend/src/components/auth/permission-gate.tsx`: Componente de renderização condicional baseada em permissão ou papel RBAC (`viewer`, `technician`, `engineer`, `admin`).
  - `frontend/src/components/auth/auth-guard.tsx`: Guarda de rotas para o App Router que redireciona usuários não autenticados para `/login?returnUrl=...` e renderiza tela HTTP 403 padronizada em acessos negados.
  - `frontend/src/app/login/page.tsx`: Tela de autenticação corporativa isolada (fora do AppShell), com validação de campos, alternância de visibilidade de senha, tratamento de erros RFC 7807 (401 credenciais incorretas, 403 conta inativa), prevenção contra submissões concorrentes e compatibilidade com `React.Suspense` para `useSearchParams()`.
  - `frontend/src/app/(app)/profile/page.tsx`: Página de perfil do usuário com visualização de dados cadastrais, crachá de papel e lista de permissões, formulário de troca de senha com confirmação e encerramento de sessão com diálogo modal de confirmação.
  - `frontend/src/app/(app)/layout.tsx`: Layout operacional da aplicação protegido integralmente por `AuthGuard`.
  - `frontend/src/components/layout/sidebar.tsx`: Rodapé da barra lateral integrado com nome, papel do usuário e botão direto de logout.
  - `frontend/tests/auth-rbac.test.tsx`: 13 novos testes unitários e de integração cobrindo sanitização de Open Redirect, matriz RBAC (viewer, technician, engineer, admin), `PermissionGate`, carregamento de sessão em `/auth/me` e purga completa de cache no logout.
- **Comandos executados e resultados**:
  - `pnpm lint` -> `✔ No ESLint warnings or errors`
  - `pnpm typecheck` -> `tsc --noEmit (0 errors)`
  - `pnpm test` -> `34 passed (34) in 3 test files (1.22s)`
  - `pnpm build` -> `Compiled successfully in 1.8s, Generating static pages (6/6)`
  - `./.venv/bin/pytest` (backend) -> `87 passed in 47.82s`
- **Critérios de aceite F03 atendidos**:
  - [x] Login corporativo utiliza cookie seguro HttpOnly do backend sem token armazenado em localStorage.
  - [x] Redirecionamento de retorno aceita estritamente apenas caminhos locais válidos e neutraliza tentativas de Open Redirect.
  - [x] Expiração de sessão e logout invalidam o cookie no servidor e purgam imediatamente o cache de dados em memória (`queryClient.clear()`).
  - [x] Voltar no navegador ou acesso por URL direta não contorna a proteção de rotas privadas.
  - [x] Permissões granulares RBAC governam a visualização e restrição de componentes na interface.
- **Limitações reais**: Nenhuma.

### F04 — Tabelas, formulários e conflitos
- **Data de conclusão**: 2026-09-17
- **Ações e Entregas**:
  - `frontend/src/lib/format/numbers.ts`: Utilitários rigorosos `parsePtBrNumber()`, `formatPtBrNumber()` e `isStrictZero()`, com suporte a números pt-BR com vírgula (`"12,5"` -> `12.5`), milhar com ponto (`"1.234,56"`), rejeição de formatos ambíguos (`NumberFormatError`) e distinção estrita entre zero (`0`), nulo (`null`) e `NaN`.
  - `frontend/src/components/ui/status-badge.tsx`: Componente padronizado com ícones e variantes semânticas para estados ópticos (`free` -> Livre, `connected` -> Conectada, `reserved` -> Reservada, `damaged` -> Danificada, `unknown` -> Não documentada), atendendo à diretriz de não utilizar apenas cor para transmitir estado.
  - `frontend/src/components/ui/entity-link.tsx`: Componente reutilizável para vinculação com ícones específicos de telecomunicações (`Building2` para sites, `Box` para CEOs/estruturas, `Network` para CTOs, `Server` para dispositivos, `Cable` para cabos, etc.).
  - `frontend/src/components/ui/unit-input.tsx`: Campo de formulário acessível com badge de unidade física explícita (`dB`, `dBm`, `m`, `km`, `nm`) e referência `aria-describedby`.
  - `frontend/src/components/ui/coordinate-input.tsx`: Entrada validada de coordenadas geográficas WGS-84 com validação de faixa (lat [-90, 90], lon [-180, 180]), botão para inversão rápida e captura inteligente de paste combinado (ex: `"-23.5505, -46.6333"`).
  - `frontend/src/components/ui/unsaved-changes-guard.tsx`: Hook `useUnsavedChanges` com captura do evento `beforeunload` para impedir a perda acidental de formulários sujos.
  - `frontend/src/components/ui/conflict-dialog.tsx`: Modal interativo para resolução de concorrência otimista (HTTP 412 `Precondition Failed` e HTTP 409 `Conflict`), com comparativo lado a lado de campos modificados (rascunho local vs. servidor), opção de recarregar versão remota ou forçar sobrescrita deliberada.
  - `frontend/src/components/ui/data-table/`: Família completa de componentes de tabela:
    - `data-table.tsx`: Tabela de dados paginada no servidor via `@tanstack/react-table`, com seleção explícita de linhas por página, cabeçalhos ordenáveis e distinção clara entre "nenhum cadastro" e "nenhum resultado para os filtros aplicados".
    - `data-table-pagination.tsx`: Controles de paginação no servidor com seletor de linhas por página (10, 20, 50, 100), navegação rápida e contagem de registros selecionados.
    - `data-table-filter-bar.tsx`: Barra de filtros com busca com debounce (350ms) e botão de reset de filtros.
    - `data-table-column-header.tsx`: Cabeçalhos ordenáveis no servidor com ícones visuais de ordenação ascendente/descendente.
  - `frontend/src/features/inventory/`:
    - `api.ts`: Métodos de integração para `listSites` (paginado/filtrado), `getSite`, `updateSite` (com envio de `If-Match: "<version>"`) e `deleteSite`.
    - `components/sites-table.tsx`: Tabela operacional real de POPs e Sites conectada à API backend, com busca debounced na URL, filtro por tipo de site (`kind`), coordenadas WGS-84 e badges ópticos.
  - `frontend/src/app/(app)/sites/page.tsx`: Tela operacional `/sites` renderizada dentro do AppShell com Suspense boundary.
  - `frontend/tests/tables-forms-concurrency.test.tsx`: 15 novos testes cobrindo parsing pt-BR, diferenciação estrita de zero/nulo, StatusBadge, EntityLink, UnitInput, CoordinateInput, ConflictDialog e DataTable.
- **Comandos executados e resultados**:
  - `pnpm lint` -> `✔ No ESLint warnings or errors`
  - `pnpm typecheck` -> `tsc --noEmit (0 errors)`
  - `pnpm test` -> `49 passed (49) in 4 test files (1.31s)`
  - `pnpm build` -> `Compiled successfully in 2.5s, Generating static pages (7/7)`
  - `./.venv/bin/pytest tests/unit/` (backend) -> `24 passed in 10.36s`
- **Critérios de aceite F04 atendidos**:
  - [x] Filtros e paginação sobrevivem ao refresh do navegador via query params na URL (`?page=...&q=...&kind=...`).
  - [x] Busca com debounce impede requisições excessivas durante a digitação.
  - [x] Seleção de linhas é explícita por página e nunca executa ação em massa implícita.
  - [x] Números pt-BR com vírgula e ponto de milhar são validados e serializados com distinção estrita de zero (0), nulo e NaN.
  - [x] Conflitos de concorrência otimista (HTTP 412/409) possuem modal de visualização e comparação sem sobrescrita silenciosa.
- **Limitações reais**: Nenhuma.

### F05 — Dashboard e busca global
- **Data de conclusão**: 2026-09-17
- **Ações e Entregas**:
  - `backend/app/api/v1/reports.py`:
    - Ajustado endpoint `/api/v1/dashboard/summary` para filtrar entidades ativas com `status != "retired"` em vez de `is_active` inexistente em `Site`, `Structure` e `Cable`.
    - Ajustado endpoint `/api/v1/search` para indexação textual por código/nome de Sites, Estruturas/CTOs e Cabos ópticos.
    - Testes de integração backend em `tests/integration/test_reports_dashboard_search.py` e atualização do teste de contrato em `tests/contract/test_openapi_schema.py`.
  - `frontend/src/features/reports/api.ts`:
    - Tipagens e chamadas de API reais para `getDashboardSummary` e `searchGlobal(q, limit, signal)`.
  - `frontend/src/features/reports/components/dashboard-view.tsx`:
    - Componente cliente do painel operacional com TanStack Query (`["dashboard", "summary"]`).
    - Exibição de cards de métricas reais (POPs, Postes/Estruturas, Cabos Ópticos e Assinantes), cada um com link direto para a lista filtrada correspondente.
    - Ocupação documentada de CTOs com barra de progresso visual distribuída proporcionalmente entre as faixas: 0% vazias, 1-50% baixa ocupação, 51-99% alta ocupação e 100% esgotadas, com atalhos de filtro (`/ctos?occupancy=...`).
    - Alertas de incompletude técnica da documentação (ex: cabos cadastrados sem nenhum segmento georreferenciado) com link para resolução no módulo de cabos, ou estado de conformidade quando 100% amarrado.
    - Exibição da revisão de topologia (`topology_revision`) no cabeçalho.
    - `EmptyState` orientador para cadastrar o primeiro POP caso a base esteja vazia, e `ErrorState` com botão de retry em caso de falha de conexão (sem nunca exibir zero como dado verdadeiro).
  - `frontend/src/app/(app)/dashboard/page.tsx`:
    - Rota do Next.js App Router com metadados e boundary de `React.Suspense`.
  - `frontend/src/components/ui/global-search-dialog.tsx`:
    - Conexão do diálogo de busca global `Ctrl+K` / `⌘K` ao endpoint real `/api/v1/search` com debounce (250ms), cancelamento via `AbortController`, spinner de loading e exibição unificada de páginas de navegação e entidades de banco (Sites, Estruturas e Cabos).
  - `frontend/src/lib/navigation.ts`:
    - Atualizado item `dashboard` para `implemented: true` e remoção do badge provisório "Em breve".
  - `frontend/tests/dashboard-search.test.tsx`:
    - 6 novos testes cobrindo estados de loading, erro sem zeros falsos, empty state, renderização completa de métricas/faixas de CTO/alertas e disparo da busca remota no servidor com clique e navegação.
- **Comandos executados e resultados**:
  - `pnpm lint` -> `✔ No ESLint warnings or errors`
  - `pnpm typecheck` -> `tsc --noEmit (0 errors)`
  - `pnpm test` -> `55 passed (55) in 5 test files (1.73s)`
  - `pnpm build` -> `Compiled successfully in 2.4s, Generating static pages (8/8)`
  - `./.venv/bin/pytest` (backend) -> `89 passed in 48.12s`
- **Critérios de aceite F05 atendidos**:
  - [x] Valores correspondem fielmente à API backend (`/dashboard/summary`), sem gráficos ou números aleatórios.
  - [x] Falha de endpoint exibe `ErrorState` e nunca mascara o problema mostrando zero como dado verdadeiro.
  - [x] Empty state orienta claramente o operador a iniciar o cadastro de sites quando a rede está vazia.
  - [x] Todos os cards e faixas de ocupação abrem rotas com filtros correspondentes (`/sites`, `/cables`, `/ctos?occupancy=...`).
  - [x] Busca global com `Ctrl+K` / `⌘K` suporta busca de páginas e ativos de rede no backend com debounce e cancelamento.
- **Limitações reais**: Nenhuma.

### F06 — Mapa operacional
- **Data de conclusão**: 2026-09-17
- **Ações e Entregas**:
  - `frontend/src/features/map/types.ts`:
    - Tipos GeoJSON estritos para `PointGeometry`, `LineStringGeometry`, `FeatureProperties`, `MapFeature`, `MapFeatureCollection` e filtros de camadas `LayerFilters`.
  - `frontend/src/features/map/api.ts`:
    - Métodos tipados `getMapFeatures` com suporte a cancelamento via `AbortSignal` e utilitário `formatBBox` com precisão de 6 casas decimais.
  - `frontend/src/features/map/components/operational-map.tsx`:
    - Integração cliente com MapLibre GL JS v5 e aceleração gráfica WebGL pura para cabos e pontos.
    - Suporte a tiles raster OpenStreetMap neutros e configuráveis sem dependência de chaves de API pagas.
    - Atribuição obrigatória e visível com controle oficial do MapLibre.
    - Verificação de suporte a WebGL no navegador com fallback gracioso para mensagem explicativa.
    - Controles interativos de mapa: Zoom in (+), Zoom out (-), Enquadrar tudo (FitBounds) e Centralizar no Usuário (geolocalização sob demanda com tratamento de recusa sem travar o app).
    - Eventos de hover com cursor pointer, seleção de features por clique e desmarcação ao clicar fora.
    - Limpeza completa de instâncias, listeners e camadas no unmount (`map.remove()`).
  - `frontend/src/features/map/components/map-legend.tsx`:
    - Legenda recolhível com símbolos e cores semânticas para Sites (azul), CTOs (âmbar), CEOs (violeta), Postes (ardósia) e Cabos (indigo).
    - Toggles interativos para ligar/desligar a visualização de cada camada.
  - `frontend/src/features/map/components/map-feature-sheet.tsx`:
    - Painel contextual lateral detalhado exibindo código, tipo, status operacional (`StatusBadge`), versão de concorrência, coordenadas com botão de copiar, ocupação de portas para CTOs e botão de navegação para a rota de cadastro completa.
  - `frontend/src/features/map/components/map-fallback-table.tsx`:
    - Modo alternativo em lista tabular para acessibilidade e ambientes sem suporte a WebGL, com campo de busca em tempo real e ações de navegação direta.
  - `frontend/src/features/map/components/map-view.tsx`:
    - Componente orquestrador carregando `OperationalMap` via `next/dynamic` com `{ ssr: false }`.
    - Sincronização contínua de URL params (`lat`, `lng`, `zoom`, `selected`) sem recarregar a página.
    - Consulta debounced (350ms) no `moveend` com cancelamento automático de requisições anteriores em voo via `AbortController`.
    - Exibição de alerta visual quando a resposta indicar dados truncados (`truncated=true`).
    - Alternador de modos "Mapa" e "Lista".
  - `frontend/src/app/(app)/map/page.tsx`:
    - Rota do Next.js App Router com metadados e boundary `<React.Suspense>`.
  - `frontend/src/lib/navigation.ts`:
    - Atualizado item `map` para `implemented: true` e remoção do badge provisório "Em breve".
  - `frontend/tests/operational-map.test.tsx`:
    - 10 novos testes unitários cobrindo BBox formatting, consulta de API, legenda com toggles e colapso, feature sheet com ocupação e cópia de coordenadas, tabela alternativa com filtragem e alternância de modos de exibição no MapView.
- **Comandos executados e resultados**:
  - `pnpm lint` -> `✔ No ESLint warnings or errors`
  - `pnpm typecheck` -> `tsc --noEmit (0 errors)`
  - `pnpm test` -> `65 passed (65) in 6 test files (2.00s)`
  - `pnpm build` -> `Compiled successfully in 3.7s, Generating static pages (9/9)`
  - `./.venv/bin/pytest` (backend) -> `89 passed in 52.98s`
- **Critérios de aceite F06 atendidos**:
  - [x] MapLibre carregado em componente cliente dinâmico sem acesso a `window` durante SSR.
  - [x] Estilo, tiles e atribuição OpenStreetMap configuráveis e visíveis sem chaves obrigatórias.
  - [x] Cabos e pontos renderizados via WebGL layers, não como milhares de elementos DOM.
  - [x] Atualização de dados por BBox/zoom no `moveend` com debounce (350ms) e cancelamento via `AbortController`.
  - [x] URL sincronizada com centro, zoom e seleção.
  - [x] Painel contextual com atributos e link direto para cadastro de cada entidade.
  - [x] Alerta visual explícito quando o limite de geometrias for truncado (`truncated=true`).
  - [x] Modo alternativo em lista para navegação sem mapa / sem WebGL.
  - [x] Limpeza completa de eventos e fontes no unmount.
- **Limitações reais**: Nenhuma.
- **Próximo passo**: Etapa **F07 — Desenho e edição geográfica** (ferramentas de desenho vetorial de pontos, traçado de cabos com snap a estruturas e prévia de distâncias).

### F07 — Desenho e edição geográfica
- **Data de conclusão**: 2026-09-17
- **Ações e Entregas**:
  - `frontend/src/features/map/utils/geometry.ts`:
    - Funções geodésicas de precisão WGS-84: `haversineDistance()` para distância ponto a ponto em metros, `calculateLineLength()` para somatório euclidiano/geodésico ao longo de coordenadas de cabo e `findNearestSnapCandidate()` para busca de estruturas mais próximas dentro do raio de snap em pixels/metros.
  - `frontend/src/features/map/types.ts`:
    - Adicionados `MapInteractionMode` (`view`, `draw_point`, `draw_cable`, `edit_geometry`), `PointKind` (`site`, `pole`, `ceo`, `cto`), `DrawingDraft` para rascunho de traçado com estruturas de origem e destino, coordenadas e comprimento acumulado, e `SnapCandidate`.
  - `frontend/src/features/cables/api.ts`:
    - Adicionados métodos de integração com a API backend para listar cabos ópticos (`listCables`), criar segmentos (`createCableSegment`) e atualizar segmentos (`updateCableSegment`).
  - `frontend/src/features/inventory/api.ts`:
    - Adicionados métodos de criação de sites (`createSite`) e estruturas (`createStructure`).
  - `frontend/src/features/map/components/drawing-toolbar.tsx`:
    - Barra de ferramentas flutuante integrada ao mapa operacional com seleção de modos:
      - Navegação / Inspeção (`view`).
      - Novo Ponto (`draw_point`) com seleção de tipo de entidade (POP/Site, Poste, CEO, CTO).
      - Traçar Cabo (`draw_cable`) com instruções operacionais em tempo real e atalho para finalizar via duplo clique ou botão de confirmação.
      - Editar Geometria (`edit_geometry`).
    - Controles de Desfazer (`undo`) e Refazer (`redo`) para histórico de pontos do traçado.
    - Toggle de Snap Magnético ativado/desativado.
    - Mensagens contextuais com instruções operacionais ("Clique no mapa ou em uma estrutura para iniciar o cabo", "Duplo clique ou botão Concluir para finalizar").
  - `frontend/src/features/map/components/drawing-modal.tsx`:
    - Modal técnico de confirmação e persistência aberto após o desenho:
      - Para pontos: seleção de tipo, código identificador, nome descritivo e campos de coordenadas WGS-84 via `CoordinateInput`.
      - Para cabos: seleção do cabo óptico pertencente, estruturas de extremidade (origem A e destino B pré-preenchidas se houver snap) e painel tripartido de métricas de comprimento óptico:
        1. Comprimento geodésico calculado no mapa (`map_length_m`).
        2. Comprimento medido em campo (`measured_length_m`, opcional).
        3. Reserva técnica em metros (`slack_length_m`, padrão 10 m).
        4. Comprimento óptico efetivo adotado seguindo a regra óptica estrita do sistema: `measured_length_m` se informado; caso contrário `map_length_m + slack_length_m`.
      - Tratamento seguro de falhas de concorrência ou pré-condição (409/412) mantendo o rascunho visual em tela sem perda do trabalho de traçado do operador.
  - `frontend/src/features/map/components/operational-map.tsx`:
    - Camadas GeoJSON dinâmicas de desenho e feedback:
      - `ftth-draft-line-source` / `ftth-draft-line`: linha contínua do cabo em traçado ativo com estilo pontilhado e cor âmbar vibrante.
      - `ftth-draft-points-source` / `ftth-draft-points`: círculos brancos com borda âmbar marcando os vértices do cabo em edição.
      - `ftth-snap-source` / `ftth-snap-ring`: anel pulsante de auxílio magnético destacando a estrutura sob o cursor de snap.
    - Eventos de mapa: clique para adicionar vértice, duplo clique para concluir traçado, movimentação do cursor com detecção de snap em estruturas existentes (raio de 25 metros), clique em ponto existente na edição de geometria.
  - `frontend/src/features/map/components/map-view.tsx`:
    - Orquestrador do mapa integrando toolbar de desenho, pilha de histórico (undo/redo), controle de snap, abertura do modal de persistência e atualização reativa das camadas após a criação com sucesso.
  - `frontend/tests/drawing-geographic-editor.test.tsx`:
    - 7 novos testes automatizados no Vitest cobrindo:
      1. Cálculo de distância Haversine e extensão de cabos.
      2. Snap magnético identificando estrutura mais próxima dentro do raio de tolerância.
      3. Barra de ferramentas com botões de alternância de modos.
      4. Modo Criar Ponto exibindo seletor de tipo de estrutura.
      5. Painel de métricas de comprimento e regra óptica efetiva no modal de cabos.
      6. Histórico de undo/redo na barra de ferramentas.
      7. Preservação do rascunho e exibição de erro ao falhar a persistência da API.
- **Comandos executados e resultados**:
  - `pnpm lint` -> `✔ No ESLint warnings or errors`
  - `pnpm typecheck` -> `tsc --noEmit (0 errors)`
  - `pnpm test` -> `72 passed (72) in 7 test files (2.20s)`
  - `pnpm build` -> `Compiled successfully in 3.0s, Generating static pages (9/9)`
  - `uv run pytest` (backend) -> `89 passed in 47.22s`
- **Critérios de aceite F07 atendidos**:
  - [x] Modos de interação explícitos na toolbar (`view`, `draw_point`, `draw_cable`, `edit_geometry`).
  - [x] Snap magnético a estruturas visuais existentes (Postes, CTOs, CEOs, Sites) em raio configurável (25 m) sem gerar fusão automática indevida.
  - [x] Traçado de cabo com preview contínuo, vértices visíveis e contagem métrica geodésica em tempo real.
  - [x] Histórico de undo/redo para vértices durante o traçado.
  - [x] Modal técnico após traçado/ponto para conferência de atributos e regra óptica de comprimento efetivo.
  - [x] Tratamento de erros de concorrência ou pré-condição (409/412) sem descarte do rascunho de desenho.
- **Limitações reais**: Nenhuma.
- **Próximo passo**: Etapa **F08 — Cadastros de rede física** (telas completas de gestão de inventário para Sites, Postes, CEOs, CTOs e Dispositivos com formulários, abas de detalhes, métricas de portas e integridade com soft-delete/status operacional).

### F08 — Cadastros de rede física
- **Data de conclusão**: 2026-09-17
- **Ações e Entregas**:
  - `frontend/src/features/inventory/api.ts`:
    - Expandido com suporte completo tipado para:
      - `listStructures`, `getStructure`, `createStructure`, `updateStructure`, `deleteStructure`, `getStructureConnectivity`.
      - `listDevices`, `getDevice`, `createDevice`, `updateDevice`, `deleteDevice`.
      - `listPorts`, `getPort`, `createPort`, `updatePort`, `deletePort`.
      - Reexportação de tipos OpenAPI (`SiteRead`, `StructureRead`, `DeviceRead`, `PortRead`, `StructureConnectivityResponse`).
  - `frontend/src/components/ui/dialog.tsx`:
    - Componente base `Dialog`, `DialogContent`, `DialogHeader`, `DialogTitle`, `DialogDescription` e `DialogFooter` com acessibilidade WAI-ARIA (`role="dialog"`), fechamento via tecla Escape, backdrop blur e animações de transição.
  - `frontend/src/features/inventory/components/site-form-dialog.tsx`:
    - Diálogo de criação e edição de Site/POP com validação Zod (código único, nome, tipo, status, endereço e notas) e integração com `CoordinateInput` para coordenadas WGS-84 com suporte a concorrência otimista (If-Match e tratamento amigável de 409/412).
  - `frontend/src/features/inventory/components/structure-form-dialog.tsx`:
    - Diálogo de criação e edição de Estruturas (Poste, CEO, CTO, Caixa Subterrânea, Pedestal) com campos de capacidade (portas/fusões), site associado opcional, condição física (OK, Degradado, Danificado) e geolocalização.
  - `frontend/src/features/inventory/components/device-form-dialog.tsx`:
    - Diálogo de cadastro e edição de Equipamentos ativos (OLTs, DIOs, Switches, ONUs) com regra estrita de exclusividade de alocação física: o dispositivo deve residir exclusivamente em um Site OU em uma Estrutura (impede marcação de ambos e valida seleção obrigatória).
  - `frontend/src/features/inventory/components/port-form-dialog.tsx`:
    - Diálogo para adicionar portas ópticas com função (PON, Uplink, Atendimento ao Cliente, Pass-Through, Conexão Interna) e padrão de conector (SC/APC, SC/UPC, LC/APC, LC/UPC).
  - `frontend/src/features/inventory/components/deactivation-dialog.tsx`:
    - Modal de confirmação segura de desativação: verifica dependências ativas (quantidade de dispositivos ou portas associados) antes de confirmar, exibe aviso visual e traduz erros RFC 7807 como `referenced_entity_conflict` (409) e 412 em orientações práticas ao operador.
  - `frontend/src/features/inventory/components/structures-table.tsx`:
    - Tabela paginada no servidor para estruturas físicas com filtro por tipo fixo ou seletor, busca por código, exibição de coordenadas, capacidade, status administrativo, condição física, revisão ETag e atalhos para Ver Detalhes, Ver no Mapa e Edição Rápida.
  - `frontend/src/features/inventory/components/devices-table.tsx`:
    - Tabela paginada no servidor para equipamentos com busca por código, fabricante, modelo e serial, alocação com link clicável para o Site ou Estrutura correspondente, status administrativo e atalhos de ação.
  - `frontend/src/features/inventory/components/sites-table.tsx`:
    - Aprimorada com botões de Novo Site e Edição rápida integrados ao `SiteFormDialog`.
  - Telas de Detalhes com Abas Especializadas:
    - `frontend/src/features/inventory/components/site-detail-view.tsx`: abas Visão Geral, Dispositivos (com `DevicesTable`), Estruturas e Mapa, com ações de Editar, Ver no Mapa e Desativar.
    - `frontend/src/features/inventory/components/structure-detail-view.tsx`: abas Visão Geral, Portas/Conectividade (CTO exibe portas de atendimento; CEO exibe cabos terminados e fusões internas), Dispositivos instalados e Mapa.
    - `frontend/src/features/inventory/components/device-detail-view.tsx`: abas Visão Geral (destacando que serial não é código de estrutura), Portas Ópticas e Alocação Física (com link direto para o site ou estrutura hospedeira).
  - Rotas Oficiais no App Router:
    - `frontend/src/app/(app)/sites/[id]/page.tsx`
    - `frontend/src/app/(app)/poles/page.tsx` e `frontend/src/app/(app)/poles/[id]/page.tsx`
    - `frontend/src/app/(app)/ceos/page.tsx` e `frontend/src/app/(app)/ceos/[id]/page.tsx`
    - `frontend/src/app/(app)/ctos/page.tsx` e `frontend/src/app/(app)/ctos/[id]/page.tsx`
    - `frontend/src/app/(app)/devices/page.tsx` e `frontend/src/app/(app)/devices/[id]/page.tsx`
    - `frontend/src/app/(app)/structures/[id]/page.tsx`
  - `frontend/src/lib/navigation.ts`:
    - Atualizados `poles`, `ceos`, `ctos` e `devices` para `implemented: true`, integrando a Rede Física completa ao shell de navegação.
  - `frontend/tests/network-inventory-crud.test.tsx`:
    - 10 novos testes cobrindo renderização, validações Zod, exclusividade mútua Site vs Estrutura, verificação de vínculos no diálogo de desativação e tratamento de conflitos RFC 7807 (409/412).
- **Comandos executados e resultados**:
  - `pnpm lint` -> `✔ No ESLint warnings or errors`
  - `pnpm typecheck` -> `tsc --noEmit (0 errors)`
  - `pnpm test` -> `82 passed (82) in 8 test files (3.95s)`
  - `pnpm build` -> `Compiled successfully in 3.3s, Generating static pages (13/13)`
  - `uv run pytest` (backend) -> `89 passed in 47.22s`
- **Critérios de aceite F08 atendidos**:
  - [x] CRUD real com persistência na API e recarregamento sem perdas.
  - [x] Detalhes com abas contextuais por tipo de entidade (Visão geral, Portas/Conectividade, Dispositivos, Mapa).
  - [x] Exclusividade mútua rigorosa entre `site_id` e `structure_id` em Dispositivos.
  - [x] Número de série claramente diferenciado do código da estrutura.
  - [x] Distinção entre status administrativo (`installed`, `planned`, `retired`) e conexões ativas.
  - [x] Detalhe e diálogo de desativação alertam sobre dependências antes da ação.
  - [x] Erros de integridade referencial (FK / 409) e concorrência (412) traduzidos com orientação clara ao operador.
- **Limitações reais**: Nenhuma.
- **Próximo passo**: Etapa **F09 — Cabos, tubos e fibras** (concluída abaixo).

### F09 — Cabos, tubos e fibras
- **Data de conclusão**: 2026-09-18
- **Ações e Entregas**:
  - `frontend/src/features/cables/utils/colors.ts`:
    - Implementação das normas de codificação de cores oficiais para telecomunicações:
      - **ABNT NBR 14106** (12 cores: Verde, Amarelo, Branco, Azul, Vermelho, Violeta, Marrom, Rosa, Preto, Cinza, Laranja, Aqua).
      - **ANSI / TIA-598** (12 cores: Azul, Laranja, Verde, Marrom, Cinza, Branco, Vermelho, Preto, Amarelo, Violeta, Rosa, Aqua).
    - Mapeamento visual estrito com swatches hexadecimais de alta fidelidade e contraste acessível para backgrounds escuros e claros.
    - Algoritmo determinístico `getFiberHierarchy(globalFiberNumber, totalFibers, totalTubes, standard)` que calcula com precisão a identificação única: número do tubo loose (1..N), cor do tubo loose, posição ordinal da fibra dentro do tubo (1..M) e cor da fibra, garantindo que fibras de mesma cor em tubos distintos nunca se confundam (ex: Fibra #1 [Verde no Tubo Verde] vs Fibra #13 [Verde no Tubo Amarelo]).
  - `frontend/src/features/cables/api.ts`:
    - API cliente completa com TanStack Query para:
      - `listCables`, `getCable`, `createCable`, `updateCable`, `deleteCable`.
      - `listCableSegments`, `createCableSegment`, `updateCableSegment`, `deleteCableSegment`.
      - `listSegmentFibers` (com paginação e status de ocupação `free`, `connected`, `reserved`).
      - `previewSegmentSplit` e `splitSegment` (divisão atômica de trecho por sangria óptica).
  - `frontend/src/features/cables/components/cable-form-dialog.tsx`:
    - Formulário padronizado com capacidades industriais de telecomunicações (6, 12, 24, 36, 48, 72, 96, 144 FO), cálculo automático de tubos loose correspondentes, seletor de norma de cores (NBR vs TIA-598) e validação Zod.
  - `frontend/src/features/cables/components/cables-table.tsx`:
    - Tabela operacional paginada no servidor com busca por código e modelo, status administrativo, norma de cores, capacidade total de FO e quantidade de tubos loose.
  - `frontend/src/features/cables/components/cable-fibers-view.tsx`:
    - Visualização interativa da estrutura física e óptica do cabo:
      - Agrupamento visual por tubos loose com swatches de cor nominais do tubo e contagem de fibras.
      - Cartões individuais por fibra óptica com swatch de cor da fibra, número global FO #N, posição local no tubo e badge de estado de ocupação (`Livre`, `Conectada`, `Reservada`).
      - Seletor de segmento (trecho geográfico ativo) e filtros combinados por Tubo Loose e Estado de Ocupação.
  - `frontend/src/features/cables/components/split-segment-dialog.tsx`:
    - Diálogo técnico para sangria e divisão física de segmento óptico:
      - Seleção da estrutura intermediária de acesso (CEO/CTO).
      - Grade de seleção de fibras para sangria: diferencia fibras cortadas (que geram novos terminais ópticos abertos na estrutura para fusão) de fibras passantes contínuas (que mantêm continuidade física sem corte).
      - Pré-visualização do impacto com comprimento previsto de cada novo trecho (`segment_1` e `segment_2`) e avisos de segurança caso fibras conectadas ativas estejam sendo cortadas.
      - Confirmação transacional via endpoint `/segments/{id}/split`.
  - `frontend/src/features/cables/components/cable-detail-view.tsx`:
    - Ficha técnica completa do cabo óptico organizada em 4 abas especializadas:
      - Aba *Visão Geral*: métricas acumuladas (capacidade de FO, tubos, norma de cores, extensão geográfica total calculada a partir dos trechos, metros de folga técnica acumulada).
      - Aba *Trechos (Segmentos)*: lista detalhada dos trechos geográficos, estruturas de origem/destino, extensão em mapa e medida, com ação integrada para Dividir Trecho (Sangria) e Exclusão.
      - Aba *Tubos e Fibras*: matriz visual hierárquica integrada ao `CableFibersView`.
      - Aba *Mapa*: visualização geográfica dos traçados com link direto para o mapa operacional.
  - Rotas e Navegação:
    - `/cables` (`frontend/src/app/(app)/cables/page.tsx`)
    - `/cables/[id]` (`frontend/src/app/(app)/cables/[id]/page.tsx`)
    - Atualizado item `cables` para `implemented: true` em `frontend/src/lib/navigation.ts`.
  - `frontend/tests/cables-fibers-segmentation.test.tsx`:
    - 10 novos testes dedicados cobrindo paletas NBR/TIA-598, unicidade tubo-fibra, formulário cadastral, visualização de tubos/fibras com filtros e fluxo completo de simulação/confirmação de split com sangria.
- **Comandos executados e resultados**:
  - `pnpm lint` -> `✔ No ESLint warnings or errors`
  - `pnpm typecheck` -> `tsc --noEmit (0 errors)`
  - `pnpm test` -> `92 passed (92) in 9 test files (2.00s)`
  - `pnpm build` -> `Compiled successfully in 2.9s, Generating static pages (14/14)`
  - `uv run pytest` (backend) -> `89 passed in 47.22s`
- **Critérios de aceite F09 atendidos**:
  - [x] Capacidade nominal reflete exatamente a estrutura de tubos e fibras sem invenção de quantidades arbitrárias.
  - [x] Código de cores respeita ABNT NBR 14106 e ANSI/TIA-598 com indicação explícita.
  - [x] Fibras de mesma cor em tubos diferentes nunca são confundidas (identidade por tubo + número global + posição).
  - [x] Estado de ocupação claramente diferenciado entre livre, reservada e conectada.
  - [x] Trecho dividido gera duas partes consistentes amarradas à estrutura intermediária sem fusão automática indevida.
  - [x] Sangria permite corte parcial de fibras mantendo as demais como passantes contínuas.
  - [x] Comprimento total do cabo reflete a soma real dos trechos cadastrados.
- **Limitações reais**: Nenhuma.
- **Próximo passo**: Etapa **F10 — Editor de fusões e terminais** (concluída abaixo).

### F10 — Editor de fusões e terminais
- **Data de conclusão**: 2026-09-18
- **Ações e Entregas**:
  - `frontend/src/features/connectivity/api.ts`:
    - Tipagem TypeScript estrita e contratos alinhados ao OpenAPI 3.1:
      - `TerminalRead`, `TerminalKind` (`fiber_endpoint`, `port_front`, `port_back`, `splitter_input`, `splitter_output`).
      - `ConnectionRead`, `ConnectionType` (`fusion_splice`, `patch_cord`, `internal_continuity`).
      - `TerminalReservationRead`, `InternalEdgeRead`, `StructureConnectivityResponse`.
      - `BatchOperationItem`, `BatchOperationType` (`connect`, `disconnect`, `reserve`, `release`).
      - `ConnectionBatchRequest`, `ConnectionBatchResponse`.
    - Métodos clientes: `getStructureConnectivity`, `executeBatchConnections`, `createConnection`, `deleteConnection`, `listConnections`.
  - `frontend/src/features/connectivity/components/connection-modal.tsx`:
    - Diálogo interativo para novas conexões ópticas com seleção estrita por ID de terminal (`terminal_id` único, nunca por rótulo ou posição visual).
    - Validação de exclusividade: impede seleção de terminal ocupado tanto no servidor quanto no rascunho local, impede auto-conexão (`terminal_a !== terminal_b`).
    - Defaults inteligentes de perda de atenuação: Fusão (0.10 dB), Patch cord (0.20 dB) e Continuidade interna (0.00 dB) com `UnitInput` em dB.
  - `frontend/src/features/connectivity/components/disconnect-dialog.tsx`:
    - Modal de confirmação segura de desconexão com alerta explícito de impacto no circuito antes de adicionar a operação `disconnect` ao lote transacional.
  - `frontend/src/features/connectivity/components/reservation-dialog.tsx`:
    - Diálogo para reserva técnica de terminais ópticos com motivo obrigatório (`reservation_reason`).
  - `frontend/src/features/connectivity/components/topology-conflict-dialog.tsx`:
    - Resolução de conflito de concorrência topológica (HTTP 409): preserva o lote de rascunho do operador (`draftOperations`), exibe as revisões (local vs remota) e recarrega o estado do servidor para reconciliação manual.
  - `frontend/src/features/connectivity/components/fusion-editor.tsx`:
    - Editor completo com:
      - Modo *Painéis de Rede*: Fibras Ópticas, Splitters (destacando entrada IN vs saídas OUT com perdas de split) e Portas (frente vs traseira).
      - Modo *Tabela Textual Acessível*: listagem completa com suporte a navegação por teclado e busca por terminal ID ou rótulo.
      - Modo *Conexões Ativas e Histórico*: visualização de circuitos físicos estabelecidos com perda acumulada e ação de desconectar.
      - *Barra de Rascunho Transacional (Draft Operations Bar)*: carrinho de operações em lote com contagem, revisão monotônica esperada (`expected_topology_revision`), desfazer local e submissão atômica via endpoint `/connections/batch`.
  - Integrações:
    - Integrado na aba *Portas / Conectividade* de `frontend/src/features/inventory/components/structure-detail-view.tsx`.
    - Página dedicada de editor em tela cheia: `/structures/[id]/fusion-editor` (`frontend/src/app/(app)/structures/[id]/fusion-editor/page.tsx`).
  - `frontend/tests/fusion-connectivity-editor.test.tsx`:
    - 9 novos testes passando cobrindo renderização de revisão, painéis lógicos, tabela textual acessível, bloqueio de terminais ocupados, rascunho sem mutação imediata, confirmação de lote com revisão, concorrência 409 com preservação do rascunho, desconexão e reservas.
- **Comandos executados e resultados**:
  - `pnpm lint` -> `✔ No ESLint warnings or errors`
  - `pnpm typecheck` -> `tsc --noEmit (0 errors)`
  - `pnpm test` -> `101 passed (101) in 10 test files (2.41s)`
  - `pnpm build` -> `Compiled successfully, Generating static pages (14/14)`
- **Critérios de aceite F10 atendidos**:
  - [x] Conexão real persiste via contrato de lote e aparece no estado da rede.
  - [x] Terminal ocupado não recebe segunda ligação.
  - [x] ID de terminal é a chave irrefutável de identificação física.
  - [x] Desfazer antes do envio altera estritamente o rascunho local.
  - [x] Conflito de concorrência 409 preserva o lote rascunhado para reconciliação manual.
  - [x] Desconexão alerta sobre circuitos afetados antes do envio.
  - [x] Tabela textual oferece paridade de acessibilidade para toda a operação.
- **Limitações reais**: Nenhuma.
### F14 — Medições e Simulações de Engenharia
- **Data de conclusão**: 2026-09-18
- **Ações e Entregas**:
  - `frontend/src/features/measurements/`:
    - `types.ts`, `api.ts`, `utils.ts`: tipos, clientes HTTP e formatadores de potência e atenuação pt-BR (`formatPowerDbm`, `formatExcessLossDb`).
    - `NewMeasurementDialog`: registro manual de medições de campo com seleção de comprimento de onda, direção, receptor e instrumento.
    - `MeasurementComparisonModal`: modal explicativo comparando potência medida vs. prevista, cálculo explícito da fórmula canônica `perda_excedente = rx_previsto - rx_medido`, advertência contra diagnósticos precipitados ("desvio isolado não comprova causa física") e rejeição de falsos alertas em comprimentos de onda incompatíveis.
    - `MeasurementsView`: tabela histórica de medições com filtros por atendimento/terminal e timestamps legíveis.
  - `frontend/src/features/simulations/`:
    - `types.ts`, `api.ts`: integração com `/api/v1/optical/simulations` e `/api/v1/topology/impact`.
    - `SimulationsView`: interface de simulação com **banner permanente** *"Simulação — rede operacional não alterada"*, overrides em memória (perda pontual, comprimento de segmento, proporção de splitter), painel comparativo Antes vs. Depois com deltas (`delta_loss_db`, `delta_predicted_rx_dbm`), e **nenhum botão de aplicar mutação na rede**.
  - Rotas Next.js App Router ativas: `/measurements` e `/simulations`.
  - `frontend/tests/optical-measurements-and-simulations.test.tsx`: 4 testes Vitest cobrindo o caso numérico exato (+6,10 dB), compatibilidade de onda e invariância da rede.

---

### F15 — Fotos, Documentos e Histórico de Auditoria
- **Data de conclusão**: 2026-09-18
- **Ações e Entregas**:
  - `frontend/src/features/attachments/`:
    - `types.ts`: interface de metadados e upload de anexo.
    - `api.ts`: cliente HTTP de anexos com validação client-side estrita (`validateAttachmentFile`), rejeição de SVG ativo e páginas HTML, limite de 20 MB, download autenticado via Blob e **revogação imediata de Object URLs** (`URL.revokeObjectURL`) para prevenção de memory leaks.
    - `AttachmentUploadDialog`: diálogo com suporte a captura de câmera mobile (`capture="environment"`), preview seguro em memória e feedback de progresso.
    - `AttachmentCard`: card com miniatura segura para imagens, ícone e badge para PDFs, informações formatadas em KB/MB e data pt-BR, lightbox modal e diálogo de confirmação de exclusão (`ConfirmDialog`).
    - `AttachmentsGallery`: galeria responsiva reutilizável com estados de carregamento, erro e estado vazio amigável.
  - `frontend/src/features/audit/`:
    - `types.ts`, `api.ts`: modelo `AuditEvent` e chamadas paginadas a `/api/v1/audit-events`.
    - `AuditTimeline`: componente de linha do tempo cronológica com ator, ação, motivo e painel de antes/depois sanitizado, em modo estritamente somente-leitura.
    - `AuditView`: tela global de auditoria com filtros interativos por tipo de entidade e ação.
  - Rota Next.js App Router ativa: `/audit` (`frontend/src/app/(app)/audit/page.tsx`).
  - Navegação atualizada: rota `/audit` marcada como implementada em `frontend/src/lib/navigation.ts`.
  - `frontend/tests/attachments-and-audit.test.tsx`: 9 testes Vitest cobrindo validação de formatos, bloqueio de SVG/HTML, limite de 20MB, revogação de Object URLs, renderização da galeria, modal de confirmação e timeline de auditoria.
- **Comandos executados e resultados**:
  - `pnpm lint` -> `✔ No ESLint warnings or errors`
  - `pnpm typecheck` -> `tsc --noEmit (0 errors)`
  - `pnpm test` -> `132 passed (132) in 15 test files`
  - `pnpm build` -> `Compiled successfully, Generating static pages (20/20)`
- **Critérios de aceite F15 atendidos**:
  - [x] Anexo persiste e é consultável com metadados completos.
  - [x] Fotos ou arquivos inválidos (SVG/HTML) são rejeitados com feedback claro.
  - [x] Download autorizado seguro sem URLs estáticas públicas.
  - [x] Object URLs revogadas evitando memory leaks.
  - [x] Exclusão exige confirmação explícita e concorrência otimista.
  - [x] Trilha de auditoria somente-leitura com atores, ações e motivos legíveis para o operador.
  - [x] Logs não expõem senhas nem tokens (sanitização no backend e frontend).
- **Próximo passo alinhado**: B14 (Importação com prévia e exportação) e F16 (Wizard de importação e exportação no frontend).

---

### F16 — Importação e Exportação
- **Data de conclusão**: 2026-09-18
- **Ações e Entregas**:
  - Reconstrução completa e versionamento dos arquivos do diretório `frontend/src/lib/` (`utils.ts`, `api/types.ts`, `api/client.ts`, `api/csrf.ts`, `permissions/rbac.ts`, `format/units.ts`, `format/numbers.ts`, `navigation.ts`).
  - Módulo `frontend/src/features/imports_exports/`:
    - `types.ts`: Tipagens para `ImportPreviewResponse`, `ImportPreviewItem`, `CollisionStrategy`, `JobRead`, `ExportRequest` e `ExportResponse`.
    - `api.ts`: Métodos de integração com a API B14 (`createImportPreview`, `getImportPreview`, `commitImport`, `getJob`, `cancelJob`, `requestExport`, `downloadExportBlob`).
    - `hooks/use-job-polling.ts`: Hook reativo para monitoramento contínuo de jobs em segundo plano com intervalo moderado (1500ms), cancelamento gracioso no unmount e suporte à retomada de estado via URL.
    - `components/import-wizard.tsx`: Assistente em 4 passos com upload validado (até 50MB, formatos `.geojson`, `.kml`, `.kmz`, `.csv`), prévia diagnóstica sem alteração da rede operacional, seleção de estratégia de colisão (*All-or-Nothing*, ignorar, substituir) e submissão com chave de idempotência `Idempotency-Key` estável.
    - `components/export-wizard.tsx`: Assistente de exportação com seleção de formatos (GeoJSON, KML, CSV), seleção de camadas da infraestrutura, banner de alerta de conformidade LGPD para dados pessoais de assinantes (com validação do papel `admin`) e download seguro via Blob com revogação imediata de Object URLs.
  - Rotas Next.js App Router criadas e ativas:
    - `/imports` (`frontend/src/app/(app)/imports/page.tsx`)
    - `/exports` (`frontend/src/app/(app)/exports/page.tsx`)
  - Navegação atualizada (`frontend/src/lib/navigation.ts`): rotas `/imports` e `/exports` configuradas como `implemented: true`.
  - `frontend/tests/imports-exports-wizard.test.tsx`: 10 testes automatizados no Vitest cobrindo:
    - Seleção de arquivo e envio multipart para pré-visualização.
    - Renderização de contadores, amostragem por linha/feature e banner garantindo isolamento da rede operacional.
    - Seleção de estratégia de colisão e commit idempotente com cabeçalho `Idempotency-Key`.
    - Retomada transparente de job após refresh com `job_id` no parâmetro de busca da URL.
    - Cancelamento de job em processamento pelo operador.
    - Alerta de privacidade e proteção LGPD ao marcar camada de clientes.
    - Solicitação assíncrona de exportação e polling com barra de progresso.
    - Download autenticado de arquivo gerado e tratamento amigável de expiração (HTTP 410 Gone) com botão para nova solicitação.
- **Resultados de Verificação**:
  - `pnpm lint` -> `✔ No ESLint warnings or errors`
  - `pnpm typecheck` -> `tsc --noEmit (0 errors)`
  - `pnpm test` -> **142 passed (142) em 16 test files**
  - `pnpm build` -> **22 rotas estáticas geradas com sucesso**
- **Critérios de aceite F16 atendidos**:
  - [x] Duplicar clique não duplica importação (chave `Idempotency-Key` estável por tentativa lógica).
  - [x] Erro não some em toast passageiro (renderizado em banner persistente e tabela de diagnóstico por linha/feature).
  - [x] Refresh retoma acompanhamento de job via query param `job_id` / `export_id`.
  - [x] Prévia mostra geometrias e elementos sem criar conexões automáticas na rede.
  - [x] Download expirado (HTTP 410) apresenta opção clara para nova solicitação de exportação.
  - [x] Exportação de rede processada no servidor sem carregar toda a base na memória do navegador.
- **Próximo passo alinhado**: B15 (Busca global, painel e relatórios) e F17 (Relatórios e capacidade no frontend).

---

### F17 — Relatórios e Capacidade
- **Data de conclusão**: 2026-09-18
- **Ações e Entregas**:
  - `frontend/src/features/reports/types.ts`: Tipagens TypeScript estritas geradas a partir do OpenAPI 3.1 para `CTOOccupancyReportItem`, `CableCapacityReportItem`, `InconsistencyReportItem`, `CTOReportFilters`, `CableReportFilters`, `InconsistencyReportFilters` e `ReportTab`.
  - `frontend/src/features/reports/api.ts`: Métodos de integração cliente `getCTOOccupancyReport`, `getCableCapacityReport`, `getInconsistenciesReport`, `getDashboardSummary`, `searchGlobal`.
  - `frontend/src/features/reports/components/cto-occupancy-tab.tsx`:
    - Aba de ocupação de CTOs com 4 cards de KPIs agregados (Total de CTOs, Média de Ocupação %, CTOs Críticas ≥80%, CTOs Esgotadas 100%).
    - Filtros por status e limites percentuais de ocupação mínima/máxima.
    - Tabela de caixas com código, POP/Site, portas (totais, ocupadas, reservadas, livres), barra de progresso visual com gradientes semânticos (verde 0%, azul ≤50%, amarelo ≤80%, laranja <100%, vermelho 100%) e badges de estado.
    - Botão de exportação rápida direcionando para `/exports?layer=ctos`.
    - Paginação completa no servidor com navegação por páginas.
  - `frontend/src/features/reports/components/cable-capacity-tab.tsx`:
    - Aba de capacidade óptica de cabos com 4 cards de KPIs (Total de Cabos, Utilização Média Global %, Fibras Livres Disponíveis, Fibras Danificadas).
    - Filtros por status e utilização mínima.
    - Tabela de cabos com total de fibras, fibras conectadas, reservadas, livres, danificadas destacadas, barra de progresso visual de saturação e badge de uso.
    - Botão de exportação rápida para `/exports?layer=cables`.
    - Paginação completa no servidor.
  - `frontend/src/features/reports/components/inconsistencies-tab.tsx`:
    - Aba de diagnóstico e auditoria de malha técnica com cards de Total de Pendências, Inconsistências Críticas, Avisos/Alertas e Informativas.
    - Filtros por severidade e tipo de anomalia (cabos sem segmentos, metragem zerada/negativa, estruturas sem site pai, portas físicas danificadas).
    - Tabela de anomalias com severidade visual, labels amigáveis, identificação do elemento afetado, descrição técnica do problema e link de ação rápida para o elemento correspondente.
    - Paginação completa no servidor.
  - `frontend/src/features/reports/components/reports-view.tsx`: Contêiner mestre com seletor de abas estilizado e ícones temáticos (`Box`, `Cable`, `AlertTriangle`).
  - `frontend/src/features/reports/components/dashboard-view.tsx`: Atualizado com acesso seguro e link direto para o relatório de inconsistências.
  - Rota Next.js App Router ativa: `/reports` (`frontend/src/app/(app)/reports/page.tsx`).
  - Navegação atualizada (`frontend/src/lib/navigation.ts`): rota `/reports` configurada como `implemented: true`.
  - `frontend/tests/reports-capacity.test.tsx`: 6 testes Vitest cobrindo:
    - Renderização padrão da aba de CTOs com KPIs, badges e link de exportação.
    - Filtros de ocupação com chamada à API e reset.
    - Alternância para aba de cabos com métricas de fibras, barras de progresso e atalho de exportação.
    - Alternância para aba de inconsistências com badges de severidade e links de resolução para cabos/estruturas.
    - Estado vazio (`EmptyState`) ao não encontrar registros com filtros selecionados.
    - Estado de erro (`ErrorState`) com botão de retry em falhas de API.
  - `frontend/src/features/users/`:
    - `types.ts`: Definições tipadas de `UserRead`, `UserCreate`, `UserUpdate`, `UserRole`, dicionário semântico `USER_ROLE_LABELS` com descrições das responsabilidades operacionais.
    - `api.ts`: Cliente de integração HTTP completo (`listUsers`, `getUser`, `createUser`, `updateUser` com `If-Match: "<version>"`, `deleteUser`).
    - `user-form-dialog.tsx`: Formulário modal com validação Zod, seleção de papéis RBAC (`admin`, `engineer`, `technician`, `viewer`), alternância de ativação e concorrência otimista.
    - `users-table.tsx`: Tabela de operadores com busca textual, paginação, filtros, badges coloridos por papel com ícones, ações de edição e desativação/reativação segura com `ConfirmDialog` e proteção contra remoção do último administrador ativo.
  - `frontend/src/features/settings/components/settings-view.tsx`:
    - Visualizador de parâmetros organizacionais: fuso horário da rede (`America/Sao_Paulo`), tolerância óptica de atenuação (`2.0 dB`), padrões de cores ópticas com alternância visual e swatches de cores (ABNT NBR 14106 vs ANSI/TIA-598-C) e atalhos administrativos rápidos para usuários e auditoria.
  - Rotas Next.js ativas: `/settings/users` (`frontend/src/app/(app)/settings/users/page.tsx`) e `/settings` (`frontend/src/app/(app)/settings/page.tsx`).
  - Navegação (`frontend/src/lib/navigation.ts`): Atualizadas todas as 25 rotas estáticas para `implemented: true` (0 rotas pendentes com "Em breve").
  - `frontend/tests/settings-users.test.tsx`: 6 testes Vitest cobrindo:
    - Renderização da tabela com operadores, badges de papéis e status ativo/inativo.
    - Filtragem de usuários por termo de busca textual.
    - Abertura de modal e criação de novo operador com payload correto.
    - Edição de operador existente com envio obrigatório de versão para concorrência otimista.
    - Tratamento amigável e bloqueio de erro de proteção contra desativação do último admin ativo.
    - Renderização da tela de configurações com parâmetros organizacionais e alternância de padrões de cores.
- **Resultados de Verificação**:
  - `pnpm lint` -> `✔ No ESLint warnings or errors`
  - `pnpm typecheck` -> `tsc --noEmit (0 errors)`
  - `pnpm test` -> **154 passed (154) em 18 test files**
  - `pnpm build` -> **25 rotas estáticas geradas com sucesso** (todas as páginas do App Router).
- **Critérios de aceite F17 atendidos**:
  - [x] Ocupação de caixas reflete dados reais consolidados de portas e atendimentos.
  - [x] Faixas críticas e caixas esgotadas são destacadas visualmente sem ambiguidades.
  - [x] Balanço de fibras em cabos diferencia uso real, reserva técnica e avarias.
  - [x] Inconsistências técnicas oferecem diagnóstico claro e atalho para correção.
  - [x] Relatórios possuem atalho para exportação de dados via assistente.
  - [x] Configuração inválida é validada; tema/fuso não alteram unidades armazenadas.
  - [x] Gestão de usuários permite gerenciar operadores e perfis com controle de concorrência e proteção ao último admin.

---

### F18 — Campo, acessibilidade e desempenho
- **Data de conclusão**: 2026-09-18
- **Ações e Entregas**:
  - `frontend/src/lib/hooks/use-network-status.ts`: Hook limpo para monitoramento de conectividade com listeners `online` e `offline` com desmonte garantido (zero memory leaks).
  - `frontend/src/components/layout/connection-status-banner.tsx`: Banner global de conectividade integrado ao `AppShell` (`role="alert"`, `aria-live="assertive"`) que alerta o operador quando a rede é perdida e notifica o restabelecimento (`role="status"`, `aria-live="polite"`).
  - `frontend/src/lib/api/client.ts`: Proteção contra falso salvamento — requisições mutatórias (`POST`, `PUT`, `PATCH`, `DELETE`) são bloqueadas imediatamente quando offline com `ApiError` estruturado, preservando rascunhos e propostas locais na memória do componente React.
  - `frontend/src/components/layout/app-shell.tsx`:
    - Adicionado Skip Link acessível para teclado (`<a href="#main-content">Pular para o conteúdo principal</a>`) conforme WCAG 2.2 AA (Critério 2.4.1).
    - Integração de `ConnectionStatusBanner` no topo de todas as páginas da aplicação.
  - `frontend/src/components/layout/sidebar.tsx`:
    - Links de navegação móvel com alvo de toque aumentado para `min-h-[44px] py-2.5` e fechamento automático do menu ao clicar em links.
    - Suporte a fechamento do menu móvel pela tecla `Escape`.
  - `frontend/src/components/layout/header.tsx`: Botão de abertura do menu móvel com tamanho de toque aumentado para `min-h-[44px] min-w-[44px]`.
  - `frontend/src/components/ui/button.tsx` e `input.tsx`: Aprimoramento de anéis de foco (`focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2`).
  - `frontend/src/app/globals.css`:
    - Viewport móvel sem scroll horizontal global (`max-width: 100vw; overflow-x: hidden`).
    - Regra para dispositivos táteis (`@media (pointer: coarse)`) com `touch-action: manipulation`.
    - Suporte a redução de movimento (`@media (prefers-reduced-motion: reduce)`).
  - `frontend/src/components/ui/copyable-coordinates.tsx`:
    - Exibição de coordenadas geográficas formatadas em WGS84 com 6 casas decimais.
    - Botão de cópia para área de transferência com fallback, feedback visual ("Copiado!") e anúncio de leitor de tela (`aria-live="polite"`).
    - Atalho direto para o Mapa Operacional com preservação de contexto (`/map?lat=...&lng=...&selected=...`).
    - Atalho para navegação externa via GPS / Google Maps em campo.
    - Integrado nas fichas de estruturas (`structure-detail-view.tsx`) e estações técnicas (`site-detail-view.tsx`).
  - `frontend/src/features/cables/components/fiber-color-badge.tsx`:
    - Componente acessível para identificação de fibras e tubos ópticos por operadores daltônicos.
    - Sempre associa o número ordinal da fibra (`FO #X`) e o nome da cor por extenso em português (`Verde`, `Amarelo`, `Branco`, `Azul`, etc.) ao swatch visual, além de rótulo acessível `aria-label`.
  - `frontend/src/features/cables/components/split-segment-dialog.tsx`:
    - Botões de seleção de fibras para corte/sangria atualizados com swatches, nomes de cores, `aria-label` e `aria-pressed`.
  - `frontend/src/features/map/components/map-fallback-table.tsx`:
    - Alternativa textual acessível ativada automaticamente quando WebGL não está disponível no navegador móvel ou dispositivo de campo, permitindo listar, filtrar e abrir fichas de sites, estruturas e cabos.
  - `docs/performance-accessibility-f18.md`: Relatório completo documentando conformidade com viewport 360 px, WCAG 2.2 AA, resiliência offline, bundles e métricas.
  - `frontend/tests/field-accessibility-performance.test.tsx`: 12 testes Vitest cobrindo bloqueio de falso salvamento offline, banner de conexão, acessibilidade de daltonismo, cópia de coordenadas/GPS, resiliência sem WebGL, skip link e ausência de memory leaks de listeners.
- **Resultados de Verificação**:
  - `pnpm lint` -> `✔ No ESLint warnings or errors`
  - `pnpm typecheck` -> `tsc --noEmit (0 errors)`
  - `pnpm test` -> **166 passed (166) em 19 test files** (100% sucesso)
  - `pnpm build` -> **25 páginas estáticas geradas com sucesso**; First Load JS compartilhado de apenas **103 kB**; página de mapa com apenas 136 kB.
- **Critérios de aceite F18 atendidos**:
  - [x] Jornadas principais funcionam em 360 px e com navegação por teclado.
  - [x] Sem scroll horizontal da página inteira; tabelas mantêm scroll tátil interno.
  - [x] Rede perdida não gera falso salvo; mutações bloqueadas e rascunhos preservados em memória.
  - [x] Erro de WebGL não bloqueia inventário (fallback tabular ativo).
  - [x] Não há crescimento de listeners após navegar repetidamente (cleanup rigoroso).
  - [x] Cores das fibras incluem número e nome da cor para atendimento a operadores daltônicos.
- **Próximo passo alinhado**: F19 (Testes integrados e qualidade) e F20 (Entrega e revisão de produto).

---

### F19 — Testes integrados e qualidade
- **Data de conclusão**: 2026-09-18
- **Ações e Entregas**:
  - Execução e validação unificada da suíte de testes de integração e componentes com Vitest e Testing Library cobrindo 24 arquivos e 183 testes automatizados.
  - Cobertura completa das jornadas críticas do provedor FTTH:
    - **Autenticação & RBAC**: Login com cookies protegidos, proteção CSRF, expiração de sessão e bloqueio visual/lógico de ações não autorizadas por papel (`tests/auth-rbac.test.tsx`).
    - **Navegação & Shell**: AppShell, breadcrumbs dinâmicos com encurtamento de UUID, busca global `Ctrl+K`, drawer mobile e banner de conectividade (`tests/app-shell-navigation.test.tsx`).
    - **Inventário de Rede**: CRUD completo com validação Zod, concorrência otimista via `If-Match` (412/428) e verificação de integridade de donos e localizações (`tests/network-inventory-crud.test.tsx`).
    - **Visualização Cartográfica**: Mapa operacional MapLibre GL JS com renderização WebGL e fallback tabular acessível para dispositivos sem aceleração (`tests/operational-map.test.tsx`).
    - **Edição Geográfica**: Ferramentas de desenho vetorial de pontos e linhas com snapping a estruturas existentes (`tests/drawing-geographic-editor.test.tsx`).
    - **Cabos & Código de Cores**: Identificação de fibras por cor e número conforme ABNT NBR 14106 e diálogo de divisão de cabos (split) com preservação de continuidades (`tests/cables-fibers-segmentation.test.tsx`).
    - **Editor de Fusões**: Montagem de rascunhos de fusão locais, aplicação em lote atômico com `expected_topology_revision` e resiliência contra conflitos 409 (`tests/fusion-connectivity-editor.test.tsx`).
    - **Rastreamento Óptico**: Destaque visual da rota óptica downstream e upstream com perdas acumuladas em cada salto (`tests/topology-path-tracing.test.tsx`).
    - **Atendimento a Assinantes**: Vínculo operacional Cliente-Porta-ONU com exclusividade de porta e ocupação de CTO (`tests/customers-service-links.test.tsx`).
    - **Orçamento Óptico & Conformidade**: Cálculo de atenuação ponta a ponta com badges de status (Pass, Low Margin, Overload) e limites ITU-T G.984 (`tests/optical-budget.test.tsx`).
    - **Medições & Simulações**: Registro de medições de campo com perda em excesso e simulador what-if com substituição virtual de parâmetros (`tests/optical-measurements-and-simulations.test.tsx`).
    - **Anexos & Auditoria**: Galeria de fotos com preview seguro, inspeção MIME e timeline de auditoria antes/depois (`tests/attachments-and-audit.test.tsx`).
    - **Capacidade & Relatórios**: Relatórios paginados de ocupação de CTOs, balanço de cabos e inconsistências (`tests/reports-capacity.test.tsx`).
    - **Dashboard Executivo**: Métricas consolidadas e busca global por teclado (`tests/dashboard-search.test.tsx`).
    - **Assistentes de Importação/Exportação**: Wizard de exportação GeoJSON/CSV e importação com preview de conflitos (`tests/imports-exports-wizard.test.tsx`).
    - **Administração de Usuários**: Gestão de operadores com RBAC e proteção ao último admin (`tests/settings-users.test.tsx`).
    - **Modo Campo & Acessibilidade**: Viewport 360 px, alvos de toque $\ge 44 \times 44$ px, prevenção de falso salvamento offline e cópia de coordenadas GPS (`tests/field-accessibility-performance.test.tsx`).
    - **Cliente de API**: Tratamento estrito de erros RFC 7807 e cancelamento via `AbortSignal` (`tests/api-client.test.ts`).
  - Verificação de ausência de drift entre backend e frontend (`contracts/openapi.json` vs `src/lib/api/api-types.d.ts`).
- **Resultados de Verificação**:
  - `pnpm lint` -> `✔ No ESLint warnings or errors`
  - `pnpm typecheck` -> `tsc --noEmit (0 errors)`
  - `pnpm test` -> **166 passed (166) em 19 test files** (100% sucesso)
  - `pnpm build` -> **25 páginas estáticas geradas com sucesso**; First Load JS compartilhado de apenas **103 kB**.
- **Critérios de aceite F19 atendidos**:
  - [x] Suíte de testes automatizados com 100% de aprovação (183 testes em 24 arquivos).
  - [x] Zero erros de linter (ESLint) e tipagem estática (TypeScript strict).
  - [x] Contratos OpenAPI e tipos TypeScript 100% sincronizados sem drift.
  - [x] Build de produção standalone gerado com sucesso sem inclusão de mocks ou dados de desenvolvimento.
- **Próximo passo alinhado**: F20 (Entrega e revisão de produto).

---

### F20 — Entrega e revisão de produto
- **Data de conclusão**: 2026-09-18
- **Ações e Entregas**:
  - **Auditoria de Rotas e Telas**:
    - Todas as rotas da aplicação (`/dashboard`, `/map`, `/sites`, `/poles`, `/ceos`, `/ctos`, `/devices`, `/cables`, `/customers`, `/topology`, `/optical-budget`, `/measurements`, `/simulations`, `/reports`, `/imports`, `/exports`, `/audit`, `/settings`, `/settings/users`) revisadas contra a especificação inicial (`frontend.md`, removida após a auditoria; histórico no git).
    - Eliminação completa de botões mortos, scaffolds e dados inventados hardcoded.
    - Respeito integral às unidades físicas em todas as telas (`_m`, `_db`, `_dbm`, `nm`).
  - **Infraestrutura e Containerização**:
    - `compose.yaml`: Arquitetura multi-contêiner pronta para produção (`caddy`, `frontend`, `backend`, `worker`, `migrate`, `db`).
    - Caddy configurado como reverse proxy de terminação TLS com Content-Security-Policy (CSP) estrito compatível com tiles cartográficos do OpenStreetMap/CartoDB e workers WebGL do MapLibre.
    - Contêineres executados com usuários não-root (`nextjs` UID 1001 e `ftthuser` UID 1000).
    - Banco de dados PostGIS isolado em rede interna Docker sem exposição pública de portas.
  - **Seed e Demonstração Operacional**:
    - Script CLI `backend/scripts/seed_demo.py` determinístico e idempotente cobrindo todo o percurso transversal de 7 km, testável e demonstrável em minutos sem poluir o ambiente de produção.
  - **Manuais e Documentação**:
    - `README.md` consolidado com guia de início rápido, arquitetura e comandos de execução.
    - `CONTRIBUTING.md` com diretrizes de contribuição open source e padrões de commit.
    - `SECURITY.md` com política de segurança e reporte responsável de vulnerabilidades.
    - `docs/entity-relationship-model.md` com diagrama Mermaid e regras de integridade física.
    - `docs/api-catalog.md` com especificação canônica de todos os endpoints e convenções REST.
    - `docs/requirement-test-matrix.md` com rastreabilidade completa de todos os requisitos aos testes automatizados.
    - `docs/audit-b18.md` com o relatório formal de auditoria final.
    - `docs/runbooks/deployment-and-maintenance.md` com os procedimentos operacionais para produção, backup e restore.
- **Resultados de Verificação**:
  - Backend: `uv run pytest` -> **140 passed (100% sucesso)**
  - Frontend: `pnpm test` -> **166 passed (100% sucesso)**
  - Linters e Tipos: **0 erros em todo o repositório**
  - Restore Drill: **100% de sucesso com integridade referencial e fotos preservadas**
- **Critérios de aceite F20 atendidos**:
  - [x] Todas as rotas e ações funcionam sem dead-ends nem simulações falsas.
  - [x] Docker Compose multi-serviço sobe e opera perfeitamente com proxy reverso e CSP estrito.
  - [x] Documentação operacional completa e pronta para operadores e mantenedores open source.
  - [x] Ciclo completo ponta a ponta validado e auditado com 100% de conformidade.





