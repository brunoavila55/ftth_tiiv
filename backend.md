# Backend — Prompts para desenvolver um sistema FTTH open source

Este documento é uma especificação de desenvolvimento e uma sequência de prompts executáveis. Projeto: aplicação web self-hosted para documentação física e óptica de uma rede FTTH, sem objetivo comercial. Nome provisório: **FTTH Manager**. Complemento obrigatório: `frontend.md`.

## Como usar

1. Entregue os dois documentos à IA que trabalhará no repositório.
2. Execute o **prompt mestre** e depois os prompts B01–B18, na ordem. Cada etapa deve produzir código funcional, migrations quando necessárias, documentação e evidências dos critérios de aceite.
3. Não peça para implementar tudo em uma única resposta. Uma etapa pode exigir várias sessões; termine uma fatia funcional antes de avançar.
4. Em uma sessão nova, use o prompt de retomada ao final. O progresso deve ficar em `docs/progress-backend.md`.
5. Os blocos de especificação deste documento fazem parte de todos os prompts, mesmo quando não são repetidos.
6. Estas são decisões propostas para o projeto, não descrição de software já implementado. As versões citadas na conversa anterior não são requisitos: valide compatibilidade nas fontes oficiais e fixe versões estáveis no momento da implementação.

## Prompt mestre — papel, objetivo e regras

```text
Atue como engenheiro de backend responsável pelo FTTH Manager. Leia backend.md e frontend.md integralmente e inspecione o repositório e suas instruções antes de modificar arquivos. Implemente a etapa solicitada, não apenas uma proposta.

Objetivo: aplicação open source, self-hosted, para uma operação FTTH, com inventário, GIS, conexões fibra a fibra, splitters, clientes, rastreamento óptico, impacto de rompimento, cálculo de potência, fotos e auditoria. Uma instalação atende uma organização. Não implementar billing, planos, multitenancy, Kubernetes nem banco de grafo nesta versão.

Stack: Python, FastAPI, Pydantic, SQLAlchemy 2, GeoAlchemy2, Alembic, PostgreSQL/PostGIS, pytest, Ruff e verificação estática de tipos. Use uv e lockfile. Arquitetura monólito modular; domínio óptico independente de HTTP e banco. Frontend Next.js/TypeScript consome REST. Deploy Docker Compose e Caddy. Arquivos em volume local por uma interface de storage; S3 é extensão futura. Redis e workers externos só após necessidade comprovada.

Adote SQLAlchemy síncrono com psycopg e endpoints compatíveis com esse modelo; não bloqueie o event loop em rotas async. Use transações explícitas nos casos de uso. Não monte uma arquitetura genérica de abstrações sem consumidor real.

Regras: integridade no banco, autorização no servidor, validação forte, migrações revisadas, alterações auditadas e erros estruturados. Nenhum segredo em código. Nenhum dado fictício em produção. Nenhum placeholder em uma funcionalidade declarada pronta. Não deduza conectividade óptica por proximidade geográfica. Não trate estimativa de potência como medição.

Antes de codificar: identifique dependências e conflitos com o contrato compartilhado. Tome decisões reversíveis e documente-as. Pergunte somente quando faltar uma decisão que realmente bloqueie o trabalho. Não apague trabalho existente nem publique serviços sem autorização correspondente.

Ao concluir: informe arquivos alterados, migrações, comandos executados e seus resultados, critérios atendidos, limitações reais e próximo passo. Nunca diga que um teste passou se não foi executado. Atualize docs/progress-backend.md. Se uma ferramenta estiver indisponível, registre o bloqueio e entregue o que puder ser verificado.
```

## Arquitetura e divisão de responsabilidade

Estrutura alvo; diretórios são criados conforme surgirem implementações:

```text
ftth-manager/
  backend/
    app/
      main.py
      core/            # configuração, sessão, permissões, erros, logs
      api/v1/          # routers e dependências HTTP
      modules/
        identity/
        inventory/
        gis/
        connectivity/
        topology/
        optical/
        customers/
        attachments/
        imports/
        reports/
        audit/
      db/              # base, sessões e tipos compartilhados
      cli/             # bootstrap admin, backup helpers, demo
    migrations/
    tests/{unit,integration,contract}/
    pyproject.toml
    uv.lock
    Dockerfile
  frontend/
  contracts/openapi.json
  docs/{adr,runbooks}/
  compose.yaml
  .env.example
  README.md
```

Fluxo: router → schema → caso de uso → domínio/repositório → banco. Routers não contêm regras de fusão ou orçamento óptico. Repositórios não fazem commits isolados durante uma operação composta. A transação que cria a conexão também cria sua auditoria e incrementa a revisão de topologia.

## Contrato compartilhado v1 — manter igual ao frontend

O backend é proprietário do schema OpenAPI; `contracts/openapi.json` é exportado da aplicação e versionado. O frontend gera tipos a partir dele. Este texto define o contrato inicial; mudanças exigem atualizar ambos os documentos e os testes de contrato. Não manter tipos manuais divergentes.

| Aspecto | Decisão |
| --- | --- |
| Prefixo | `/api/v1` |
| Identificadores | UUID em string; códigos humanos em `code` |
| JSON | `snake_case`; enums em inglês, interface traduz em pt-BR |
| Datas | ISO 8601 com timezone, persistência UTC |
| Unidades | comprimentos `*_m`, perdas `*_db`, potência `*_dbm`, onda `wavelength_nm` |
| Coordenadas | GeoJSON WGS84/EPSG:4326, `[longitude, latitude]` |
| Listas | `{items, total, page, page_size}`; página inicial 1, padrão 50, máximo 200 |
| Filtros | `q`, `status`, `page`, `page_size`, `sort`; sort permitido por endpoint, desempate por id |
| Escritas | POST cria; PATCH altera campos fornecidos; null apenas nos campos anuláveis |
| Concorrência | `version` inteiro no recurso; PATCH/DELETE exigem `If-Match: "<version>"` |
| Falhas de concorrência | 428 sem precondição; 412 versão desatualizada; 409 conflito de negócio |
| Erros | `application/problem+json`: `type,title,status,detail,code,request_id,errors` |
| Validação | 422; `errors` lista de `{field,code,message}` |
| Sessão | cookie opaco HttpOnly; Secure em produção; SameSite=Lax; sem JWT no localStorage |
| CSRF | `GET /auth/csrf` retorna `{csrf_token}` e cookie de vínculo; escritas enviam `X-CSRF-Token`; validar Origin |
| Perfis | `admin`, `engineer`, `technician`, `viewer` |
| Revisão de rede | `topology_revision` monotônica, incrementada em mutações que afetam caminhos ou perdas |
| Processamento | importações/exportações demoradas retornam job; polling HTTP nesta versão |

Autenticação: `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`, `GET /auth/csrf`, `POST /auth/change-password`. CSRF também no login/logout. `GET /auth/me` retorna `{id,name,email,role,permissions}`. Não retornar hashes ou segredos. Sem cadastro público; administração cria usuários e recuperação de acesso inicial usa CLI segura.

Recursos principais: `/sites`, `/structures`, `/devices`, `/ports`, `/cables`, `/cable-segments`, `/splitters`, `/connections`, `/customers`, `/service-links`, `/optical-profiles`, `/measurements`, `/users`. CRUD apenas onde faz sentido; fibras são geradas pelo modelo de cabo, não criadas avulsas pelo cliente HTTP. CEO/CTO/poste são tipos de `structure`; OLT/DIO/ONU são tipos de `device`; splitter tem recurso próprio. Cadastro de CTO: `/structures?kind=cto`, detalhe `/structures/{id}`.

| Operação especializada | Contrato inicial |
| --- | --- |
| Dashboard | `GET /dashboard/summary` |
| Busca global | `GET /search?q=...&limit=20`; agrupada por tipo, autorizada |
| Mapa | `GET /map/features?bbox=minLon,minLat,maxLon,maxLat&layers=ctos,cables&zoom=...` |
| Fibras | `GET /cable-segments/{id}/fibers` paginado |
| Ocupação CTO | `GET /structures/{id}/occupancy` |
| Conteúdo CEO | `GET /structures/{id}/connectivity` |
| Conexões em lote | `POST /connections/batch` com `expected_topology_revision` e operações tipadas |
| Rastrear | `POST /topology/trace` com `start_terminal_id,direction,max_results` |
| Rompimento | `POST /topology/impact` com `cable_segment_ids,expected_topology_revision` |
| Orçamento | `POST /optical/budgets` com `service_link_id,direction,profile_id,engineering_margin_db` |
| Simulação | `POST /optical/simulations` com referência ao caminho e overrides explícitos |
| Anexos | `POST /attachments` multipart; `GET /attachments/{id}/download`; DELETE versionado |
| Auditoria | `GET /audit-events` filtrado e paginado |
| Importação | `POST /imports/preview`; `GET /imports/{id}`; `POST /imports/{id}/commit` |
| Exportação | `POST /exports`; `GET /exports/{id}`; `GET /exports/{id}/download` |
| Jobs | `GET /jobs/{id}`; `POST /jobs/{id}/cancel` |
| Configuração | `GET /settings`; `PATCH /settings`; segredos nunca retornados |

Mapa responde FeatureCollection com `features`, `bbox`, `topology_revision`, `truncated`. Cada feature contém `id`, `geometry` e `properties` com `entity_id,entity_type,code,status,version`; ocupação agregada quando aplicável. Estabelecer limite de features e retornar `truncated=true` de forma explícita. Não truncar silenciosamente. Formato de mapa é exceção ao envelope paginado.

Rastreamento retorna `topology_revision`, `status` (`complete`, `incomplete`, `ambiguous`, `cycle_detected`, `limit_exceeded`), `paths`, `warnings` e `unresolved_terminals`. Cada caminho tem `path_id` identificado pela revisão, terminais inicial/final e `steps` ordenados. Cada step inclui tipo, entidade, terminais de entrada/saída, localização e dados de comprimento/perda disponíveis. `downstream` segue PON → ONUs; `upstream` segue ONU → PON. Rastrear fibra sem orientação inequívoca exige terminal e contexto; não escolher a menor rota geométrica.

Orçamento retorna `status` (`complete` ou `insufficient_data`), `direction`, `wavelength_nm`, `topology_revision`, `assumptions`, `missing_fields`, `steps`, `total_loss_db`, `tx_dbm`, `predicted_rx_dbm`, `rx_min_dbm`, `rx_max_dbm`, `engineering_margin_db`, `remaining_margin_db`, `overload_headroom_db`, `assessment`. Valores não calculáveis são null, nunca zero fictício. `assessment`: `pass`, `low_margin`, `below_sensitivity`, `overload`, `unknown`. `steps` incluem perda individual e acumulada, unidade, origem do parâmetro e referência do elemento.

## Modelo físico e óptico obrigatório

### Identidade e inventário

- `site`: POP/armário/local técnico, código, nome, ponto e estado.
- `structure`: poste/CEO/CTO/caixa de passagem, código, ponto, capacidade e estado; relação opcional com site.
- `device`: OLT/DIO/ONU, fabricante, modelo, serial e localização. Localização em site ou structure por FKs explícitas e CHECK de exclusividade.
- `port`: pertence a device ou structure, com FKs e CHECK exatamente um proprietário; nome, função e capacidade. Porta de CTO é porta explícita, não contador editável.
- `cable`: identidade física, código, modelo, quantidade de fibras, organização de tubos, padrão de cores e estado.
- `cable_segment`: trecho do cabo entre dois locais de acesso; geometria, comprimento medido opcional, comprimento geográfico e reservas. Uma rota atravessar poste não obriga uma emenda nem uma nova segmentação óptica.
- `tube` e `fiber`: identidade lógica dentro do cabo. `fiber` tem número global no cabo e posição no tubo; ambos verificáveis. Cores são rótulos configuráveis, nunca chaves de identidade.
- `fiber_segment`: materializa uma fibra em um segmento de cabo; possui exatamente duas extremidades A/B representadas por `terminal`.
- `splitter`: localização, modelo e portas explícitas de entrada/saída; perdas por saída e comprimento de onda. Primeira versão implementa 1:N, incluindo divisão desigual cadastrada por porta. Não fingir suporte a 2:N.
- `customer`: código, nome de exibição e dados mínimos de contato opcionais. `service_link`: relação entre cliente, ONU e atendimento documentado; mantém histórico, não sobrescreve silenciosamente uma ativação anterior.

### Terminais, conexões e integridade

O grafo utiliza **terminais**, não caixas como vértices suficientes. Uma CTO pode conter portas de circuitos diferentes. Conectar caixas inteiras geraria caminhos falsos.

- `terminal`: identidade referenciável por FK. Subtipos normalizados ligam terminal à extremidade de fiber_segment, lado de porta ou porta de splitter; implementar integridade de exatamente um subtipo, inclusive em SQL direto, por constraints/triggers quando necessário.
- Portas passivas passantes de DIO/CTO possuem lados frente/trás e uma travessia interna explícita. Porta PON e porta óptica ONU são terminais de transmissão/recepção. Não criar uma travessia interna onde ela não existe.
- Arestas internas representam fibra A↔B, travessia de adaptador e entrada↔saída específica do splitter. Arestas externas representam fusão, patch cord e continuidade documentada.
- `connection` possui dois terminais distintos e tipo validado. Tabela `connection_endpoint` com unicidade de terminal em conexão ativa evita que a mesma ponta seja usada em duas ligações. Uma fibra pode estar conectada em A e em B, cada uma uma única vez.
- Fusões somente entre extremidades compatíveis e no mesmo local. Patches também exigem localização e compatibilidade. Continuidade em acesso intermediário mantém fibra sem corte; não conta uma fusão inexistente.
- Ligação interna de splitter permite apenas entrada↔saída; nunca saída↔saída no algoritmo de travessia. Uma aresta de grafo genérica sem esta semântica produz caminhos errados.
- Perdas pertencem a elementos de travessia identificáveis. Definir contabilização única de par acoplado/conector, patch cord, fusão e splitter para impedir perda duplicada.
- Separar estado administrativo (`planned`, `installed`, `retired`), condição física (`ok`, `damaged`, `unknown`) e ocupação (`free`, `reserved`, `connected`). Ocupação física conectada não implica cliente ativo.
- Reserva tem responsável, motivo e expiração opcional. Transição de reservado para conectado é atômica e exige permissão. Não inferir fibra livre somente porque não há cliente associado.
- Exclusão física só para rascunho sem referências. Elementos em uso são desativados/arquivados com validação e histórico. FKs usam RESTRICT onde há conectividade.

Todos os elementos mutáveis têm UUID, timestamps, version e autor quando aplicável. Códigos são únicos dentro do escopo documentado, com normalização. Modelar índices para busca, relações, endpoints ativos e geometrias GiST. Escolha e documente constraints reais; validação apenas em Python não atende este projeto.

## Etapas de implementação

### B01 — Fundação reproduzível

```text
Implemente a fundação descrita neste documento. Inspecione o repo, escolha versões estáveis compatíveis em documentação oficial, fixe Python/dependências/imagens e registre decisões em docs/adr. Não reutilize números de versão não verificados da conversa.
Crie configuração tipada por ambiente, fábrica da aplicação, routers v1, tratamento uniforme de erros, request_id, logs JSON com remoção de segredos, sessões SQLAlchemy, Alembic e fixtures de PostgreSQL/PostGIS real.
Crie /health/live e /health/ready; readiness verifica banco e revisão de migration sem expor credenciais. Inclua compose de desenvolvimento, .env.example e comandos de lint/tipos/testes.
Aceite: instalação reproduzível com lockfile; aplicação sobe; readiness falha quando DB está indisponível; nenhum acesso ao banco ao importar módulos de domínio; smoke test documentado.
```

### B02 — Contrato e schemas antes de telas

```text
Implemente os schemas compartilhados, paginação, filtros permitidos, enums, GeoJSON, Problem Details e precondições de versão. Publique OpenAPI com operation_id estável e exportador determinístico para contracts/openapi.json.
Crie exemplos sintéticos de requests/responses para auth, cabo, segmento, conexão, trace, orçamento e conflito. Defina formatos exatos de operações de /connections/batch e overrides de simulação. Documente cada campo obrigatório/opcional e os códigos de erro.
Endpoints ainda não implementados não devem responder sucesso falso; registre contratos pendentes e não os anuncie como funcionais. Crie teste de schema exportado e detecção de mudança incompatível.
Aceite: geração de cliente TypeScript possível; todas as unidades explícitas; resposta 422 uniforme; nenhuma paginação sem limite.
```

### B03 — Sessões, usuários e permissões

```text
Implemente autenticação com hash Argon2id via biblioteca mantida, sessão opaca cujo token é guardado em hash no banco, expiração absoluta e por inatividade, rotação após login, logout revogando sessão e bloqueio de usuários desativados. Cookies e CSRF conforme contrato. Rate limit de login deve funcionar entre processos usando persistência compartilhada; não introduza Redis apenas para isso.
Crie CLI para primeiro admin e recuperação de acesso, sem senha padrão. Permita admin criar/desativar usuários, alterar função e invalidar sessões. Proteja o último admin ativo contra remoção acidental.
Matriz: viewer consulta rede e relatórios sem dados pessoais desnecessários; technician consulta e registra medições, fotos e observações; engineer adiciona/edita inventário, conectividade, importações e simulações; admin também administra usuários/configuração. Alterações de topologia por technician ficam fora desta versão.
Aceite: testes para 401/403, CSRF, sessão expirada, enumeração de usuário, rate limit, logout e todas as operações privilegiadas. Ocultar botão no frontend não substitui autorização.
```

### B04 — Inventário e migrações

```text
Implemente site, structure, device, port, catálogos de fabricantes/modelos, padrões de cabos/cores e perfis ópticos. Use enums e FKs conforme este documento. Perfis ópticos armazenam fonte, modelo, revisão, onda, faixa de TX, sensibilidade e sobrecarga RX, com validação de limites.
Crie CRUD com busca, ordenação permitida, paginação, versionamento, arquivo/desativação e auditoria. Defina campos obrigatórios por tipo. Não torne metadados arbitrários JSON a única forma de representar campos essenciais.
Aceite: migrations aplicam em DB vazio; constraints recusam proprietário inválido de porta; atualização concorrente retorna 412; exclusão referenciada não destrói rede; teste de matriz de permissões.
```

### B05 — GIS e comprimentos confiáveis

```text
Implemente pontos e linhas SRID 4326, GeoJSON válido, bbox, camadas e consultas espaciais indexadas. Valide longitude/latitude, geometrias vazias, tipos, número de vértices, NaN e limites de tamanho.
Calcule comprimento em metros via geography ou projeção apropriada, nunca graus. Mantenha map_length_m separado de measured_length_m e slack_length_m. Regra óptica: measured_length_m quando informado já representa comprimento total instalado; caso contrário map_length_m + slack_length_m. Retorne length_source. Não some reserva duas vezes.
Estabeleça tolerância configurável para extremidades da rota e locais de acesso; divergência grande exige correção explícita. Mover um poste/caixa não deve redirecionar cabos automaticamente nem alterar conexão óptica por proximidade.
Aceite: segmento conhecido tem distância verificada com tolerância; consulta bbox usa índice; geometria inválida dá 422; mapa limitado sinaliza truncamento; alteração geométrica atualiza revisão quando afeta cálculo.
```

### B06 — Cabos, tubos, fibras e segmentação

```text
Implemente criação transacional de cabo a partir de modelo, tubos/fibras numerados e segmentos com duas extremidades por fibra. Suporte cabo sem tubos físicos com agrupamento lógico explicitamente identificado. Numeração de cores deve aceitar padrões diferentes; não codifique uma sequência como verdade universal.
Crie operação de dividir segmento em local de acesso, preservando identidade do cabo/fibra, geometria e relações externas. Pré-visualize impacto; para fibras não cortadas crie continuidade sem perda de fusão. Para corte/emenda, exija operação explícita. Não duplicar comprimentos/reservas ao dividir. Bloqueie redução de capacidade se remover fibras usadas.
Aceite: cabo 24F de dois grupos de 12 gera 24 fibras e 48 extremidades por segmento; divisão preserva rastreabilidade; falha no meio reverte tudo; não existem fibras órfãs ou identificadas apenas pela cor.
```

### B07 — Motor de conectividade e fusões

```text
Implemente terminais, arestas internas e conexões externas conforme modelo obrigatório. Crie conexão, desconexão, reserva e lote atômico para editor de fusão. Batch usa expected_topology_revision; revisão desatualizada retorna 409 topology_revision_conflict.
Bloqueie recursos em ordem determinística para reduzir deadlocks. Banco deve impedir dupla ocupação mesmo com requisições simultâneas. A alteração da conexão e sua auditoria ocorrem na mesma transação. Preserve histórico de desconexões.
Valide tipos, localização, lado correto, terminais diferentes, pertencimento de entidades e condição desativada. Retorne conflito com código e terminais envolvidos sem expor dados não autorizados.
Aceite: duas tentativas simultâneas de ocupar a mesma ponta deixam exatamente uma conexão ativa; fusão inválida não altera DB; lote parcialmente inválido reverte inteiro; reconexão exige liberação explícita; frente/trás de DIO não é porta com fan-out.
```

### B08 — Splitters, CTOs e atendimento

```text
Implemente splitters 1:N com perdas por saída e onda, identificação de porta, posição na caixa e vínculo explícito com terminais. Razão de divisão pode ser cadastrada, mas a perda efetiva deve aceitar datasheet/medição; não substituir automaticamente por perda ideal.
Implemente ocupação de CTO a partir das portas e conexões/reservas. Crie clientes, ONUs e service_links com ativação/desativação histórica. Uma porta pode estar conectada sem cliente cadastrado; mostre essa situação. Impeça dois atendimentos ativos incompatíveis na mesma porta/ONU.
Aceite: CTO 8 portas com 3 conectadas e 1 reservada informa 4 livres; splitter sem perda cadastrada gera orçamento incompleto; nenhuma ramificação óptica surge só porque dois elementos estão na mesma caixa.
```

### B09 — Rastreamento óptico

```text
Implemente serviço de travessia tipada do grafo com leitura consistente de uma revisão. PostgreSQL é fonte da verdade; carregue subgrafo necessário, não toda a rede a cada request. NetworkX é opcional, nunca justificativa para ignorar semântica de portas/splitters.
Rastreie PON→ONU e ONU→PON. No splitter downstream permite entrada→saídas; upstream saída→entrada. Registre caminhos, arestas, perdas parametrizadas e comprimentos. Detecte ciclos, ponta aberta, múltiplas origens e limites de nós/resultados/tempo. Não esconda inconsistência escolhendo arbitrary first/shortest path.
Aceite: fixtures de rede linear, cascata de splitters, derivação, continuidade sem corte, ciclo inválido, desconexão e origem ambígua retornam os estados corretos. Ordem determinística; caminhos não transitam entre saídas irmãs.
```

### B10 — Cálculo óptico independente e testável

```text
Implemente módulo puro de cálculo que recebe caminho tipado, onda, parâmetros e margem. Não dependa de ORM/FastAPI. Resolva caminho no serviço de aplicação e envie ao módulo.
Fórmulas: perda da fibra = comprimento_m/1000 × atenuação_db_por_km; perda total = soma das perdas reais modeladas no caminho; RX previsto = TX - perda total. Margem restante = RX previsto - sensibilidade RX - margem de engenharia. Folga de sobrecarga = limite máximo RX - RX previsto. Margem de engenharia não é perda física e não deve diminuir a potência nominal prevista.
Calcule downstream com TX OLT/RX ONU e upstream com TX ONU/RX OLT. Onda é parâmetro do perfil; presets GPON 1490/1310 nm são convenções de projeto a validar por equipamentos. Prepare perfis para outras tecnologias sem presumir mesmos limites.
Se existirem intervalos, RX mínimo = TX mínimo - perda máxima; RX máximo = TX máximo - perda mínima. Avalie sensibilidade no pior RX mínimo e sobrecarga no pior RX máximo. Não reutilize uma perda típica como limite garantido sem sinalizar hipótese.
Retorne breakdown por elemento, origem do parâmetro, faixa/típico, avisos, revisão e dados faltantes. Não trate ausência de atenuação como zero nem interpole ondas silenciosamente. Arredonde apenas na apresentação; teste tolerância numérica.
Aceite numérico sintético: TX +3 dBm; 7 km × 0,25 dB/km; 4 fusões × 0,10 dB; 2 pares acoplados × 0,30 dB; 2 splitters × 10,5 dB = perda 23,75 dB e RX -20,75 dBm. Sensibilidade -27 dBm e margem 3 dB resultam em margem restante 3,25 dB. São números de teste, não padrões de fabricante. Teste também sobrecarga, perdas ausentes, saída desigual, onda diferente e contagem única de conector.
```

### B11 — Medições e comparação com previsão

```text
Implemente medições manuais com potência dBm, direção, onda, terminal receptor, equipamento/instrumento, timestamp, autor, origem e observação. Associe snapshot da revisão/parâmetros usados na previsão para comparação histórica.
Retorne perda excedente = RX previsto - RX medido; valor positivo indica medição menor que previsão. Compare somente medições compatíveis em direção/onda/receptor; preserve antiguidade e tolerância configurada. Um desvio sozinho não localiza falha nem comprova causa.
Integração SNMP/telemetria fica atrás de interface futura; nesta etapa o registro manual é funcional. Não conectar a OLT real sem dados e autorização.
Aceite: previsto -19,3 dBm e medido -25,4 dBm produzem 6,1 dB de perda excedente; medição incompatível não vira alerta conclusivo; edição não apaga valor histórico sem trilha.
```

### B12 — Impacto de rompimento e simulações

```text
Implemente análise de falha removendo virtualmente arestas dos segmentos selecionados em snapshot consistente. Compare alcançabilidade antes/depois para atendimentos documentados, CTOs e PONs; deduplique clientes. Não altere dados operacionais.
Retorne impacted, unaffected e unknown quando documentação incompleta impedir conclusão; diferencie elementos já desconectados antes do cenário. Redundância/proteção só conta se explicitamente modelada. A primeira versão não promete simular protocolos de failover.
Implemente simulação de perda/comprimento/splitter por overrides tipados, resultado antes/depois e premissas. Troca de splitter com quantidade diferente de portas exige mapeamento; não reconecta silenciosamente.
Aceite: rompimento de ramo não afeta ramo irmão; cliente já desconectado não vira nova queda; cenário não muda topology_revision operacional; restauração do estado não depende de desfazer writes.
```

### B13 — Fotos, anexos e auditoria

```text
Implemente anexos privados em volume persistente com IDs aleatórios, metadados no DB, limites de bytes/tipos e validação de conteúdo. Suporte JPEG/PNG/WebP/PDF inicialmente, rejeite HTML/SVG ativo. Original somente por download autorizado; thumbnails seguros; não confiar em nome/extensão/MIME recebido. Bloqueie path traversal.
Use vínculo a entidade existente e autorizada. Implemente limpeza de arquivos temporários e reconciliação de órfãos sem excluir anexos válidos. Downloads precisam de autorização a cada acesso, não de URL pública previsível.
Auditoria append-only para papel da aplicação: ator, ação, entidade, antes/depois sanitizados, motivo, timestamp e request_id. Inclua alterações de conectividade, perfis ópticos, permissões e importações. Não registrar senhas/tokens nem prometer resistência contra administrador do banco.
Aceite: upload inválido é recusado; usuário sem acesso não baixa arquivo por UUID conhecido; escrita revertida não deixa auditoria de sucesso; anexos sobrevivem restart.
```

### B14 — Importação com prévia e exportação

```text
Implemente importação GeoJSON, KML e CSV por preview/validação/commit. Detecte encoding e CRS suportados, valide cabeçalhos, limite volume, desative entidades externas XML, bloqueie arquivos compactados abusivos se KMZ for habilitado. Não executar fórmulas de planilha.
Preview guarda conteúdo/hash, mapeamento, erros por linha/feature, colisões e ações propostas. Commit exige preview válido, mesma versão/hash e Idempotency-Key; execute transação ou chunks explicitamente documentados com relatório. Não deduza fusão por cruzamento de linhas ou proximidade de pontos.
Exporte inventário CSV e geometrias GeoJSON/KML com filtros e autorização; neutralize fórmulas em CSV. Jobs em PostgreSQL com estados queued/running/succeeded/failed/cancelled, lease, heartbeat, retry limitado e recuperação após crash. Worker pode usar a mesma imagem do backend e serviço Compose separado. Não usar BackgroundTasks para tarefa que precisa sobreviver a reinício.
Aceite: importar duas vezes a mesma chave não duplica; preview não altera rede; erro tem linha identificável; worker reiniciado recupera job; cancelamento informa o que foi aplicado; exportação respeita permissões de dados pessoais.
```

### B15 — Busca, painel e relatórios

```text
Implemente busca global por código/nome/serial com limite e escopo autorizado. Dashboard com totais por tipo, CTOs por faixa de ocupação, capacidade documentada, dados incompletos e alterações recentes; não inventar disponibilidade em tempo real.
Crie relatórios paginados/exportáveis de fibras conectadas/livres/reservadas, portas CTO, ocupação por PON documentada, orçamentos insuficientes e inconsistências de conectividade. Disponibilidade ponta a ponta exige caminho contínuo compatível; número de fibras livres em um cabo isolado não comprova viabilidade de atendimento.
Aceite: totais batem com fixture; todos os contadores têm critério documentado; contagem não multiplica cliente por joins; filtros e autorização são os mesmos nas telas e exports.
```

### B16 — Desempenho e observabilidade

```text
Crie dataset sintético reproduzível com pelo menos 10 mil estruturas e 100 mil fiber_segments para medir os endpoints críticos. Documente hardware, configuração, volume e resultados; alvos iniciais, não garantias: p95 de consulta de mapa limitada abaixo de 1 s e trace de um atendimento abaixo de 2 s no ambiente registrado.
Procure N+1, planos sem índice e resposta excessiva. Adote MVT/tiles da rede ou cache por topology_revision apenas se medições justificarem; invalidação deve ser correta. Incremente revisão atomicamente e obtenha dados de uma revisão consistente.
Implemente métricas de latência/erros/jobs e logs com request_id; acesso às métricas é restrito. Limite nós de trace, features, uploads, requests e consultas caras. Não colocar cliente/serial como label de alta cardinalidade.
Aceite: benchmark repetível; limites retornam estados explícitos; nenhum resultado antigo é apresentado como revisão atual; endpoint sob carga não impede login/readiness.
```

### B17 — Implantação, backup e manutenção

```text
Finalize Docker Compose com web, api, PostgreSQL/PostGIS, Caddy e worker somente se B14 o exigir. Imagens fixadas, processo não root onde possível, volumes persistentes, rede privada de banco e healthchecks. Não publique porta do DB por padrão.
Crie comando único de migração anterior ao start dos workers; não executar Alembic simultaneamente em cada réplica. Bootstrap do admin exige segredo fornecido pelo operador. Configure cookies/HTTPS/origens/proxy confiável conforme ambiente.
Documente instalação limpa, atualização, backup consistente de DB+anexos, restauração em ambiente isolado, retenção, rotação de segredos e recuperação. Faça restore drill real da fixture com anexo; backup sem teste de restauração não atende aceite. Não prometa downgrade automático de migração destrutiva: documente backup e roll-forward.
Aceite: Compose sobe após configuração; restart preserva dados; backup restaurado abre caminho e foto; sem credenciais padrão; documentação explica servidor de tiles configurável e requisitos de rede.
```

### B18 — Auditoria final e entrega open source

```text
Revise o backend contra este documento e o contrato do frontend. Rode lint, tipos, unitários, integração PostgreSQL/PostGIS, concorrência e contratos. Crie CI que reproduz os gates e verifica export OpenAPI/cliente sem drift.
Teste fluxo completo: admin → POP/OLT/DIO → cabo → CEO/fusão/splitter → CTO → drop/ONU/cliente → trace → orçamento → medição → impacto → export → backup/restore.
Revise autorização por endpoint/objeto, uploads, CSRF, SQL injection, dados pessoais, constraints e exclusões. Corrija falhas prioritárias antes de declarar pronto. Não substitua isso por um percentual genérico de cobertura.
Entregue README, CONTRIBUTING, SECURITY, decisões de arquitetura, modelo ER, catálogo de API e matriz requisito→teste. Recomende que o mantenedor escolha a licença antes de publicar; não invente titularidade nem afirme open source sem arquivo de licença escolhido. Gere dados demo sintéticos via comando opt-in, jamais no boot de produção.
Aceite: checklist objetivo com PASS/FAIL/BLOCKED e evidências. Nenhuma pendência crítica escondida como melhoria futura. Se não executou um teste, marque BLOCKED com motivo.
```

## Marcos e coordenação com o frontend

| Marco | Backend | Frontend liberado |
| --- | --- | --- |
| Contrato | B01–B03 | F01–F04 com mocks derivados dos exemplos |
| Rede física | B04–B06 | F05–F08 integrados |
| Rede óptica | B07–B09 | F09–F11 integrados |
| Engenharia | B10–B12 | F12–F14 integrados |
| Operação | B13–B15 | F15–F17 integrados |
| Entrega | B16–B18 | F18–F20 e aceite ponta a ponta |

## Prompt de retomada

```text
Leia backend.md, frontend.md, docs/progress-backend.md, os ADRs e o estado real do repositório. Identifique a última etapa concluída com evidências. Não reescreva módulos saudáveis nem reinicie o projeto. Resuma o estado em até 10 linhas, execute a próxima etapa pendente e atualize o progresso. Se houver divergência entre documento e código, registre e resolva mantendo integridade dos dados e compatibilidade do contrato.
```

## Prompt de revisão de uma entrega

```text
Revise a etapa B__ contra seus critérios de aceite e as invariantes de backend.md. Procure bugs de domínio, concorrência, integridade, segurança e divergência de API. Demonstre problemas com cenário reproduzível, arquivo e teste quando útil. Priorize por impacto. Corrija e rode os testes relevantes. Não declare tudo certo apenas porque compila ou porque o caminho feliz funciona.
```

## Referências técnicas

Referências de implementação, não versões fixadas. O domínio e as regras de produto acima são decisões propostas para este projeto.

- [FastAPI — recursos e OpenAPI](https://fastapi.tiangolo.com/features/): contrato gerável e validação de entrada/saída.
- [PostGIS — ST_Length](https://postgis.net/docs/ST_Length.html): comprimento de geography em metros; geometry usa unidades do sistema de referência.
- [Next.js — componentes de servidor e cliente](https://nextjs.org/docs/app/getting-started/server-and-client-components): fronteira de integração com frontend.
- [MapLibre GL JS — documentação](https://maplibre.org/maplibre-gl-js/docs/): renderização do mapa consumidor da API geográfica.

Parâmetros ópticos de produção precisam de datasheets dos modelos usados. Valores numéricos de testes deste documento são deliberadamente sintéticos e não certificam uma rede.
