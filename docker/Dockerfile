FROM python:3.13-slim-bookworm

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl netcat-openbsd && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.7.9 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Usa o Python da imagem; se a versão não bater com o pyproject o build falha,
# em vez de o uv baixar outro interpretador em silêncio.
ENV UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependências antes do código: o cache da camada só é refeito quando elas mudam.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev

COPY ./app ./app
COPY alembic.ini ./
COPY migrations ./migrations

COPY docker/wait-for-postgres.sh /wait-for-postgres.sh
RUN chmod +x /wait-for-postgres.sh

# As variáveis de ambiente vêm do compose (env_file); nenhum segredo entra na imagem.
RUN useradd --system --no-create-home appuser && chown -R appuser /app
USER appuser

CMD ["sh", "-c", " \
  /wait-for-postgres.sh postgres 5432 && \
  /app/.venv/bin/python -m alembic upgrade heads && \
  /app/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 \
"]
