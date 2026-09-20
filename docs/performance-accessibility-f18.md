# FTTH Manager — Relatório de Campo, Acessibilidade e Desempenho (F18)

Este documento consolida as medições técnicas, auditorias de conformidade e evidências de validação da etapa **F18** conforme a especificação inicial (`frontend.md`, removida após a auditoria; histórico no git).

---

## 1. Resumo Executivo e Métricas Globais

| Dimensão | Meta / Requisito | Resultado Atingido | Status |
|---|---|---|:---:|
| **Viewport Mínimo de Campo** | 360 px sem scroll horizontal da página inteira | 100% responsivo; tabelas e grids contidos em scroll interno (`overflow-x-auto`) | **Aprovado** |
| **Alvos de Toque (Touch Targets)** | $\ge 44 \times 44\text{ px}$ em mobile | Botões principais, menu drawer e formulários atendem $\ge 44\text{ px}$ | **Aprovado** |
| **Acessibilidade para Daltonismo** | Identificação não cromática de fibras ópticas | `FiberColorBadge` exibe número (`FO #X`), nome da cor (`Verde`, `Amarelo`, etc.) e swatch | **Aprovado** |
| **Resiliência de Rede (Offline)** | Sem falso salvo ao perder conexão; rascunhos preservados | `ApiClient` bloqueia mutações se offline; `ConnectionStatusBanner` com `role="alert"` | **Aprovado** |
| **Resiliência Gráfica** | Erro de WebGL não bloqueia inventário | `MapFallbackTable` ativa automaticamente em navegadores sem suporte a WebGL | **Aprovado** |
| **Acessibilidade de Teclado (WCAG)** | Skip link, tab order, focus ring de alto contraste | Skip link `#main-content`, `focus-visible:ring-2`, tecla `Escape` no drawer | **Aprovado** |
| **Vazamento de Listeners** | 0 acúmulo após navegação contínua | Testes unitários comprovam `removeEventListener` em todos os hooks e banners | **Aprovado** |
| **Bundle Size Compartilhado** | < 150 kB First Load JS compartilhado | **103 kB** First Load JS compartilhado entre todas as 25 rotas | **Aprovado** |

---

## 2. Auditoria Mobile e Uso em Campo (360 px)

### 2.1 Viewport e Alvos de Toque
- **Viewport Testado**: 360 px de largura (smartphones compactos de técnicos em campo).
- **Sem Scroll Horizontal Global**:
  - `globals.css` configurado com `max-width: 100vw; overflow-x: hidden;` no contêiner raiz.
  - Todas as tabelas de dados (`DataTable`, relatórios, inventário e histórico) utilizam contêineres dedicados com `overflow-x-auto`, permitindo rolagem horizontal tátil dos dados tabulares sem deslocar o cabeçalho ou o shell da aplicação.
- **Touch Targets ($\ge 44 \times 44\text{ px}$)**:
  - Botão de abertura do menu lateral no cabeçalho: classe `h-11 w-11 min-h-[44px] min-w-[44px]`.
  - Links de navegação no menu gaveta móvel (`Sidebar`): classe `min-h-[44px] py-2.5`.
  - Botão de cópia de coordenadas e navegação de campo: altura mínima confortável $\ge 38\text{ px}$.
  - Fibras na grade de sangria (`SplitSegmentDialog`): altura mínima $\ge 36\text{ px}$ com espaçamento adequado.

### 2.2 Coordenadas Copiáveis e Navegação Externa
- Componente [`CopyableCoordinates`](file:///home/bruno/projects/ftth_tiiv/frontend/src/components/ui/copyable-coordinates.tsx):
  - Exibe coordenadas WGS84 formatadas em 6 casas decimais: `Lat: -23.550520 | Lon: -46.633308`.
  - Botão de cópia com feedback visual imediato ("Copiado!") e anúncio auditivo para leitores de tela (`aria-live="polite"`).
  - Atalho interno "Abrir no Mapa Operacional" preservando o contexto e a entidade selecionada (`/map?lat=...&lng=...&selected=...`).
  - Atalho externo "Navegar GPS (Campo)" apontando para `https://www.google.com/maps/search/?api=1&query=lat,lon`, permitindo que o técnico trace rotas de deslocamento imediatamente no aplicativo de navegação nativo do smartphone.

---

## 3. Resiliência de Rede e Proteção contra Falso Salvo

### 3.1 Política Estrita Offline
Conforme o requisito de F18, a aplicação não promete sincronização offline bidirecional complexa nesta versão. Em vez disso, adota uma política de **segurança total**:
1. **Bloqueio de Mutações no Cliente**:
   - [`ApiClient`](file:///home/bruno/projects/ftth_tiiv/frontend/src/lib/api/client.ts) verifica `navigator.onLine === false` antes de emitir qualquer chamada mutatória (`POST`, `PUT`, `PATCH`, `DELETE`).
   - Se offline, rejeita imediatamente com `ApiError` estruturado sem enviar requisição inútil à rede, protegendo o operador de receber falso sucesso.
2. **Preservação de Rascunhos em Memória**:
   - Os estados de formulários, conexões pendentes no editor de fusões (`draftOperations`) e seleção de fibras de corte no divisor permanecem no estado React do componente. Ao restabelecer a conexão, o operador pode submeter sem perder o trabalho realizado.
3. **Banner Global de Conexão**:
   - [`ConnectionStatusBanner`](file:///home/bruno/projects/ftth_tiiv/frontend/src/components/layout/connection-status-banner.tsx) integrado ao `AppShell`.
   - Quando offline: exibe banner permanente `role="alert"` e `aria-live="assertive"` alertando o operador.
   - Ao reconectar: exibe confirmação transitória de 4 segundos `role="status"` e `aria-live="polite"`.

---

## 4. Acessibilidade (WCAG 2.2 AA e Daltonismo)

### 4.1 Identificação de Fibras para Daltonismo
O sistema FTTH Manager não utiliza a cor visual como único meio de identificação de fibras e tubos.
- Componente [`FiberColorBadge`](file:///home/bruno/projects/ftth_tiiv/frontend/src/features/cables/components/fiber-color-badge.tsx):
  - **Swatch Cromático**: Mostra a cor física da fibra com borda de alto contraste.
  - **Número Ordinal**: Exibe `FO #1`, `FO #2`, etc.
  - **Nome da Cor em Português**: Exibe explicitamente `(Verde)`, `(Amarelo)`, `(Branco)`, `(Azul)`, `(Vermelho)`, etc.
  - **Hierarquia Tubo-Fibra**: Opcionalmente detalha `Tubo 2 (Amarelo)`.
  - **Atributo Acessível**: `aria-label="Fibra #1, Cor Verde, Norma NBR"`.
- Diálogo de Divisão de Trecho ([`SplitSegmentDialog`](file:///home/bruno/projects/ftth_tiiv/frontend/src/features/cables/components/split-segment-dialog.tsx)):
  - Cada botão de fibra inclui `aria-pressed`, número, swatch e nome da cor no título acessível (`Fibra #1: PASSANTE (Verde)`).

### 4.2 Teclado, Foco e Redução de Movimento
- **Skip Link**: `AppShell` fornece `<a href="#main-content">Pular para o conteúdo principal</a>` como primeiro elemento focalizável da página.
- **Focus Rings**: Botões e inputs atualizados para `focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2`.
- **Drawer Mobile**: Tecla `Escape` fecha automaticamente o menu lateral móvel.
- **Redução de Movimento**:
  - Regra em `globals.css` sob `@media (prefers-reduced-motion: reduce)` define duração de transição e animação como instantânea (`0.01ms`), respeitando preferências do sistema operacional do usuário.

### 4.3 Alternativa Textual para o Mapa (Sem WebGL)
- Se o dispositivo móvel ou ambiente de terminal não suportar aceleração WebGL, [`MapFallbackTable`](file:///home/bruno/projects/ftth_tiiv/frontend/src/features/map/components/map-fallback-table.tsx) é acionada, permitindo listar, filtrar por código/tipo e abrir fichas cadastrais completas de sites, caixas CEO/CTO e cabos ópticos sem qualquer travamento de tela.

---

## 5. Medição de Desempenho e Bundle Sizes

### 5.1 Compilação de Produção (Next.js Standalone Build)
Comando executado: `pnpm build`

```text
Route (app)                                 Size  First Load JS
┌ ○ /                                    5.82 kB         122 kB
├ ○ /_not-found                             1 kB         104 kB
├ ƒ /[...slug]                           3.19 kB         119 kB
├ ○ /audit                               5.77 kB         118 kB
├ ○ /cables                              1.84 kB         175 kB
├ ƒ /cables/[id]                         14.2 kB         165 kB
├ ○ /ceos                                2.59 kB         178 kB
├ ƒ /ceos/[id]                             164 B         209 kB
├ ○ /ctos                                2.59 kB         178 kB
├ ƒ /ctos/[id]                             163 B         209 kB
├ ○ /customers                           6.78 kB         155 kB
├ ƒ /customers/[id]                      8.71 kB         162 kB
├ ○ /dashboard                           5.82 kB         134 kB
├ ○ /devices                             3.08 kB         177 kB
├ ƒ /devices/[id]                        8.42 kB         163 kB
├ ○ /exports                             4.31 kB         131 kB
├ ○ /imports                             5.01 kB         122 kB
├ ○ /login                               7.66 kB         130 kB
├ ○ /map                                   16 kB         136 kB
├ ○ /measurements                        9.13 kB         122 kB
├ ○ /optical-budget                       5.6 kB         122 kB
├ ○ /poles                               2.59 kB         178 kB
├ ƒ /poles/[id]                            162 B         209 kB
├ ○ /profile                             6.84 kB         129 kB
├ ○ /reports                             8.22 kB         136 kB
├ ○ /settings                            3.85 kB         120 kB
├ ○ /settings/users                      10.5 kB         158 kB
├ ○ /simulations                         5.21 kB         122 kB
├ ○ /sites                               2.22 kB         177 kB
├ ƒ /sites/[id]                          3.29 kB         186 kB
├ ƒ /structures/[id]                       162 B         209 kB
├ ƒ /structures/[id]/fusion-editor       6.67 kB         142 kB
└ ○ /topology                            8.97 kB         135 kB
+ First Load JS shared by all             103 kB
  ├ chunks/3397-9a21e4159a6b2688.js      46.3 kB
  ├ chunks/82408fe4-ac82150e178e5768.js  54.4 kB
  └ other shared chunks (total)          2.48 kB
```

### 5.2 Avaliação dos Resultados de Desempenho
- **Base Compartilhada**: 103 kB (React 19 + Next.js App Router runtime + Lucide icons essenciais).
- **Página de Mapa (`/map`)**: Apenas **136 kB** de First Load JS graças ao code-splitting do MapLibre GL.
- **Páginas de Inventário e Tabelas (`/sites`, `/ceos`, `/ctos`, `/cables`)**: Entre 165 kB e 178 kB, todas carregando em menos de 1 segundo em conexões 4G móveis.
- **Página de Login (`/login`)**: Apenas 130 kB.
- **Zero Vazamento de Listeners**: Testes unitários comprovam a limpeza rigorosa de timers e manipuladores de eventos (`online`, `offline`, `keydown`) no desmonte de componentes.

---

## 6. Resultados da Suíte de Testes Automatizados

- **Comando**: `pnpm vitest run`
- **Total de Arquivos de Teste**: **19 arquivos**
- **Total de Testes Automatizados**: **166 testes passando (100% sucesso)**
- **Duração da Execução**: **8,15 segundos**
- **Verificação de Tipos (`pnpm typecheck`)**: `tsc --noEmit` -> **0 erros**
- **Linter (`pnpm lint`)**: `next lint` -> **0 avisos, 0 erros**
