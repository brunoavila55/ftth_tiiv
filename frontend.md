# Frontend — Prompts para desenvolver um aplicativo FTTH completo

Especificação e sequência de prompts para o **FTTH Manager**, aplicação open source e self-hosted de documentação de rede FTTH. Interface em português brasileiro, pensada para engenharia e operação de campo. Complemento obrigatório: `backend.md`.

## Como usar

1. Entregue ambos os arquivos à IA e execute o prompt mestre.
2. Execute F01–F20 em ordem, acompanhando as dependências do backend. Cada etapa entrega código funcional e evidências dos critérios de aceite.
3. Use mocks apenas enquanto endpoints não estiverem disponíveis, gerados a partir dos contratos. Ative-os por variável explícita de desenvolvimento; produção nunca deve trocar uma API com erro por dados fictícios.
4. Em sessões novas, use o prompt de retomada ao final. Registre estado em `docs/progress-frontend.md`.
5. As tabelas de páginas, componentes e fluxos são requisitos de todas as etapas. Nenhum botão pode ser apenas decorativo ou retornar sucesso sem persistir a ação correspondente.
6. Nome, cores e medidas são uma direção inicial de produto. Versões devem ser verificadas na implementação; não repetir números de versão da conversa como se fossem garantidos.

## Prompt mestre — papel, objetivo e regras

```text
Atue como engenheiro frontend e designer de produto responsável pelo FTTH Manager. Leia frontend.md e backend.md integralmente, inspecione o repositório e suas instruções e implemente a etapa solicitada.

Crie uma aplicação de trabalho com Next.js App Router, React, TypeScript strict, Tailwind, shadcn/ui, Lucide, MapLibre GL JS, TanStack Query/Table, React Hook Form e Zod. Use pnpm com lockfile e versões compatíveis verificadas em documentação oficial. Um editor de conexões pode usar React Flow, após validar manutenção, licença e compatibilidade; seu grafo visual não é fonte de verdade da rede.

Frontend consome FastAPI via /api/v1. Tipos são gerados de contracts/openapi.json; backend é proprietário das regras de integridade, cálculo e autorização. Não implementar um segundo backend no Next.js. Use componentes de servidor onde úteis ao shell e componentes cliente para mapa, formulários e editores. Dados de sessão e rede nunca entram em cache público compartilhado.

Objetivo: mapa útil, inventário completo, editor de fusão preciso, ocupação de CTO, rastreamento, orçamento óptico, medições, impacto de rompimento, importações, relatórios, fotos e auditoria. Uma organização por instalação. Sem planos, checkout, billing ou landing page comercial.

Interface pt-BR, legível, responsiva, clara/escura, navegação por teclado e acessibilidade WCAG 2.2 AA como alvo de verificação. Não comunicar ocupação apenas pela cor. Use dados sintéticos somente em fixtures/demo sinalizada. Não usar fotos decorativas, métricas inventadas ou botões sem função para parecer completo.

Antes de codificar: identifique o endpoint e o fluxo de cada ação. Preserve padrões existentes que estejam corretos. Documente decisões reversíveis; pergunte somente por bloqueios reais. Não apague trabalho existente nem publique sem autorização correspondente.

Ao concluir cada etapa: informe arquivos alterados, fluxos implementados, comandos de verificação e resultados reais, limitações e próxima dependência. Atualize docs/progress-frontend.md. Não afirme que browser/teste/build passou se não foi executado.
```

## Contrato compartilhado v1

`backend.md` contém a especificação completa. O backend exporta `contracts/openapi.json`; este arquivo gera os tipos do cliente. Alterações precisam ser refletidas nos dois documentos e nos testes, nunca adaptadas silenciosamente só no frontend.

| Aspecto | Decisão |
| --- | --- |
| API | `/api/v1`, JSON `snake_case`, UUID em string, códigos humanos `code` |
| Datas | API ISO 8601 com timezone/UTC; apresentação pt-BR no fuso configurado |
| Unidades | `*_m`, `*_db`, `*_dbm`, `wavelength_nm`; não misturar dB e dBm |
| Geometria | GeoJSON EPSG:4326, `[longitude, latitude]` |
| Paginação | `{items,total,page,page_size}`, início 1, padrão 50, máximo 200 |
| Filtros | `q,status,page,page_size,sort`; campos e valores permitidos por endpoint |
| Concorrência | recurso tem `version`; PATCH/DELETE enviam `If-Match: "<version>"` |
| Falhas | 428 sem precondição; 412 versão antiga; 409 conflito de negócio |
| Erro uniforme | `application/problem+json`: `type,title,status,detail,code,request_id,errors` |
| Erros de campo | 422 com `errors: [{field,code,message}]` |
| Sessão | cookie HttpOnly, Secure em produção, SameSite=Lax; nunca token no localStorage |
| CSRF | buscar `{csrf_token}` em `GET /auth/csrf`; escritas incluem `X-CSRF-Token`; backend valida Origin |
| Perfis | `admin`, `engineer`, `technician`, `viewer`; permissões efetivas em `/auth/me` |
| Consistência | `topology_revision` em trace, orçamento, impacto e mapa; resultado antigo deve ser sinalizado |
| Jobs | polling HTTP e estados `queued/running/succeeded/failed/cancelled` |

Sessão: `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`, `GET /auth/csrf`, `POST /auth/change-password`. Sem cadastro público. Recuperação inicial é procedimento administrativo documentado, sem botão que promete enviar um e-mail inexistente.

Recursos: `/sites`, `/structures`, `/devices`, `/ports`, `/cables`, `/cable-segments`, `/splitters`, `/connections`, `/customers`, `/service-links`, `/optical-profiles`, `/measurements`, `/users`. CEO e CTO são structures, OLT/DIO/ONU são devices. A rota de UI `/ctos` consulta `/structures?kind=cto`; ela não inventa `/api/v1/ctos`.

| Fluxo | Endpoint |
| --- | --- |
| Painel | `GET /dashboard/summary` |
| Busca global | `GET /search?q=...&limit=20` |
| Mapa | `GET /map/features?bbox=...&layers=...&zoom=...` |
| Fibras por trecho | `GET /cable-segments/{id}/fibers` |
| Ocupação CTO | `GET /structures/{id}/occupancy` |
| Conectividade CEO | `GET /structures/{id}/connectivity` |
| Editor de conexão | `POST /connections/batch`, `expected_topology_revision` |
| Rastreamento | `POST /topology/trace` |
| Impacto | `POST /topology/impact` |
| Orçamento/simulação | `POST /optical/budgets`, `POST /optical/simulations` |
| Anexos | `POST /attachments`, `GET /attachments/{id}/download`, DELETE versionado |
| Histórico | `GET /audit-events` |
| Importação | `POST /imports/preview`, `GET /imports/{id}`, `POST /imports/{id}/commit` |
| Exportação | `POST /exports`, `GET /exports/{id}`, `GET /exports/{id}/download` |
| Jobs | `GET /jobs/{id}`, `POST /jobs/{id}/cancel` |
| Configuração | `GET /settings`, `PATCH /settings` |

Mapa retorna FeatureCollection com `features,bbox,topology_revision,truncated`; propriedades incluem `entity_id,entity_type,code,status,version`. Ao receber `truncated=true`, pedir aproximação/filtro e não sugerir que todos os elementos estão visíveis.

Trace retorna `status=complete|incomplete|ambiguous|cycle_detected|limit_exceeded`, `paths`, `warnings`, `unresolved_terminals`, `topology_revision`. Cada path possui steps ordenados e identificador associado à revisão. O frontend não transforma estado incompleto em caminho válido.

Orçamento retorna `status=complete|insufficient_data`, direção/onda, revisão, premissas, dados ausentes, steps, perdas, TX/RX, limites, margem e `assessment=pass|low_margin|below_sensitivity|overload|unknown`. Campos não calculáveis são null; UI usa “Não informado”/“Não calculável”, nunca `0,00` por conveniência.

## Experiência visual e componentes

O mapa é a área principal de trabalho. Layout desktop: barra lateral recolhível (~240 px), cabeçalho (~56 px), conteúdo central e painel contextual (~400 px). Em telas pequenas, navegação em drawer e detalhes em painel de altura ajustável ou página. Não cobrir atribuição, escala e controles do mapa com botões flutuantes.

Direção visual: fundo neutro, cartões discretos, bordas suaves, azul para ação principal, tipografia de sistema ou fonte local. Conteúdo denso com espaçamento suficiente para leitura; textos de operação em tamanho confortável. Código de cabo/porta em fonte monoespaçada opcional. Evitar grandes banners, gradientes excessivos e animações que atrapalhem o trabalho.

### Ícones e estados

Usar `lucide-react`; validar nomes exportados na versão instalada. Se um símbolo não existir, escolher equivalente no registro central. Ícones 18–20 px em botões/menu, traço consistente, tooltip e nome acessível em botão sem texto. Ícones decorativos são escondidos do leitor de tela. Não usar emoji como ícone principal da interface.

| Conceito/ação | Ícone proposto | Comportamento |
| --- | --- | --- |
| Painel | `LayoutDashboard` | Abre indicadores reais |
| Mapa | `Map` | Abre mapa mantendo filtros |
| POP/local | `Building2` | Abre cadastro de site |
| Poste | `MapPin` | Símbolo geográfico + tipo textual |
| OLT | `Server` | Abre equipamento e portas PON |
| DIO/portas | `PanelTop` | Abre painel de terminais |
| CEO | `Box` | Abre caixa e fusões |
| CTO | `Network` | Abre portas e ocupação |
| Cabo | `Cable` | Abre cabo, trechos e fibras |
| Splitter | `GitBranch` | Exibe entrada e saídas |
| ONU | `Router` | Exibe atendimento e potência |
| Cliente | `Users` | Abre cliente e vínculo |
| Rastrear | `Route` | Abre caminho óptico |
| Orçamento | `Calculator` | Calcula potência prevista |
| Medição | `Gauge` | Registra/exibe leitura |
| Simular rompimento | `Scissors` | Abre cenário sem alterar rede |
| Aviso/erro | `TriangleAlert` | Abre detalhes do problema |
| Camadas | `Layers` | Mostra seleção de camadas |
| Localização atual | `LocateFixed` | Solicita geolocalização após clique |
| Novo/editar/salvar | `Plus`, `Pencil`, `Save` | Ações reais com estado pendente |
| Desfazer/refazer | `Undo2`, `Redo2` | Histórico local do desenho |
| Buscar/filtrar | `Search`, `Filter` | Busca e filtros persistidos |
| Fotos/documentos | `Camera`, `Paperclip` | Captura/upload e anexos |
| Importar/exportar | `Upload`, `Download` | Fluxo com preview/job |
| Histórico | `History` | Auditoria filtrada |
| Configurações | `Settings` | Preferências e administração |
| Segurança/sair | `Shield`, `LogOut` | Usuários/permissões e logout |

Livre: rótulo “Livre” e símbolo neutro/verde. Conectada: “Conectada” e símbolo azul. Reservada: “Reservada” e símbolo âmbar. Danificada: “Danificada” e alerta vermelho. Desconhecida: “Não documentada” e símbolo cinza. Use forma, texto e legenda além de cor. A cor física de uma fibra é outro atributo: não alterá-la para representar ocupação.

### Componentes compartilhados

- `AppShell`, `Sidebar`, `Header`, `Breadcrumbs`, `GlobalSearch`, `PermissionGate`.
- `DataTable`, `FilterBar`, `Pagination`, `ColumnVisibility`, `EntityLink`, `StatusBadge`.
- `FormField`, `CoordinateInput`, `UnitInput`, `UnsavedChangesGuard`, `ConfirmDialog`, `ConflictDialog`.
- `LoadingState`, `EmptyState`, `ErrorState`, `OfflineBanner`, `JobProgress`, `Toast`.
- `MapCanvas`, `LayerPanel`, `MapLegend`, `MapToolbar`, `FeaturePanel`, `GeometryEditor`.
- `FiberSwatch` com cor+número+rótulo, `FiberTable`, `PortGrid`, `SpliceEditor`, `TerminalPicker`.
- `OpticalPathView`, `LossBreakdown`, `PowerBadge`, `MeasurementComparison`, `ScenarioBanner`.
- `AttachmentGallery`, `AuditTimeline`, `ImportWizard`, `ExportDialog`.

Todos devem ter estados loading, empty, success, error e forbidden quando aplicáveis. Tabelas precisam distinguir “nenhum cadastro” de “nenhum resultado para esses filtros”. Detalhes removidos/arquivados são diferentes de API indisponível. Evitar toast como única forma de explicar erro persistente.

## Mapa de páginas e funções

| Rota UI | Conteúdo e ações |
| --- | --- |
| `/login` | Login, erros seguros, sessão; sem cadastro público |
| `/dashboard` | Totais reais, ocupação, incompletudes, atividade, atalhos filtrados |
| `/map` | Camadas, busca, seleção, desenho, edição, filtros, mapa/trace sincronizados |
| `/sites`, `/sites/[id]` | POPs/locais, posição, equipamentos, anexos, histórico |
| `/structures`, `/structures/[id]` | Todos os tipos de estrutura, localização, estado |
| `/poles`, `/poles/[id]` | Visão filtrada de postes, cabos associados |
| `/ceos`, `/ceos/[id]` | CEOs, bandejas quando cadastradas, cabos, fibras, editor de fusões |
| `/ctos`, `/ctos/[id]` | CTOs, portas, reservas, splitter, atendimentos, potência |
| `/devices`, `/devices/[id]` | OLTs/DIOs/ONUs, fabricante/modelo/serial, portas e perfis |
| `/cables`, `/cables/[id]` | Cabo, segmentos, tubos/fibras, mapa, ocupação, impacto |
| `/splitters`, `/splitters/[id]` | Modelo, entradas/saídas, perdas por onda/porta, conexões |
| `/customers`, `/customers/[id]` | Cliente, atendimento/ONU, caminho, medições e anexos |
| `/topology` | Busca de terminal, rastreamento, caminho e contexto do mapa |
| `/optical-budget` | Atendimento, direção, parâmetros, breakdown e margem |
| `/measurements` | Leituras manuais, filtros, histórico e comparações válidas |
| `/simulations` | Cenários temporários de perdas/divisão e rompimento |
| `/reports` | Capacidade, fibras/portas, qualidade da documentação, exportação |
| `/imports` | Upload, mapeamento, preview, erros, commit, progresso |
| `/exports` | Histórico de solicitações e downloads autorizados |
| `/audit` | Histórico por entidade, ator, ação e período |
| `/settings` | Nome da operação, fuso, mapa, unidades, limites autorizados |
| `/settings/catalogs` | Modelos de cabos/cores/equipamentos e perfis ópticos |
| `/settings/users` | Gestão de usuários e permissões, admin |
| `/profile` | Preferências locais, dados próprios, troca de senha/logout |

As visões filtradas reutilizam formulários e detalhes comuns. Não duplicar regras de CTO em três componentes independentes. Listas abrem detalhe persistente por URL; painel no mapa oferece “Abrir ficha completa”. Breadcrumbs e botão de voltar preservam contexto de busca.

## Etapas de implementação

### F01 — Fundação e cliente de API

```text
Prepare Next.js/TypeScript strict, Tailwind, shadcn/ui, Lucide, Query/Table, React Hook Form/Zod e MapLibre em versões compatíveis verificadas. Organize src/app, components/ui, components/layout, features/{map,inventory,connectivity,optical,...}, lib/api, lib/permissions, lib/format e tests.
Gere tipos a partir de contracts/openapi.json. Crie cliente central com cookies, CSRF, timeout, AbortSignal, Problem Details e request_id. Não retry automático de POST/commit; retries de leitura limitados. Separe estado remoto (Query), URL (filtros) e estado efêmero de UI. Zustand só se houver necessidade entre componentes; não duplicar cache remoto.
Crie scripts lint, typecheck, test, build e geração de tipos. Fixtures só em modo explícito, sem fallback silencioso.
Aceite: build reproduzível; requests canceláveis; 401/403/409/412/422 tratados; cliente não converte falha em lista vazia; nenhum segredo em NEXT_PUBLIC_*.
```

### F02 — Design system, shell e navegação

```text
Implemente shell, menu agrupado em Visão geral, Rede, Engenharia e Administração, busca global, breadcrumbs e tema claro/escuro. Use mapa de páginas e ícones deste documento. Guarde preferências visuais locais sem dados sensíveis.
Crie componentes compartilhados e catálogo de estados em rota de desenvolvimento ou histórias de componentes. Botões destrutivos exigem confirmação com nome/efeito; botão salvar mostra pendência e impede repetição. Preserve foco após modal e nomes acessíveis.
Aceite: navegação inteira funciona; rotas ainda não entregues são marcadas no ambiente de desenvolvimento e não anunciam recurso pronto; teclado percorre shell/dialogs; layout utilizável em 360, 768 e 1440 px; contraste medido nos dois temas.
```

### F03 — Login, sessão e acesso

```text
Implemente /login, sessão por /auth/me, CSRF, logout e /profile com troca de senha. Login deve usar cookie seguro do backend, sem token em storage. Redirecionamento de retorno aceita apenas caminho local válido.
Use permissions para proteger rotas e ações visuais. Viewer lê rede/relatórios; technician registra fotos/medições/observações; engineer altera rede; admin gerencia usuários/configurações. Não habilite edição de topologia para technician. Backend continua validando tudo.
Trate expiração de sessão preservando rascunho somente em memória enquanto possível; não guardar dados de clientes em storage persistente por padrão. Limpe cache de dados no logout/troca de usuário.
Aceite: login válido/inválido, sessão expirada, CSRF recusado, rota proibida e logout têm fluxo verificável; voltar no browser não revela cache de usuário anterior; acesso por URL direta não contorna proteção.
```

### F04 — Tabelas, formulários e conflitos

```text
Implemente padrões reutilizáveis de tabela com paginação/ordenação no servidor, filtros na URL, busca com debounce, colunas opcionais e seleção por IDs. Deixe explícito se seleção é da página ou de todos os resultados; não aplicar ação em massa implícita.
Formulários com schema, campos obrigatórios, ajuda contextual, erros de API junto ao campo, foco no primeiro erro e alerta de alterações não salvas. Números pt-BR aceitam vírgula para digitação e serializam número JSON correto; rejeite separadores ambíguos. Use unidades visíveis.
Envie If-Match em PATCH/DELETE. Em 412/409, mantenha rascunho, mostre versão remota e permita recarregar/comparar; não sobrescreva automaticamente. Conexão óptica não usa optimistic update de sucesso antes do backend.
Aceite: filtros sobrevivem refresh/voltar; ordem estável; rede lenta não duplica registro; NaN/null/zero distinguidos; teste de conflito com dois contextos de browser.
```

### F05 — Dashboard e busca global

```text
Implemente /dashboard e busca global usando endpoints reais. Exiba POPs/CTOs/cabos cadastrados, ocupação documentada, portas livres/reservadas/conectadas e problemas de documentação. Todos os cards abrem lista com filtro correspondente.
Busca Ctrl/Cmd+K com resultados por tipo/código/nome, debounce, cancelamento e limite. Não interceptar atalho dentro de componentes que precisem dele sem alternativa. Resultados respeitam permissões.
Aceite: valores correspondem à fixture/API, sem gráficos aleatórios; empty state orienta cadastrar/importar; falha de endpoint não mostra zero como dado verdadeiro; todos os atalhos levam à entidade correta.
```

### F06 — Mapa operacional

```text
Implemente MapLibre em componente cliente carregado adequadamente para não acessar window durante SSR. Estilo, tiles e atribuição configuráveis; não assumir serviço público de OSM ilimitado nem chave comercial obrigatória. MapLibre é renderizador, não provedor de mapas base.
Camadas: sites, postes, CEOs, CTOs, equipamentos localizáveis, cabos por função, drops e clientes quando autorizados. Cabos por layers WebGL, não milhares de elementos DOM. Atualize dados por bbox/zoom no moveend com debounce e cancelamento. Evite resposta antiga sobrescrever área nova.
Implemente legenda, escala, zoom, seleção, fitBounds, painel contextual, filtros, busca e URL com centro/zoom/seleção. Controle de geolocalização somente após clique e permissão; permitir recusa sem bloquear app. Coordenadas não são conectividade.
Aceite: navegar e selecionar leva ao cadastro; eventos/fontes/layers limpos no unmount; atribuição visível; aviso em truncamento, indisponibilidade de tiles ou WebGL; alternativa em lista para navegação sem mapa.
```

### F07 — Desenho e edição geográfica

```text
Implemente modos explícitos visualizar/criar ponto/desenhar cabo/editar geometria. Mostre ferramenta ativa, instruções curtas, cancelar, salvar e desfazer/refazer local. Para edição de linha, vértices arrastáveis e inserção/remoção; snap a estruturas é auxílio visual, nunca cria fusão.
Primeiro selecionar tipo e endpoints de cadastro, depois desenhar e revisar dados. Distância durante desenho é prévia; backend confirma map_length_m. Exiba separadamente comprimento do mapa, medido total e reserva; regra óptica está em backend.md.
Salvar persiste após validação; cancelar restaura geometria; sair com rascunho exige confirmação. Não executar undo local como exclusão de alterações já salvas por outros usuários. Implemente alternativa acessível por formulário/lista de coordenadas.
Aceite: criar POP/CTO/cabo, editar vértice, desfazer, cancelar e reabrir persistido; conflito preserva rascunho; rota inválida exibe erro; arrastar caixa não move todos os cabos sem decisão explícita.
```

### F08 — Cadastros de rede física

```text
Implemente páginas/listas/detalhes de sites, structures, postes, CEOs, CTOs, devices e splitters com componentes reutilizados e formulários por tipo. Detalhes com abas Visão geral, Conexões/portas, Mapa, Anexos e Histórico conforme entidade.
Campos: código/nome, tipo, localização, estado administrativo, condição, fabricante/modelo/serial quando aplicável, observações. Serial de equipamento não é código de estrutura. Devices ficam em site ou structure conforme contrato.
Ações: criar, editar, arquivar, mostrar no mapa, abrir conexões, anexar foto e ver histórico, cada uma por permissão. Dados de interface não podem trocar installed por connected: são dimensões diferentes.
Aceite: CRUD real persiste após reload; detalhe mostra dependências antes de desativar; estado arquivado legível; ações indisponíveis explicam motivo; erro de FK não vira mensagem genérica sem orientação.
```

### F09 — Cabos, tubos e fibras

```text
Implemente /cables e detalhe com resumo, mapa, segmentos, tubos/fibras, capacidade e histórico. Exiba números globais de fibras, número/posição no tubo, cor textual+swatch, extremidades A/B, reservas e conexões. Identidade inclui cabo+segmento+fibra+extremidade.
Filtre por tubo, número e ocupação; virtualize grandes listas. Geração de fibras vem do modelo no backend. Não permitir editar quantidade livre manualmente.
Crie fluxo de dividir segmento com prévia e explicação de fibras contínuas/cortadas. Coordenadas e trechos devem ser revisados antes do commit. Preserve vínculo de identidade e permita mostrar o impacto da operação retornado pela API.
Aceite: fibras de mesma cor em tubos diferentes nunca se confundem; cabo conectado em A e B aparece corretamente; reduzir capacidade usada é bloqueado; dividir não inventa fusões; totais batem com backend.
```

### F10 — Editor de fusões e terminais

```text
Implemente editor em CEO/CTO/DIO com painéis de cabos/tubos/fibras e portas/splitters, linhas de conexão e tabela textual equivalente. Use ID de terminal como chave, nunca rótulo/cor/posição visual. Mostre cabo, trecho, tubo, fibra, A/B e localização em toda seleção.
Fluxo: escolher terminal livre → escolher destino compatível → selecionar fusão/patch/continuidade permitida → revisar perda e motivo → adicionar ao lote → confirmar lote. Mostre conexão existente e ação separada de desconectar. O backend confirma compatibilidade/ocupação.
Permita seleção por teclado e formulário como alternativa ao arrastar. Pan/zoom/reorganização visual não alteram conectividade. Portas frente/trás e entrada/saída do splitter têm representação distinta.
Batch usa expected_topology_revision; conflito recarrega dados para reconciliação manual preservando propostas locais. Não salvar metade de lote inválido. Antes de desconectar, mostrar relações afetadas disponíveis.
Aceite: conexão real persiste e aparece no trace; terminal ocupado não recebe segunda ligação; cabo sem corte usa continuidade; desfazer antes do envio só altera rascunho; nenhuma linha é salva só porque foi desenhada.
```

### F11 — CTOs, clientes e atendimento

```text
Implemente grade de portas numeradas, status textual/símbolo, filtro e lista acessível. Clique abre origem óptica, reserva, patch/drop, ONU/cliente e histórico. Estado danificado é condição separada de ocupação.
Crie fluxo de atendimento: selecionar cliente ou cadastrar → selecionar CTO/porta disponível → informar ONU e drop/conexões conforme API → revisar → salvar transacionalmente pelo contrato. Não assumir que criar cliente já conecta fisicamente a porta. Mostre conectado sem cliente como situação válida.
Implemente reserva/liberação com responsável, motivo e expiração quando oferecida. Perfil viewer recebe dados pessoais limitados conforme servidor. Desativação de service_link preserva histórico.
Aceite: CTO de 8 portas com 3 conectadas e 1 reservada mostra 4 livres; concorrência na mesma porta mostra conflito; detalhes do cliente abrem caminho correto; nenhum dado pessoal em URL/logs desnecessários.
```

### F12 — Rastreamento e topologia

```text
Implemente /topology e ação Rastrear em fibra/porta/cliente. Solicite terminal e direção quando ambíguos; envie ao backend. Mostre caminho em lista ordenada e diagrama com tipos de elemento, portas, localização e ligação para ficha.
Sincronize seleção do step com destaque de segmento/ponto no mapa. Cabos compartilhados não significam que todas as fibras atendem o cliente. Splitters exibem ramo selecionado e opção de expandir resultados disponíveis.
Mostre complete/incomplete/ambiguous/cycle_detected/limit_exceeded com explicação e terminais não resolvidos. Exiba revisão e opção recalcular após alteração. Não construir caminho próprio com linhas próximas no mapa.
Aceite: escolher cliente destaca rota correspondente; clique no step abre entidade correta; ponta aberta é visível; ciclo não trava browser; ramificações grandes podem ser expandidas progressivamente sem ocultar truncamento.
```

### F13 — Orçamento óptico e potência

```text
Implemente /optical-budget e aba de atendimento com direção downstream/upstream, onda, perfis e margem. Envie parâmetros ao backend; resultado oficial vem da API. Prévia local, se existir, deve ser rotulada e nunca substituir resultado salvo/revisionado.
Mostre TX em dBm, perda total em dB, RX previsto em dBm, sensibilidade, limite de sobrecarga, margem de engenharia, margem restante e revisão. Breakdown por fibra/fusão/conector/splitter com perda individual/acumulada, origem do dado e links. Renderize tabela e gráfico acessível se agregar compreensão.
Estados: aprovado, margem baixa, abaixo da sensibilidade, sobrecarga e dados insuficientes. Mostre campos faltantes e premissas. Não classificar todo RX negativo como ruim nem margem de engenharia como perda física.
Aceite com fixture sintética: TX +3; perda 23,75; RX -20,75; sensibilidade -27; margem engenharia 3; margem restante 3,25. Formatação pt-BR preserva sinal e unidade. Null não vira zero. Trocar direção muda perfil/receptor/onda conforme contrato.
```

### F14 — Medições e simulações

```text
Implemente /measurements com leitura manual, direção, onda, receptor, data/hora, instrumento/origem e observações. Mostre histórico e comparação somente quando compatível; medição antiga tem timestamp visível. Perda excedente = previsto - medido; -19,3 e -25,4 produzem +6,1 dB.
Implemente /simulations com banner permanente “Simulação — rede operacional não alterada”, cenário temporário, seleção de segmentos para rompimento e overrides de perda/comprimento/splitter. Mostre antes/depois, premissas, affected/unaffected/unknown e resultados já desconectados antes do cenário.
Evite afirmar localização de falha a partir de RX isolado. Não disponibilize botão Aplicar cenário se não houver caso de uso transacional próprio no backend. Alterar quantidade de portas do splitter exige mapeamento explícito.
Aceite: encerrar cenário devolve vista operacional; não há mutação da revisão de rede; impacto não duplica clientes; alerta não compara ondas/receptores diferentes; cenários incompletos deixam incerteza visível.
```

### F15 — Fotos, documentos e histórico

```text
Implemente galeria, captura mobile via input apropriado, upload com progresso quando suportado, cancelamento e erros de tamanho/tipo. Aceite tipos permitidos pelo backend; não confiar apenas no accept do input. Mostre miniatura, legenda, autor, data e download autorizado.
Revogue Object URLs; limite previews em memória; não renderize HTML vindo de anotação/anexo. PDF tem visualização segura ou download. Remover exige permissão e confirmação; cancelamento não deve deixar UI de sucesso.
Implemente AuditTimeline por entidade com antes/depois legíveis, ator, motivo e horário. Eventos não são editáveis pelo usuário comum.
Aceite: anexo persiste e reabre após reload, upload interrompido é recuperável/repetível sem duplicação silenciosa, foto inválida mostra erro, log não expõe token/senha, histórico de conexão é compreensível por operador.
```

### F16 — Importação e exportação

```text
Implemente wizard de importação: arquivo → mapeamento/CRS → preview → erros/duplicatas → resumo → confirmar → job → resultado. Preview não modifica mapa operacional. Mostre contagem por ação e lista de erros com linha/feature. Commit usa chave de idempotência por tentativa lógica, não nova chave a cada retry de rede.
Polling com intervalo moderado, cancelamento no unmount e retomada por URL. Exiba progresso real quando disponível ou estado indeterminado honesto. Distinga cancelamento solicitado de cancelado e mostre alterações parciais se o contrato permitir chunks.
Exportação permite formato/filtros, solicita job, apresenta histórico e link de download autorizado; não montar CSV de toda rede carregando tudo no browser.
Aceite: duplicar clique não duplica importação; erro não some no toast; refresh retoma job; prévia mostra geometrias sem criar conexões automáticas; download expirado tem nova solicitação possível.
```

### F17 — Relatórios, configuração e usuários

```text
Implemente relatórios de capacidade, portas/fibras, potência e qualidade da documentação com filtros de site/região/estado suportados, tabela, data de referência e export. Defina claramente conectada, reservada, livre e não documentada. Capacidade isolada não é garantia de rota disponível.
Implemente settings por permissão: nome, fuso, tema/padrão local, mapa base/atribuição e parâmetros oferecidos pelo servidor. Catálogos incluem padrões de cores, modelos e perfis ópticos com fonte e revisão. Segredos não aparecem em campos GET.
Admin gerencia usuários/roles, confirmação de desativação e proteção de último admin. Tela de perfil troca senha e encerra sessão. Não oferecer controle de cobrança ou planos.
Aceite: export respeita filtro; total da tabela bate com relatório; configuração inválida é validada; usuário sem permissão não vê ação e recebe tratamento de 403; tema/fuso não alteram unidades armazenadas.
```

### F18 — Campo, acessibilidade e desempenho

```text
Revise mobile para uso de campo: alvos de toque confortáveis, ações principais acessíveis, painel de detalhe ajustável, câmera, coordenadas copiáveis e navegação mapa/ficha sem perder contexto. Não exigir hover. Não prometer edição offline: nesta versão perda de conexão mostra aviso, bloqueia confirmação e mantém rascunho em memória quando seguro.
Verifique labels, foco, tab order, diálogos, contraste, leitores de tela, mensagens aria-live sem excesso e redução de movimento. Mapa e editor têm alternativas em listas/formulários. Cores das fibras incluem número/nome para daltonismo.
Meça carregamento, bundles, pan/zoom e tabelas com fixtures grandes. Lazy load de mapa/editor, renderização por layers, paginação/virtualização, query cancellation e cleanup. Documente dispositivo/volume/resultados; não declarar fluidez universal sem medição.
Aceite: jornadas principais funcionam em 360 px e teclado; sem scroll horizontal da página inteira; rede perdida não gera falso salvo; erro de WebGL não bloqueia inventário; não há crescimento de listeners após navegar repetidamente.
```

### F19 — Testes integrados e qualidade

```text
Implemente Vitest/Testing Library para comportamento relevante e Playwright para jornadas reais contra backend de teste PostgreSQL/PostGIS com seed sintético. Use mocks de contrato apenas para estados difíceis de reproduzir, nunca como única evidência de integração.
Jornadas: login por papel; criar POP/CTO/cabo; desenhar e cancelar; editar geometria; fusão válida/inválida; reserva e atendimento; trace; orçamento numérico; medição; impacto; upload; import/export; logout. Teste conflitos em dois contextos de browser, sessão expirada, 403, 422, timeout, API 500, tiles indisponíveis e dados incompletos.
Rode typecheck, lint, unitários, build e E2E pertinentes. Confira deriva de OpenAPI/tipos e ausência de mocks no build de produção. Inclua verificação automática de acessibilidade e revisão manual dos fluxos de mapa/editor.
Aceite: evidências reproduzíveis por comando; testes validam persistência após reload, não apenas toast; screenshot ajuda a revisar layout mas não substitui teste de ação; falhas/bloqueios são listados explicitamente.
```

### F20 — Entrega e revisão de produto

```text
Revise todas as páginas e ações contra este documento. Para cada rota registre implementado/parcial/bloqueado, endpoint, permissão e teste. Elimine botões mortos, textos de scaffold, números inventados, dados demo em produção e divergência de unidade/estado.
Finalize Dockerfile do frontend e integração Compose/Caddy: mesma origem, /api/* encaminhado ao FastAPI, estáticos/Next nas rotas corretas. Não incluir lógica óptica no proxy/Next. Configure CSP compatível com workers/tiles do mapa usando origens necessárias; valide sem liberar tudo por conveniência.
Documente instalação, variáveis públicas seguras, mapa base/atribuição, geração de tipos, testes, contribuição e guia curto de operação: cadastrar → conectar → rastrear → calcular → medir. Prepare demo opt-in consistente com fixture do backend.
Aceite: instalação limpa abre app; fluxo completo real funciona após restart; nenhum dado de outro usuário no cache; todas as limitações constam do relatório final; não marcar pronto com erro crítico pendente.
```

## Cenário de demonstração e aceite transversal

Usar IDs gerados e códigos humanos estáveis, sem dados pessoais reais:

1. POP-DEMO com OLT-DEMO, PON 1/1/1 e DIO-DEMO.
2. Cabo de alimentação com trecho até CEO-DEMO e fibra identificada por tubo/número/extremidade.
3. CEO com splitter 1:8 e conexões explícitas.
4. Distribuição até CTO-DEMO, segundo splitter 1:8, porta de atendimento e drop até ONU-DEMO.
5. Cliente sintético DEMO-001 associado ao atendimento documentado.
6. Fixture óptica que totaliza exatamente 7 km, quatro fusões, dois pares acoplados e dois splitters, conforme B10/F13. A localização de cada perda deve estar na fixture; não adicionar perdas extras implicitamente ao desenhar o cenário.
7. Ramos adicionais com porta livre/reservada, fibra danificada, ponta aberta e parâmetro óptico ausente para demonstrar estados reais.

O usuário deve conseguir clicar no cliente, ver caminho, abrir a fibra, conferir a fusão, calcular RX, registrar medição e simular rompimento do segmento correspondente. Alterar um elemento e voltar à tela anterior deve atualizar/invalidate os dados relevantes e indicar quando um cálculo precisa ser refeito.

## Coordenação e sequência recomendada

| Marco | Backend necessário | Frontend |
| --- | --- | --- |
| Fundação/contrato | B01–B03 | F01–F04 |
| Rede física | B04–B06 | F05–F08 |
| Rede óptica | B07–B09 | F09–F11 |
| Engenharia | B10–B12 | F12–F14 |
| Operação | B13–B15 | F15–F17 |
| Entrega | B16–B18 | F18–F20 |

F09 depende também da segmentação de B06; F12 usa B09; F13 usa B10; F14 usa B11/B12. Quando faltar endpoint, registrar bloqueio no progresso e desenvolver apresentação com fixture tipada explícita, sem declarar a integração concluída.

## Prompt de retomada

```text
Leia frontend.md, backend.md, docs/progress-frontend.md e o estado real do repositório. Identifique a última etapa com critérios atendidos e os endpoints disponíveis. Não refaça o design system nem substitua componentes saudáveis. Resuma estado em até 10 linhas, execute a próxima etapa pendente e atualize progresso. Preserve contratos e fluxos já verificados.
```

## Prompt de revisão visual e funcional

```text
Revise a etapa F__ em desktop e mobile. Para cada ação, confirme destino/endpoint, permissão, loading, success, empty, error e persistência quando aplicável. Navegue com teclado. Procure unidade errada, status contraditório, contraste ruim, sobreposição no mapa, perda de rascunho e resposta antiga sobrescrevendo dados novos. Corrija problemas com evidência. Não trate screenshot bonito como prova de funcionamento.
```

## Referências técnicas

As fontes fundamentam escolhas de integração, sem fixar uma versão supostamente atual:

- [Next.js — componentes de servidor e cliente](https://nextjs.org/docs/app/getting-started/server-and-client-components): interfaces interativas e APIs do browser ficam na fronteira cliente apropriada.
- [MapLibre GL JS — documentação](https://maplibre.org/maplibre-gl-js/docs/): mapa interativo baseado em fontes, layers e estilo configurável.
- [FastAPI — OpenAPI e recursos](https://fastapi.tiangolo.com/features/): geração do contrato que alimenta os tipos do frontend.
- [PostGIS — comprimento e unidades](https://postgis.net/docs/ST_Length.html): cálculo geográfico pertence ao backend; mostrar comprimento em metros, não graus.
