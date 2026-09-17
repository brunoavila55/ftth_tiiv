# ADR 0004: Modelo de Dados de Inventário Físico, Restrições e Perfis Ópticos

## Status
Aceito

## Contexto
O FTTH Manager modela a infraestrutura física de telecomunicações de provedores de internet. Elementos como POPs centrais, armários técnicos, postes de concessionária, caixas de emenda (CEOs), caixas de atendimento (CTOs), equipamentos ativos (OLTs, ONUs, switches) e passivos (DIOs) constituem os nós da rede.

Conforme as diretrizes do `backend.md`:
1. Campos essenciais devem ser colunas tipadas e normalizadas, não metadados JSON arbitrários.
2. Cada dispositivo deve pertencer exclusivamente a um local técnico (`site`) ou a uma estrutura externa (`structure`).
3. Toda porta óptica deve pertencer exclusivamente a um dispositivo ou a uma estrutura passiva (como portas conectorizadas de CTO).
4. A integridade referencial deve prevenir a exclusão acidental de nós que possuam outros elementos vinculados (`ON DELETE RESTRICT`), retornando HTTP 409 Conflict em vez de destruir dados da rede em cascata.
5. Perfis ópticos devem conter limites validados de comprimento de onda, potências TX/RX e atenuação nominal da fibra.
6. A concorrência otimista deve exigir o cabeçalho `If-Match: "<version>"`.

## Decisões Arquiteturais

### 1. Entidades Tipadas com PostGIS
- `sites`: Representa POPs e armários com chave primária UUID, código alfanumérico único (`code`), tipo normalizado (`SiteKind`), ponto geográfico `Geometry(POINT, 4326)` indexado com GiST e controle de versão monotônica.
- `structures`: Representa postes, CEOs, CTOs, caixas subterrâneas e pedestais. Possui relação opcional com `sites` (caso a estrutura esteja localizada dentro do perímetro do site).
- `devices`: Representa OLTs, DIOs, ONUs e switches.
- `ports`: Representa portas ópticas com função explícita (`PortRole`: pon, uplink, client_access, pass_through, internal) e tipo de conector (`SC/APC`).
- `optical_profiles`: Perfis de tecnologia PON (GPON, XGS-PON, etc.) com potência TX mínima/máxima, sensibilidade RX e sobrecarga.

### 2. Check Constraints de Exclusividade no Banco de Dados
A validação em nível de aplicação não substitui restrições de integridade no banco. Foram implementadas constraints SQL estritas:
- **Dispositivo (`chk_device_single_location`)**:
  ```sql
  CHECK ((site_id IS NOT NULL AND structure_id IS NULL) OR (site_id IS NULL AND structure_id IS NOT NULL))
  ```
- **Porta (`chk_port_single_owner`)**:
  ```sql
  CHECK ((device_id IS NOT NULL AND structure_id IS NULL) OR (device_id IS NULL AND structure_id IS NOT NULL))
  ```
- **Perfis Ópticos**:
  - `chk_optical_profile_tx`: `tx_min_dbm <= tx_max_dbm`
  - `chk_optical_profile_rx`: `rx_sensitivity_dbm <= rx_overload_dbm`
  - `chk_optical_profile_wavelength`: `wavelength_nm >= 800 AND wavelength_nm <= 2000`
  - `chk_optical_profile_attenuation`: `default_attenuation_db_per_km >= 0.0`

### 3. Unicidade de Nomes de Portas por Escopo
- Uma CTO e uma OLT podem ambas ter uma porta com o identificador `"Porta 01"`.
- Para garantir que não haja portas homônimas dentro do mesmo equipamento/estrutura, foram criados índices parciais únicos no PostgreSQL:
  - `uq_ports_device_name` em `(device_id, name)` onde `device_id IS NOT NULL`
  - `uq_ports_structure_name` em `(structure_id, name)` onde `structure_id IS NOT NULL`

### 4. Proteção contra Destruição da Rede (RESTRICT)
- Todas as chaves estrangeiras de inventário utilizam `ON DELETE RESTRICT`.
- Tentativas de exclusão de um site com estruturas associadas, ou de uma estrutura com portas/dispositivos associados, são interceptadas e convertidas em erro HTTP `409 Conflict` com código `referenced_entity_conflict`, impedindo a deleção em cascata e preservando a integridade física da documentação.

### 5. Catálogo Formal de Cores de Fibras
- Criado o módulo `app/modules/inventory/catalogs.py` com as especificações ABNT NBR 14106/14771 (padrão nacional), TIA-598-C (padrão norte-americano/internacional) e DIN VDE 0888 (padrão europeu).
- O padrão de cores é configurável no modelo de cabo e não fica hardcoded como verdade universal.

## Consequências

### Positivas
- Total conformidade com as regras de integridade física exigidas pelo setor de telecomunicações.
- Impossibilidade física e lógica de orfanar portas ou criar dispositivos sem localização definida.
- Consultas geoespaciais com alta performance por meio de índices GiST sobre as geometrias PostGIS.
- Respostas consistentes RFC 7807 para conflitos (409) e precondições (428/412).

### Negativas / Trade-offs
- A exclusão de entidades complexas requer que o operador explicitamente desvincule ou remova os elementos dependentes primeiro, aumentando o número de requisições mas prevenindo desastres operacionais.
