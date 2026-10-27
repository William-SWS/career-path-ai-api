# career-path-backend
Repositório do BackEnd do CareerPath-AI.

## Descrição
API para análise de currículos, geração de trilhas de desenvolvimento em áreas da tecnologia e de guias de entrevista utilizando Google Gemini AI. A aplicação extrai informações de PDFs e fornece análise detalhada de habilidades, nível de experiência, recomendações de carreira e insights de mercado.

## Opção 1: Execução com Docker

### Pré-requisitos
- Docker
- Docker Compose
- Chave de API do Google Gemini

### Passos para execução:

#### 1. Clone o repositório
```bash
git clone <url-do-repositorio>
cd career-path-backend
```

#### 2. Configure as variáveis de ambiente
```bash
cp .env.example .env.docker
```

#### 3. Edite o arquivo .env.docker
```env
POSTGRES_DB=seu_banco
POSTGRES_HOST=career-path-postgres
POSTGRES_PORT=5433
POSTGRES_USER=seu_user
POSTGRES_PASSWORD=sua_senha

SECRET_KEY=<gere uma chave aleatória: veja abaixo>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

GEMINI_API_KEY=sua_chave_api_gemini_aqui
```

> **`SECRET_KEY`** assina os tokens JWT e precisa ter **pelo menos 32 caracteres**; a API não inicia com uma chave menor.
> Nunca reutilize um valor de exemplo. Gere uma chave aleatória com:
>
> ```bash
> python -c "import secrets; print(secrets.token_urlsafe(48))"
> ```
>
> Se você trocar a chave, as sessões existentes deixam de valer e é preciso entrar de novo.

#### 4. Execute a aplicação
```bash
docker compose up --build
```

#### 5. Acesse a aplicação
- **API: http://localhost:8000
- **Swagger UI: http://localhost:8000/docs
- **Redoc: http://localhost:8000/redoc

## Opção 2: Execução local

### Pré requisitos
- Python 3.13
- PostgreSQL
- Chave da API do Google Gemini

### Passos para execução:

#### 1. Clone o repositório
```bash
git clone <url-do-repositorio>
cd career-path-backend
```

#### 2. Instalar o gerenciador de pacotes uv

##### No Linux/Mac
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

##### No Windows
```bash
irm https://astral.sh/uv/install.ps1 | iex
```

##### Verifique a instalação
```bash
uv --version
```

#### 3. Instalar as dependências e ativar ambiente virtual
```bash
uv sync
```

##### No Windows:
```bash
.venv\Scripts\activate
```

##### No Linux/Mac:
```bash
source .venv/bin/activate
```

#### 4. Configurar PostgreSQL

##### Opção A: Usando Docker para apenas o PostgreSQL
```bash
docker run --name career-path-postgres \
  -e POSTGRES_USER=seu_user \
  -e POSTGRES_PASSWORD=sua_senha \
  -e POSTGRES_DB=seu_db \
  -p 5432:5432 -d postgres
```

##### Opção B: PostgreSQL local

Certifique-se de ter o PostgreSQL instalado e cria o banco manualmente.

#### 5. Configure as variáveis de ambiente
```bash
cp .env.example .env
```

Edite o arquivo .env:
```env
POSTGRES_DB=seu_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=seu_user
POSTGRES_PASSWORD=sua_senha

DEBUG=False
SECRET_KEY=<gere uma chave aleatória: veja abaixo>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

GEMINI_API_KEY=sua_chave_api_gemini_aqui
```

#### 6. Aplique as migrations do banco
```bash
alembic upgrade head
```

#### 7. Execute a aplicação
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 8. Acesse a aplicação
- **API: http://localhost:8000
- **Swagger UI: http://localhost:8000/docs
- **Redoc: http://localhost:8000/redoc

## Estrutura do Projeto
```
career-path-backend/
├── alembic.ini                     # Configuração do Alembic (migrations)
├── app/                            # Código principal da aplicação
│   ├── core/                       # Configurações centrais da aplicação
│   │   ├── config.py              # Configurações de ambiente
│   │   ├── database.py            # Configuração do banco de dados
│   │   ├── security.py            # Configurações de segurança e JWT
│   │   └── tasks.py               # Tarefas em background
│   ├── dependencies/               # Dependências do FastAPI
│   │   ├── database.py            # Injeção de dependência do banco
│   │   └── security.py            # Dependências de autenticação
│   ├── models/                     # Modelos do SQLAlchemy (banco de dados)
│   │   ├── user.py                # Modelo de usuário
│   │   ├── token_blacklist.py     # Modelo para blacklist de tokens
│   │   ├── resume_analysis.py     # Modelo de análise de currículo
│   │   ├── development_trail.py   # Modelo de trilha de desenvolvimento
│   │   └── interview_guide.py     # Modelo de guia de entrevista
│   ├── routes/                     # Rotas da API (endpoints)
│   │   ├── auth_routes.py         # Autenticação (login, registro, logout)
│   │   ├── resume_analysis_routes.py # Análise de currículos
│   │   ├── development_trail_routes.py # Trilhas de desenvolvimento
│   │   ├── interview_guide_routes.py  # Guias de entrevista
│   │   └── check_routes.py        # Health checks e status
│   ├── schemas/                   # Schemas Pydantic (validação de dados)
│   │   ├── auth_schema.py         # Schemas de autenticação
│   │   ├── resume_analysis_schema.py # Schemas de análise de currículo
│   │   ├── development_trail_schema.py # Schemas de trilhas
│   │   └── interview_guide_schema.py # Schemas de guias de entrevista
│   ├── services/                  # Lógica de negócio
│   │   ├── resume_analysis_services.py # Serviços de análise de currículo
│   │   ├── development_trail_services.py # Serviços de trilhas
│   │   └── interview_guide_services.py # Serviços de guias
│   ├── utils/                     # Utilitários e helpers
│   │   ├── resume_analysis_utils.py # Utilitários para análise de currículo
│   │   ├── development_trail_utils.py # Utilitários para trilhas
│   │   ├── interview_guide_utils.py # Utilitários para guias
│   │   └── token_cleanup.py       # Limpeza de tokens expirados
│   └── main.py                    # Aplicação FastAPI principal
├── migrations/                    # Migrations do banco de dados (Alembic)
│   └── versions/                  # Histórico de migrations
├── docker/                        # Configurações do Docker
│   └── Dockerfile                 # Dockerfile da aplicação
├── docker-compose.yaml           # Orquestração de containers
├── docs/                         # Documentação
│   └── requisitos.pdf            # Documento de requisitos
├── pyproject.toml               # Dependências e configuração do projeto
├── uv.lock                      # Lock file do gerenciador uv
└── README.md                    # Este arquivo
```

## Funcionalidades
- ✅ Extração de texto de PDFs
- ✅ Análise de currículos com Google Gemini AI
- ✅ Detecção de habilidades técnicas
- ✅ Determinação de nível de experiência
- ✅ Recomendações de carreira personalizadas
- ✅ Identificação de lacunas de habilidades
- ✅ Insights de mercado
- ✅ Fallback para análise local caso a API falhe

## Tecnologias Utilizadas
- **FastAPI** - Framework web moderno
- **Google Gemini AI** - IA generativa para análise
- **PyPDF2** - Extração de texto de PDFs
- **Python-dotenv** - Gerenciamento de variáveis de ambiente
- **Uvicorn** - Servidor ASGI

## Troubleshooting

### Erro de chave de API
Certifique-se de que a variável `GEMINI_API_KEY` está configurada corretamente no arquivo `.env`.

### Problemas com PDF
- A API suporta apenas PDFs não criptografados
- PDFs devem conter texto extraível (não apenas imagens)

### Porta em uso
Se a porta 8000 estiver em uso, altere a porta no comando de execução:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```