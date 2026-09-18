# Runbook de Implantação, Backup, Manutenção e Recuperação (B17)

Este documento estabelece as diretrizes e procedimentos operacionais padronizados para o **FTTH Manager** em conformidade com o marco **B17**.

---

## 1. Arquitetura de Implantação e Topologia Docker Compose

A pilha de produção do FTTH Manager é orquestrada via Docker Compose com separação estrita de redes, privilégios mínimos (não-root) e volumes persistentes:

| Serviço | Imagem / Base | Rede | Porta Host Exposta | Função |
|---|---|---|---|---|
| `db` | `docker.io/postgis/postgis:16-3.4` | `internal` | Nenhuma (privada) | Banco relacional e espacial PostGIS |
| `migrate` | `backend:runner` (Python 3.12 non-root) | `internal` | Nenhuma | Execução atômica e única das migrações Alembic (`alembic upgrade head`) antes de subir o backend/workers |
| `backend` | `backend:runner` (Python 3.12 non-root) | `internal`, `public` | Nenhuma (via Caddy) | API FastAPI, endpoints REST, telemetria e documentação |
| `worker` | `backend:runner` (Python 3.12 non-root) | `internal` | Nenhuma | Consumo concorrente de jobs de importação/exportação via `SKIP LOCKED` |
| `frontend` | `frontend:runner` (Node 22 Alpine non-root) | `public` | Nenhuma (via Caddy) | Interface Web Next.js App Router standalone |
| `caddy` | `docker.io/caddy:2.8.4-alpine` | `public` | `80:80`, `443:443` | Reverse proxy com compressão, terminação TLS e CSP estrito |

### Invariantes de Infraestrutura:
1. **Rede Privada do Banco**: A porta `5432` do PostgreSQL **não** é publicada no host por padrão. Somente containers na rede `internal` têm acesso direto. Para desenvolvimento local, utilize `compose.override.yaml` (baseado em `compose.override.yaml.example`).
2. **Migração Sequencial Única**: O serviço `migrate` roda como tarefa pontual (`restart: "no"`) com bloqueio transacional do Alembic, impedindo corrida concorrente de migrações em réplicas de workers ou da API.
3. **Usuários Não-Root**: Os containers da API, Worker (`ftthuser`, UID 1000) e Web (`nextjs`, UID 1001) rodam com privilégios reduzidos.
4. **Volumes Persistentes**:
   - `pgdata`: Dados do PostgreSQL.
   - `backend_storage`: Fotos e documentos enviados do campo.
   - `caddy_data` / `caddy_config`: Certificados TLS e estado do proxy.

---

## 2. Instalação Limpa (Fresh Install)

### 2.1 Pré-requisitos
- Docker Engine 24+ e Docker Compose v2+
- Mínimo de 2 vCPU e 4 GB de RAM
- Portas de entrada 80/TCP e 443/TCP liberadas no firewall

### 2.2 Configuração Inicial de Variáveis
Copie o modelo de variáveis de ambiente:
```bash
cp .env.example .env
```

Edite o arquivo `.env` gerando credenciais criptográficas fortes:
```bash
# Gerar chave de sessão (mínimo 32 caracteres)
openssl rand -hex 32

# Gerar segredo CSRF
openssl rand -hex 32

# Gerar token para endpoint de métricas Prometheus
openssl rand -hex 16
```
> [!IMPORTANT]
> **Sem credenciais padrão**: O FTTH Manager recusa subir em modo de produção se `SECRET_KEY` contiver valores de exemplo ou strings fracas.

### 2.3 Inicialização da Pilha
```bash
docker compose up -d --build
```
Acompanhe os healthchecks até que todos os serviços estejam saudáveis:
```bash
docker compose ps
```

### 2.4 Bootstrap do Primeiro Administrador
O bootstrap do administrador exige credenciais fornecidas explicitamente pelo operador, sem senhas predefinidas ou inseguras:
```bash
docker compose exec backend python -m app.cli.bootstrap_admin \
  --email "admin@provedor.com.br" \
  --name "Administrador Geral"
# O terminal solicitará a senha de forma interativa e oculta (mínimo 8 caracteres)
```

---

## 3. Procedimento Operacional de Backup Consistente

O FTTH Manager implementa backup atômico e determinístico contemplando tanto o banco relacional/espacial quanto os arquivos de mídia armazenados.

### 3.1 Execução Manual
```bash
# Via script bash
./scripts/backup.sh

# Ou diretamente no contêiner backend
docker compose exec backend python scripts/backup.py --target-dir /app/storage/backups --retention-count 7
```

### 3.2 Anatomia do Arquivo de Backup (`.tar.gz`)
Cada arquivo gerado (ex: `ftth_backup_20260918_142030.tar.gz`) contém:
- `manifest.json`: Manifesto assinado contendo ID do backup, timestamp UTC, versão de schema Alembic, revisão da topologia óptica (`topology_revision`), quantidade de anexos e dicionário de hashes SHA256 para verificação de integridade de cada arquivo.
- `database.dump`: Dump binário nativo de alta performance das tabelas relacionais e espaciais.
- `attachments/`: Diretório contendo todas as fotos e documentos técnicos armazenados.

### 3.3 Política de Retenção
Por padrão, o parâmetro `--retention-count 7` mantém os 7 backups mais recentes, expurgando de forma segura arquivos legados para evitar exaustão de disco.

---

## 4. Teste de Restauração em Ambiente Isolado (Restore Drill)

> [!NOTE]
> Conforme exigência de aceite de **B17**, um backup sem teste de restauração comprovado não é considerado válido. O script automatizado `scripts/restore_drill.py` executa todo o ciclo de validação fim-a-fim.

### 4.1 O que o Restore Drill Valida
1. Criação de base de teste isolada e injeção de cenário com POP, OLT, cabos, fusões, CTO e uma foto real em formato JPEG com assinatura de magic bytes (`\xFF\xD8\xFF`).
2. Execução do backup consistente com geração de manifesto criptográfico.
3. Criação de um segundo banco isolado e diretório de storage limpo.
4. Restauração do backup no ambiente de teste com conferência de checksums SHA256.
5. Validação pós-restauração:
   - Rastreamento óptico (`trace_optical_path`) idêntico ao original e com mesma revisão topológica.
   - Restauração byte-a-byte do anexo fotográfico mantendo SHA256 e magic bytes JPEG intactos.
   - Contagem exata de inventário (sites e estruturas).

### 4.2 Executando o Drill
```bash
uv run --directory backend python scripts/restore_drill.py
```
Saída esperada:
```text
================================================================================
 RESTORE DRILL B17: SUCESSO ABSOLUTO (PASS 100%)
================================================================================
```

---

## 5. Restauração em Produção e Recuperação de Desastres

Para restaurar um backup existente:
```bash
# 1. Parar serviços que realizam mutação
docker compose stop backend worker

# 2. Executar restauração
docker compose exec -T db ... # ou via script:
./scripts/restore.sh ./backups/ftth_backup_YYYYMMDD_HHMMSS.tar.gz

# 3. Reiniciar serviços
docker compose start backend worker
```

---

## 6. Estratégia de Migração: Roll-Forward vs. Downgrade

> [!WARNING]
> O FTTH Manager **não** suporta downgrade automático para migrações destrutivas (remoção de colunas ou tabelas, truncamento de dados espaciais). 
> Em caso de falha de release:
> 1. Restaure o backup consistente imediatamente anterior à atualização.
> 2. Implemente a correção via **Roll-Forward** (nova migração corretiva `00XX_fix_...`).

---

## 7. Rotação de Segredos Operacionais

1. **SECRET_KEY**:
   - Atualize `SECRET_KEY` no `.env`.
   - Reinicie `backend` e `worker`.
   - *Impacto*: Sessões ativas de usuários serão invalidadas por segurança, exigindo novo login.
2. **Senha do Banco (`POSTGRES_PASSWORD`)**:
   - Altere a senha no PostgreSQL: `ALTER USER ftth_user WITH PASSWORD 'nova_senha';`
   - Atualize `POSTGRES_PASSWORD` e `DATABASE_URL` no `.env`.
   - Reinicie os containers.
3. **METRICS_SECRET_TOKEN**:
   - Atualize `METRICS_SECRET_TOKEN` no `.env`.
   - Reinicie `backend`. Atualize o scraper Prometheus correspondente.

---

## 8. Servidor de Tiles Cartográficos e Requisitos de Rede

### 8.1 Provedores de Tiles Suportados
O mapa operacional do FTTH Manager utiliza MapLibre GL JS e requer acesso a um servidor de tiles raster ou vetoriais:
- **Padrão OpenStreetMap**: `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`
- **CartoDB Positron / Dark**: `https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png`
- **Servidor Próprio / Offline (TileServer-GL)**: Para operações em rede fechada ou sem internet, configure o endpoint interno via configuração da organização (`/settings`).

### 8.2 Requisitos de Firewall (Egress / Ingress)
- **Ingress**: Portas `80/TCP` e `443/TCP` para acesso dos técnicos e administradores ao Caddy.
- **Egress**:
  - Acesso HTTPS (`443/TCP`) aos domínios de tiles configurados (`*.tile.openstreetmap.org`, `*.basemaps.cartocdn.com`).
  - Nenhuma outra porta de saída é requerida para a operação segura do sistema.
