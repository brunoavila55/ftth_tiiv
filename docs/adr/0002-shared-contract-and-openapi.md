# ADR 0002: Contrato Compartilhado OpenAPI, Nomenclatura e Concorrência Otimista

- **Status**: Aceito
- **Data**: 2026-09-17
- **Autores**: Equipe de Engenharia FTTH Manager

## Contexto

Conforme estabelecido na especificação inicial (`backend.md`/`frontend.md`, removidas após a auditoria; histórico no git), o backend é o proprietário absoluto do contrato e das regras de integridade e validação do sistema. O frontend gerará tipos TypeScript estritos diretamente a partir do arquivo [`contracts/openapi.json`](file:///home/bruno/projects/ftth_tiiv/contracts/openapi.json).

Para evitar divergências, foram necessárias definições formais quanto a:
1. Padronização de endpoints e esquemas de dados.
2. Identificadores únicos determinísticos para geração de clientes (`operationId`).
3. Convenção de unidades físicas explícitas nas propriedades dos schemas.
4. Mecanismo de controle de concorrência com precondições HTTP.
5. Tratamento uniforme de erros e não emissão de falsos sucessos para endpoints em desenvolvimento.

## Decisões

### 1. Contrato OpenAPI Central e Determinístico
- O arquivo [`contracts/openapi.json`](file:///home/bruno/projects/ftth_tiiv/contracts/openapi.json) é gerado de forma determinística com chaves ordenadas via script [`backend/scripts/export_openapi.py`](file:///home/bruno/projects/ftth_tiiv/backend/scripts/export_openapi.py).
- Um teste automatizado de regressão (`test_openapi_json_matches_app_schema`) bloqueia qualquer alteração em código que introduza desvio não exportado no contrato.
- A compatibilidade foi validada gerando com sucesso 6.900+ linhas de tipagens TypeScript estritas via `openapi-typescript` em [`contracts/api-types.d.ts`](file:///home/bruno/projects/ftth_tiiv/contracts/api-types.d.ts).

### 2. Formato e Geração de `operationId`
- Foi implementada a função `custom_generate_unique_id(route)` que constrói identificadores estáveis no formato `{clean_path}_{route_name}`.
- Isso elimina nomes arbitrários e garante que nenhuma rota compartilhe `operationId` duplicado.

### 3. Convenção de Unidades Explícitas
- Nenhuma propriedade de distância, atenuação ou potência omite sua unidade:
  - Comprimentos: `*_m` (ex: `map_length_m`, `measured_length_m`, `slack_length_m`, `effective_length_m`).
  - Perdas e atenuação: `*_db` (ex: `loss_db`, `total_loss_db`, `engineering_margin_db`, `excess_loss_db`) e `default_attenuation_db_per_km`.
  - Potência óptica: `*_dbm` (ex: `tx_dbm`, `predicted_rx_dbm`, `power_dbm`).
  - Comprimento de onda: `wavelength_nm`.
- Campos descritores não numéricos utilizam enums explícitos (ex: `length_source = "measured" | "calculated"`).

### 4. Controle de Concorrência Otimista
- Recursos mutáveis incluem a propriedade inteira monotônica `version`.
- Requisições `PATCH` e `DELETE` exigem o cabeçalho `If-Match: "<version>"`.
- Códigos de resposta:
  - `428 Precondition Required`: cabeçalho ausente.
  - `412 Precondition Failed`: versão diverge do estado atual no banco.
  - `409 Conflict`: conflito lógico de negócio ou de revisão topológica (`topology_revision_conflict`).

### 5. Contratos pendentes durante o desenvolvimento
- Durante a construção por etapas, rotas futuras retornavam `501 Not Implemented` em vez de sucesso falso. Em 20/09/2026, os últimos contratos B03/B08 foram implementados e o helper de stubs foi removido. O teste de contrato agora falha se qualquer rota publicada voltar a delegar para `pending_endpoint`.

## Consequências

- **Positivas**:
  - Geração de código TypeScript no frontend sem atrito ou tipos manuais inconsistentes.
  - Prevenção garantida contra sobrescrita acidental de dados em campo através do `If-Match`.
  - Autodocumentação imediata no Swagger UI (`/docs`).
- **Limitações / Mitigações**:
  - Qualquer alteração futura em rotas ou modelos exige reexecução do script de exportação do contrato.
