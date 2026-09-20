# ADR 0006: Cabos, Tubos Loose, Fibras, Terminais e Divisão de Segmentos

## Status
Aceito

## Contexto
No projeto FTTH Manager, a modelagem de cabos de fibra óptica requer granularidade no nível de tubo loose e fibra individual. Conforme os requisitos do prompt B06 da especificação inicial (`backend.md`, removida após a auditoria; histórico no git):
1. Criação transacional de cabos a partir de modelos de catálogo ou especificações diretas, gerando tubos e fibras numerados com rastreabilidade completa.
2. Suporte a cabos multitubo e cabos sem tubos físicos (monotubo / loose único ou tight buffered), utilizando agrupamento lógico explicitamente identificado (`is_logical_group = True`).
3. Suporte a múltiplos padrões e sequências de cores de tubos e fibras (NBR 14106 / ABNT, TIA-598-C, DIN VDE 0888), sem codificar uma única sequência como verdade universal. Fibras e tubos são identificados por número global, posição e nome da cor. Nenhuma fibra pode ser anônima ou identificada exclusivamente por cor.
4. Cada segmento de cabo (`CableSegment`) deve instanciar duas extremidades normalizadas (`Terminal`) por fibra (uma na estrutura/caixa de origem e outra na de destino), resultando em exatamente $2N$ terminais por segmento para um cabo de $N$ fibras (ex.: 24 fibras geram 48 terminais normalizados).
5. Operação atômica de divisão de segmento (`split_cable_segment`) ao interceptar um segmento existente em um local de acesso intermediário (como uma CEO ou CTO):
   - Divisão da geometria LineString em duas partes respeitando a projeção ou coordenada da estrutura de corte.
   - Recálculo dos comprimentos geodésicos em metros sem duplicar reservas técnicas (`slack_length_m`).
   - Preservação da identidade das fibras e do cabo original.
   - Para fibras não cortadas (passantes / sangria de tubo), criação automática de conexão interna de continuidade (`internal_continuity`) com perda nominal de 0.0 dB.
   - Para fibras cortadas, geração de novos terminais livres na estrutura intermediária prontos para fusão ou terminação.
   - Preservação de conexões externas pré-existentes nas extremidades originais do segmento.
   - Bloqueio de redução de capacidade ou divisão inválida.
   - Pré-visualização do impacto da divisão (`preview_split_segment`) antes da execução.
   - Qualquer falha parcial na divisão deve reverter atomicamente toda a transação no banco de dados.

## Decisões Arquiteturais

### 1. Entidades Normalizadas de Fibra e Terminais
- **`Tube` (`tubes`)**: Possui `cable_id`, `number` (1-indexed), `color_name` e a flag booleana `is_logical_group` que diferencia tubos físicos reais de agrupamentos organizacionais lógicos.
- **`Fiber` (`fibers`)**: Possui `cable_id`, `tube_id`, `global_number` (1 a $N$), `tube_position` (1 a $K$) e `color_name`. Chave única `(cable_id, global_number)`.
- **`Terminal` (`terminals`)**: Ponto de terminação normalizado de conectividade. Representa uma ponta física de fibra ou porta de equipamento em um local específico (`site_id` ou `structure_id`). Cada extremidade de fibra em um trecho é mapeada para um terminal com `kind = 'fiber_endpoint'`.
- **`FiberSegment` (`fiber_segments`)**: Relaciona uma fibra lógica (`Fiber`) a um trecho físico (`CableSegment`), associando seus terminais de extremidade `terminal_a_id` e `terminal_b_id`, além de gerenciar a ocupação (`free`, `lit`, `reserved`, `damaged`).

### 2. Geração Transacional de Cabos ($2N$ Terminais por Segmento)
- A criação de cabo (`create_cable`) instancia a entidade `Cable`, os `Tubes` e as `Fibers` em uma única transação usando a paleta do padrão de cores selecionado (`NBR`, `TIA-598`, etc.).
- A criação do primeiro trecho (`create_cable_segment`) ou trechos subsequentes cria automaticamente os terminais em ambas as estruturas de ancoragem e os `FiberSegment` correspondentes. Para um cabo de 24 fibras, são criados 48 registros de `Terminal` do tipo `fiber_endpoint` vinculados aos respectivos `structure_id` ou `site_id`.

### 3. Divisão Atômica de Segmentos e Continuidade de Sangria
- A operação de split (`split_cable_segment`) recebe:
  - O ID do segmento original a ser dividido.
  - O ID da estrutura de acesso intermediária (`split_structure_id`).
  - A lista opcional de fibras a cortar (`cut_fiber_ids`).
- **Geometria e Comprimentos**:
  - A linha original é fatiada no vértice mais próximo da estrutura intermediária em `LineString 1` e `LineString 2`.
  - Os comprimentos geodésicos `map_length_m` são recalculados via PostGIS Geography para ambos os trechos.
  - A reserva técnica original `slack_length_m` permanece no trecho 1 (ou dividida conforme informado), prevenindo duplicação de reserva.
- **Terminais e Continuidade**:
  - Para cada fibra, novos terminais intermediários $T_{1b}$ e $T_{2a}$ são gerados na estrutura de acesso.
  - O trecho 1 conecta $T_{original\_a}$ a $T_{1b}$ (preservando conexões externas existentes em $T_{original\_a}$).
  - O trecho 2 conecta $T_{2a}$ a $T_{original\_b}$ (preservando conexões externas existentes em $T_{original\_b}$).
  - **Fibras Passantes**: Fibras não listadas em `cut_fiber_ids` recebem uma conexão em `connections` com `type = 'internal_continuity'`, `loss_db = 0.0` e `is_active = True` entre $T_{1b}$ e $T_{2a}$, modelando a sangria de tubo contínua sem atenuação espúria.
  - **Fibras Cortadas**: Terminais $T_{1b}$ e $T_{2a}$ permanecem livres para posterior fusão em bandeja ou conectorização.
- O segmento original é desativado (`status = 'retired'`) e a revisão topológica global é incrementada (`bump_topology_revision`).

### 4. Transacionalidade e Pré-visualização
- O endpoint `POST /cable-segments/{id}/split/preview` calcula e retorna exatamente o impacto da divisão (novos comprimentos, quantidade de conexões de continuidade a gerar e terminais a criar) sem persistir alterações.
- O endpoint `POST /cable-segments/{id}/split` executa toda a alteração sob uma transação ACID estrita com rollback garantido em caso de erro e validações de concorrência otimista.

## Consequências

### Positivas
- Rastreabilidade ponta a ponta sem perda de identidade de fibras ou cabos ao expandir ou ramificar a rede.
- Suporte total a sangria de tubo loose (passagem contínua sem fusão artificial).
- Conexões externas pré-existentes não são corrompidas ou desconectadas ao seccionar um cabo no meio do trajeto.
- Conformidade estrita com normas brasileiras (NBR) e internacionais (TIA, DIN).

### Negativas / Trade-offs
- A geração de dois terminais por fibra em cada segmento aumenta o número de registros na tabela `terminals`, demandando índices adequados por `structure_id`, `site_id` e chaves estrangeiras.
