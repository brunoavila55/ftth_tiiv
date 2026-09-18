# Guia de Contribuição — FTTH Manager

Agradecemos o seu interesse em contribuir com o **FTTH Manager**! Este projeto é um software livre e de código aberto voltado para provedores regionais de internet, operadoras neutras e engenheiros de telecomunicações.

---

## 1. Princípios do Projeto

1. **Rigor e Precisão Técnica**: O motor óptico e os modelos de dados devem refletir com exatidão a física das telecomunicações (ITU-T G.984/G.9807, ABNT NBR 14106, TIA-598-C).
2. **Contrato em Primeiro Lugar**: Qualquer alteração em endpoints ou modelos de dados deve ser refletida no contrato compartilhado `contracts/openapi.json` e nos tipos TypeScript gerados.
3. **Qualidade sem Concessões**: Nenhum pull request é aprovado com testes falhando, alertas de linter ou inconsistências de tipagem estática.
4. **Segurança por Padrão**: Todas as rotas mutantes exigem proteção CSRF, validação de permissões RBAC e concorrência otimista via `If-Match`.

---

## 2. Configuração do Ambiente de Desenvolvimento

### Requisitos Prévios
- **Docker e Docker Compose** (para o PostgreSQL 16 com PostGIS 3.4)
- **Python 3.12+** e gerenciador de pacotes [`uv`](https://github.com/astral-sh/uv)
- **Node.js 20+** e gerenciador de pacotes [`pnpm`](https://pnpm.io/)

### Passo a Passo de Inicialização

1. **Subir o Banco de Dados com PostGIS**:
   ```bash
   docker compose up -d db
   ```

2. **Configurar o Backend**:
   ```bash
   cd backend
   uv sync
   uv run alembic upgrade head
   ```

3. **Configurar o Frontend**:
   ```bash
   cd frontend
   pnpm install
   ```

4. **Popular Dados de Demonstração (Opt-in)**:
   ```bash
   cd backend
   uv run python scripts/seed_demo.py --clean
   ```

---

## 3. Fluxo de Trabalho e Padrões de Código

### 3.1. Backend (Python)
- **Linter e Formatador**: Usamos o `ruff`.
  ```bash
  cd backend
  uv run ruff check .
  uv run ruff format .
  ```
- **Verificação de Tipos**: Usamos o `mypy` com tipagem estrita.
  ```bash
  cd backend
  uv run mypy app
  ```
- **Testes**: Usamos o `pytest` com cobertura.
  ```bash
  cd backend
  uv run pytest
  ```

### 3.2. Frontend (Next.js / TypeScript)
- **Linter**: Usamos o `next lint` (ESLint).
  ```bash
  cd frontend
  pnpm lint
  ```
- **Verificação de Tipos**: Usamos o compilador TypeScript.
  ```bash
  cd frontend
  pnpm typecheck
  ```
- **Testes Unitários e Componentes**: Usamos o `vitest`.
  ```bash
  cd frontend
  pnpm test
  ```

### 3.3. Sincronização do Contrato OpenAPI
Se você alterar qualquer rota, schema Pydantic ou parâmetro de endpoint no backend:
```bash
# 1. Exportar o novo schema OpenAPI atualizado
cd backend
uv run python scripts/export_openapi.py

# 2. Gerar os tipos TypeScript correspondentes no frontend
cd ../frontend
pnpm codegen:types

# 3. Validar se não há drift
cd ../backend
uv run pytest tests/contract/test_openapi_schema.py
```

---

## 4. Padrão de Commits

Utilizamos o padrão de **Conventional Commits**:
- `feat(modulo): breve descrição da funcionalidade`
- `fix(modulo): correção de bug ou inconsistência`
- `docs(modulo): adição ou correção de documentação`
- `test(modulo): criação ou ampliação de testes automatizados`
- `refactor(modulo): refatoração de código sem alteração funcional`
- `chore(modulo): manutenção de dependências ou build`

---

## 5. Submissão de Pull Requests

1. Crie uma branch a partir da `master` ou `main`:
   ```bash
   git checkout -b feat/minha-melhoria
   ```
2. Realize suas alterações com testes correspondentes.
3. Garanta que a suíte completa de verificações locais passe:
   ```bash
   # Backend
   cd backend && uv run ruff check . && uv run mypy app && uv run pytest
   # Frontend
   cd ../frontend && pnpm lint && pnpm typecheck && pnpm test
   ```
4. Abra o Pull Request descrevendo claramente o objetivo, os testes realizados e as decisões técnicas tomadas.
