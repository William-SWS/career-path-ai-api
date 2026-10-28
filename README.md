# CareerPath-AI

[![CI](https://github.com/daviolvr/career-path-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/daviolvr/career-path-ai/actions/workflows/ci.yml)

Plataforma que usa o **Google Gemini** para ajudar pessoas de tecnologia a planejar a carreira. A partir de um currículo em PDF e de dados informados pela pessoa, ela gera:

- **Análise de currículo**: resumo profissional, nível de senioridade, habilidades técnicas encontradas, recomendações de carreira, lacunas de habilidade, cargos sugeridos e insights de mercado.
- **Guia de entrevista**: roteiro de preparação (técnica, comportamental e plano de estudo) cruzando o currículo com a descrição de uma vaga.
- **Trilha de desenvolvimento**: plano em fases, com projetos, recursos e marcos, adaptado ao prazo, à disponibilidade semanal e ao nível da pessoa.

Cada resultado fica salvo no histórico da conta, que também tem cadastro, login, renovação de sessão, recuperação de senha e edição/exclusão do perfil.

## Arquitetura em uma imagem

```mermaid
flowchart LR
    FE["Frontend<br/>React + Vite"] -->|"HTTP /api/v1"| API["API FastAPI"]
    API --> PG[("PostgreSQL")]
    API --> RD[("Redis<br/>rate limit")]
    API -->|"google-genai"| GM["Gemini API"]
```

O backend segue camadas bem separadas (rotas → serviços → repositórios → modelos), com erros de domínio traduzidos em um envelope único, uma transação por caso de uso e uma camada própria para o LLM. Detalhes em [`docs/arquitetura.md`](docs/arquitetura.md), e o *porquê* de cada escolha em [`docs/decisoes.md`](docs/decisoes.md).

## Tecnologias

| Área | Escolhas |
|---|---|
| API | Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2 (assíncrono), Alembic |
| Dados | PostgreSQL 17, Redis 7 (contadores de rate limit) |
| IA | `google-genai` (Gemini), saída estruturada por schema Pydantic, prompts versionados |
| Segurança | JWT (access/refresh/reset), bcrypt, rate limiting com `limits`, CORS restrito |
| Qualidade | pytest, ruff, mypy, GitHub Actions |
| Frontend | React + Vite |

## Como executar (Docker)

Pré-requisitos: Docker, Docker Compose e uma chave da API do Gemini.

```bash
git clone https://github.com/daviolvr/career-path-ai.git
cd career-path-ai

# 1. Credenciais do PostgreSQL usadas pelo docker-compose
cp .env.example .env              # preencha POSTGRES_DB, POSTGRES_USER e POSTGRES_PASSWORD

# 2. Configuração do backend
cp backend/.env.example backend/.env.docker
```

Edite `backend/.env.docker`. Os campos obrigatórios e o que cada um faz estão em [`docs/desenvolvimento.md`](docs/desenvolvimento.md#configuração). Dentro do Docker, use `POSTGRES_HOST=postgres` e `POSTGRES_PORT=5432`. O `SECRET_KEY` precisa ter **pelo menos 32 caracteres**; para gerar um:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

```bash
# 3. Suba tudo (as migrations rodam sozinhas na inicialização do backend)
docker compose up --build
```

| Serviço | Endereço |
|---|---|
| Frontend | http://localhost:5173/login |
| API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| PostgreSQL (do host) | `localhost:5433` |

O Redis fica só na rede interna do compose (sem porta publicada). Comandos úteis: `docker compose logs -f backend`, `docker compose down` (e `down -v` para apagar também o banco).

Para rodar o backend fora do Docker, ver [`docs/desenvolvimento.md`](docs/desenvolvimento.md).

## API em resumo

Prefixo `/api/v1`. As rotas com 🔒 exigem `Authorization: Bearer <access token>`.

| Grupo | Rotas |
|---|---|
| Autenticação | `POST /auth/register`, `/auth/login`, `/auth/login-form`, `/auth/refresh` 🔒, `/auth/logout` 🔒, `/auth/forgot-password`, `/auth/reset-password` |
| Usuário | `GET /users/me` 🔒, `PATCH /users/me` 🔒, `DELETE /users/me/delete` 🔒 |
| Análise de currículo | `POST /resume-analysis/` 🔒 (PDF), `GET /resume-analysis/` 🔒, `GET`/`DELETE /resume-analysis/{id}` 🔒 |
| Guia de entrevista | `POST /interview-guide/` 🔒 (PDF + vaga), `GET /interview-guide/` 🔒, `GET`/`DELETE /interview-guide/{id}` 🔒 |
| Trilha de desenvolvimento | `POST /development-trail/` 🔒, `GET /development-trail/` 🔒, `GET`/`PATCH`/`DELETE /development-trail/{id}` 🔒 |
| Saúde | `GET /check/` |

Todo erro usa o mesmo formato:

```json
{ "error": { "status": 429, "code": "rate_limit_exceeded", "message": "Muitas requisições. ..." } }
```

Os limites de requisição (HTTP 429, com `Retry-After`) estão na [arquitetura](docs/arquitetura.md#rate-limiting).

## Qualidade

- **Testes:** 284 testes em `backend/tests` (unitários, com repositórios e LLM falsos; e de integração, contra PostgreSQL e Redis reais, que só rodam quando `TEST_DATABASE_URL` e `REDIS_TEST_URL` estão definidos). Os testes nunca chamam o Gemini.
- **CI** (GitHub Actions): `ruff check`, `ruff format --check`, `mypy`, a suíte completa com PostgreSQL 17 e Redis como serviços, e o build da imagem Docker.
- **Avaliação da IA:** há um conjunto de avaliação sintético e manual em [`backend/evals`](backend/evals/README.md), separado dos testes porque usa a rede e gasta cota.

Como rodar cada uma dessas verificações: [`docs/desenvolvimento.md`](docs/desenvolvimento.md#qualidade).
