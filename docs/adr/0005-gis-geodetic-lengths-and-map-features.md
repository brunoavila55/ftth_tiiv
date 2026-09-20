# ADR 0005: GIS, Comprimentos Geodésicos e Feições Espaciais de Mapa

## Status
Aceito

## Contexto
O FTTH Manager baseia-se em infraestrutura física georreferenciada. Redes ópticas dependem de distâncias e comprimentos precisos em metros (`*_m`), pois o orçamento de potência e atenuação do sinal óptico é diretamente proporcional à distância física da fibra instalada.

Conforme os requisitos do prompt B05 da especificação inicial (`backend.md`, removida após a auditoria; histórico no git):
1. Todos os pontos e linhas devem ser expressos no sistema geodésico WGS84 / EPSG:4326 com GeoJSON estritamente válido.
2. Todas as coordenadas devem ser validadas contra limites geográficos, rejeitando valores nulos, vazios, degenerados, NaN e Infinito com HTTP 422 Problem Details.
3. Comprimentos e distâncias devem ser calculados obrigatoriamente em metros sobre o elipsoide de referência geodésico (via `geography` do PostGIS e fórmulas geodésicas), jamais em graus planares.
4. Deve haver distinção clara entre comprimento geográfico (`map_length_m`), comprimento físico medido no campo (`measured_length_m`) e reserva técnica (`slack_length_m`), com resolução óptica inequívoca e indicação de origem (`length_source`). A reserva técnica não pode ser somada duas vezes quando houver medição de campo.
5. Deve haver tolerância configurável (`ROUTE_ENDPOINT_TOLERANCE_M`) entre as extremidades das rotas de cabos e as estruturas físicas de acesso. Divergências exigem correção explícita.
6. A movimentação física de um poste ou caixa não pode alterar ou redirecionar cabos automaticamente por proximidade.
7. O endpoint `/map/features` deve consultar feições por Bounding Box com suporte a índices espaciais GiST, retornando a revisão monotônica da topologia (`topology_revision`) e sinalizando explicitamente truncamento (`truncated=true`) caso exceda o limite seguro de feições.
8. Mutações geométricas que afetam cálculos ópticos devem incrementar a revisão topológica global.

## Decisões Arquiteturais

### 1. Representação Espacial e Validação Estrita
- Geometrias são armazenadas em colunas PostGIS `Geometry(POINT, 4326)` e `Geometry(LINESTRING, 4326)` com índices espaciais GiST automáticos.
- Validação rigorosa em `app/modules/gis/helpers.py`:
  - `validate_coordinates(lon, lat)`: rejeita valores fora do domínio `[-180.0, 180.0]` e `[-90.0, 90.0]`, bem como `NaN` e `Inf`.
  - `validate_linestring(coordinates)`: exige no mínimo 2 vértices distintos, limita o número máximo a 10.000 pontos (mitigação DoS) e rejeita linhas colapsadas em um único ponto.
  - `parse_and_validate_bbox(bbox_str)`: valida os 4 cantos do envelope `minLon,minLat,maxLon,maxLat` garantindo que `min <= max`.

### 2. Comprimento Geodésico em Metros via PostGIS Geography
- O cálculo de comprimento geodésico é executado utilizando `ST_Length(geometry::geography)` no PostGIS, que projeta as linhas sobre o esferoide WGS84 retornando metros reais com precisão subcentimétrica.
- Em Python puro, implementou-se a fórmula de Haversine (`EARTH_RADIUS_METERS = 6371008.8m`) para validações rápidas em memória de tolerância de extremidades.

### 3. Regra Óptica de Comprimento Confiável e Prevenção de Dupla Reserva
- Implementada a regra:
  ```python
  if measured_length_m is not None:
      effective_length_m = measured_length_m
      length_source = "measured"
  else:
      effective_length_m = map_length_m + slack_length_m
      length_source = "calculated"
  ```
- **Prevenção de Dupla Reserva**: Quando o técnico no campo afere e registra o comprimento real da fibra (ex: via OTDR ou leitura do odômetro do cabo), esse valor já incorpora todas as reservas técnicas e sobras de caixa. Portanto, `slack_length_m` **não** é adicionado novamente ao valor medido.

### 4. Tolerância de Rota e Imutabilidade por Proximidade
- A função `validate_route_endpoints_tolerance` calcula a distância geodésica entre a primeira coordenada do cabo e a estrutura de origem, e entre a última coordenada e a estrutura de destino.
- Se a distância for superior à tolerância (`ROUTE_ENDPOINT_TOLERANCE_M = 5.0m`), uma exceção `UnprocessableEntityError` (HTTP 422) é levantada com mensagem detalhada exigindo correção manual.
- Mover um poste/caixa (`UPDATE structures SET location = ...`) apenas altera as coordenadas da estrutura; os cabos conectados mantêm suas geometrias exatas e não são redirecionados automaticamente por atração ou proximidade.

### 5. Estado Global da Topologia (`NetworkTopologyState`)
- Criada a tabela `network_topology_state` com um contador monotônico `topology_revision`.
- As funções `get_topology_revision` e `bump_topology_revision` fornecem controle de cache, leitura consistente de subgrafos e detecção de conflitos de revisão para operações em lote e traçados ópticos.
- Mutações que alteram trechos de cabo ou seus comprimentos acionam automaticamente `bump_topology_revision`.

### 6. Endpoint de Mapa `/map/features` e Truncamento Explícito
- O endpoint `/api/v1/map/features` consulta `Site`, `Structure` e `CableSegment` no envelope `ST_MakeEnvelope(minLon, minLat, maxLon, maxLat, 4326)` através do operador espacial de interseção `ST_Intersects`, aproveitando os índices espaciais GiST.
- Caso a contagem de feições encontradas exceda `MAP_MAX_FEATURES` (padrão 500), a API trunca a lista até o limite e seta explicitamente `truncated: true` no payload `MapFeatureCollection`, impedindo truncamento silencioso no cliente.
- Requer permissão RBAC `network:read`.

## Consequências

### Positivas
- Cálculos ópticos 100% embasados em distâncias geodésicas reais em metros sobre o WGS84, sem distorções de projeção planar em graus.
- Proteção estrita contra dados corrompidos (NaN, coordenadas invertidas, envelopes inválidos).
- Prevenção garantida de contagem dupla de reservas técnicas no cálculo de atenuação óptica.
- Truncamento de mapas seguro e transparente para clientes web e mobile.
- Revisão topológica global preparada para o motor de rastreamento e cálculo de potência.

### Negativas / Trade-offs
- A exigência de tolerância de 5 metros requer que ferramentas de desenho no frontend façam snapping ou que o operador posicione a extremidade do trecho sobre a estrutura de ancoragem.
