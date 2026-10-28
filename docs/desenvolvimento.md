# Desenvolvimento

Como configurar, rodar e verificar o backend fora do Docker. Para subir o projeto completo com Docker, veja o [README](../README.md#como-executar-docker).

Todos os comandos abaixo partem de `backend/`. Pré-requisitos: Python 3.13 e [`uv`](https://docs.astral.sh/uv/).

## Rodar localmente

```bash
cd backend
uv sync --locked                 # instala as dependências do uv.lock (inclui as de desenvolvimento)
cp .env.example .env             # preencha conforme a tabela abaixo
```

Você precisa de um PostgreSQL acessível. Uma opção descartável:

```bash
docker run -d --name careerpath-pg -p 5432:5432 \
  -e POSTGRES_PASSWORD=<senha> -e POSTGRES_DB=careerpath postgres:17
```

Com `POSTGRES_HOST=localhost` e `POSTGRES_PORT=5432` no `.env`:

```bash
uv run alembic upgrade head                        # cria/atualiza as tabelas
uv run uvicorn app.main:app --reload --port 8000   # API em http://localhost:8000/docs
```

O `REDIS_URL` pode ficar vazio: o rate limit usa então um contador em memória (adequado só para desenvolvimento). Para usar Redis de verdade, defina, por exemplo, `REDIS_URL=redis://localhost:6379/0`.

Remova o container quando terminar: `docker rm -f careerpath-pg`.

## Configuração

Todas as variáveis são lidas por `app/core/config.py` (`Settings`). Sem as obrigatórias, a API **não inicia**. O modelo de arquivo é `backend/.env.example`, e um teste (`tests/test_env_example.py`) garante que ele lista toda variável da classe.

**Obrigatórias**

| Variável | Para quê |
|---|---|
| `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | conexão com o banco (`postgres`/`5432` dentro do Docker; `localhost` fora) |
| `FRONTEND_HOST` | origem permitida no CORS (ex.: `http://localhost:5173`); também usada nos links de e-mail |
| `SECRET_KEY` | assina os JWT; **mínimo de 32 caracteres** |
| `DEBUG` | `true` ou `false` |
| `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_FROM` | conta SMTP usada na recuperação de senha |
| `GEMINI_API_KEY` | chave da API do Gemini |

**Opcionais (valor padrão entre parênteses)**

| Variável | Para quê |
|---|---|
| `ALGORITHM` (`HS256`) | algoritmo do JWT (`HS256`, `HS384` ou `HS512`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` (30), `REFRESH_TOKEN_EXPIRE_DAYS` (7), `RESET_PASSWORD_TOKEN_EXPIRE_HOURS` (1) | validade dos tokens |
| `MAIL_SERVER` (`smtp.gmail.com`), `MAIL_PORT` (587), `MAIL_STARTTLS` (`true`), `MAIL_SSL_TLS` (`false`), `USE_CREDENTIALS` (`true`) | parâmetros SMTP |
| `GEMINI_MODEL` (`gemini-2.5-flash`) | modelo usado |
| `GEMINI_TIMEOUT_SECONDS` (90; entre 20 e 300) | tempo máximo **total** de uma geração, somadas as tentativas |
| `GEMINI_THINKING_BUDGET` (0; de -1 a 24576) | 0 desliga o raciocínio, -1 deixa o modelo decidir. Nem todo modelo aceita 0. Ver [`decisoes.md`](decisoes.md) |
| `GEMINI_MAX_ATTEMPTS` (3; de 1 a 5) | tentativas por geração em falhas transitórias (1 = sem retry) |
| `REDIS_URL` (vazio) | Redis do rate limit; vazio = contador em memória |
| `TRUSTED_PROXY_COUNT` (0; de 0 a 5) | quantos proxies confiáveis existem na frente da API; só com valor maior que 0 o `X-Forwarded-For` é lido |
| `RATE_LIMIT_LOGIN` (`5/minute`), `RATE_LIMIT_REGISTER` (`3/minute`), `RATE_LIMIT_FORGOT_PASSWORD` (`3/hour`), `RATE_LIMIT_RESET_PASSWORD` (`10/hour`) | limites das rotas de autenticação |
| `RATE_LIMIT_AI_USER_HOURLY` (`10/hour`), `RATE_LIMIT_AI_USER_BURST` (`3/minute`), `RATE_LIMIT_AI_GLOBAL` (`20/minute`) | limites da geração com IA, por usuário e global |

Os limites usam o formato `<n>/<minute|hour|day>`; um valor inválido impede a API de iniciar.

Nunca versione o `.env` nem coloque segredos em mensagens, issues ou logs. A chave do Gemini é lida do ambiente e nenhum script a imprime.

## Qualidade

### Verificações estáticas

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

### Testes

Sem nenhum serviço externo, rodam os testes unitários; os de integração são pulados:

```bash
uv run pytest
```

Para rodar **tudo**, aponte para um PostgreSQL e um Redis descartáveis. Os testes de integração aplicam as migrations no banco indicado e **esvaziam as tabelas** (`TRUNCATE`) a cada teste, então **use um banco só para teste, nunca o de desenvolvimento**:

```bash
docker run -d --name cp-test-pg -p 55432:5432 -e POSTGRES_PASSWORD=test -e POSTGRES_DB=test postgres:17
docker run -d --name cp-test-redis -p 56379:6379 redis:7-alpine

TEST_DATABASE_URL=postgresql://postgres:test@127.0.0.1:55432/test \
REDIS_TEST_URL=redis://127.0.0.1:56379/0 \
uv run pytest

docker rm -f cp-test-pg cp-test-redis
```

Os testes nunca chamam o Gemini: usam um LLM falso (`tests/fakes.py`). O CI executa exatamente estas etapas (`.github/workflows/ci.yml`), com PostgreSQL 17 e Redis 7 como serviços, mais o build da imagem.

### Avaliação da geração com IA

Manual, fora dos testes, porque usa a rede e a cota da chave. Instruções, critérios e o que ela **não** mede: [`backend/evals/README.md`](../backend/evals/README.md).

```bash
uv run python -m evals.run_eval --dry-run                # só conta as chamadas
uv run python -m evals.run_eval --env-file .env.docker   # 36 chamadas reais
```

### Verificar a chave do Gemini

```bash
uv run python -m scripts.check_gemini --env-file .env
```

Lista os modelos visíveis e faz uma chamada mínima. A chave não é impressa.

## Migrations

```bash
uv run alembic revision --autogenerate -m "descrição"   # revise o arquivo gerado antes de aplicar
uv run alembic upgrade head
uv run alembic downgrade -1
```

Se você alterar um modelo e esquecer a migration, o teste de integração `test_schema_drift.py` falha.

## Contêiner

O backend roda em Python 3.13 como usuário não-root, sem segredos na imagem. As migrations são aplicadas quando o container sobe. Para construir só a imagem: `docker build -f backend/docker/Dockerfile backend`.
