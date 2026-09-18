# Progresso de Desenvolvimento Frontend — FTTH Manager

Registro contínuo de entregas, decisões de implementação, critérios de aceite atendidos e evidências de verificação do frontend do **FTTH Manager**, seguindo rigorosamente [`frontend.md`](file:///home/bruno/projects/ftth_tiiv/frontend.md) e o contrato compartilhado em `contracts/openapi.json`.

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
| **F16** | **Importação e exportação**: Assistentes de importação/exportação CSV/KML/GeoJSON com preview de validação. | ⏳ Próxima | B14 |
| **F17** | **Relatórios e capacidade**: Relatórios de ocupação de CTOs, fibras livres/reservadas e inconsistências. | ⏳ Pendente | B15 |
| **F18** | **Hardening, acessibilidade e performance**: Validação de acessibilidade WCAG 2.2 AA, contraste, foco e bundle size. | ⏳ Pendente | B16 |
| **F19** | **Validação ponta a ponta**: Testes E2E cobrindo fluxos reais do usuário de ponta a ponta. | ⏳ Pendente | B17 |
| **F20** | **Documentação operacional**: Manual do operador e guia de estilo da interface. | ⏳ Pendente | B18 |

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







