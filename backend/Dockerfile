FROM python:3.12-slim-bookworm AS builder

# Instalar dependências de sistema mínimas para compilação/c-extensions se necessário
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Obter uv binário oficial
COPY --from=ghcr.io/astral-sh/uv:0.6.5 /uv /uvx /bin/

WORKDIR /app

# Copiar arquivos de dependências
COPY pyproject.toml uv.lock README.md ./

# Instalar dependências em .venv sem pacotes de desenvolvimento
RUN uv sync --frozen --no-dev --no-install-project

# ==============================================================================
# Estágio de Execução Final
# ==============================================================================
FROM python:3.12-slim-bookworm AS runner

# Instalar bibliotecas de runtime necessárias (ex: libgeos para shapely)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgeos-c1v5 \
    && rm -rf /var/lib/apt/lists/*

# Criar usuário não-root seguro
RUN useradd -m -u 1000 -U ftthuser

WORKDIR /app

# Copiar uv
COPY --from=ghcr.io/astral-sh/uv:0.6.5 /uv /bin/

# Copiar ambiente virtual pré-instalado
COPY --from=builder --chown=ftthuser:ftthuser /app/.venv /app/.venv

# Copiar código-fonte da aplicação
COPY --chown=ftthuser:ftthuser pyproject.toml README.md alembic.ini ./
COPY --chown=ftthuser:ftthuser app ./app
COPY --chown=ftthuser:ftthuser migrations ./migrations
COPY --chown=ftthuser:ftthuser scripts ./scripts

# Criar diretório de storage persistente
RUN mkdir -p /app/storage && chown -R ftthuser:ftthuser /app/storage

USER ftthuser

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
