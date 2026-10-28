# Limitações e o que não foi verificado

Este documento separa três coisas: o que **foi verificado** (com como), o que **não foi** e o que **sei que é fraco**. Nada aqui é uma afirmação de que o projeto está pronto para produção: não está.

## Prontidão para produção

Não há evidência suficiente para afirmar isso. Falta, no mínimo:

- teste de carga e dimensionamento (pool de conexões, workers, limites do Gemini);
- observabilidade além de logs (métricas, tracing, alertas);
- política de backup e restauração do PostgreSQL;
- processo de rotação de segredos (`SECRET_KEY`, chave do Gemini, senha SMTP);
- um `healthcheck` que verifique as dependências: hoje `GET /check/` só diz que o processo responde e não consulta o banco, o Redis nem o Gemini.

## Qualidade da IA

- **Verificado:** que a saída respeita o schema, que um currículo fictício com injeção não alterou a classificação (uma amostra) e que retry, timeout e tradução de erros funcionam **com erros simulados**.
- **Não verificado:** a qualidade do conteúdo gerado. A avaliação sintética ([`evals`](../evals/README.md)) mede só critérios objetivos, e nenhuma execução chegou a completar o conjunto: a cota gratuita da chave (20 requisições por dia para o `gemini-2.5-flash`) acabou antes. Na melhor execução, **22 das 36 chamadas** foram respondidas (trilha 8, guia 7, análise 7), todas passaram em todos os critérios e o nível de senioridade ficou estável entre as repetições que rodaram. As 14 chamadas restantes não foram executadas, incluindo o caso `injection_in_resume` da trilha, então não há resultado para elas. Não rodei o conjunto completo.
- **Decisão pendente:** `GEMINI_THINKING_BUDGET=0` foi escolhido pela latência (21,7 s → 8,8 s em uma chamada por configuração). O efeito na qualidade é desconhecido.
- **Retry contra a API real:** visto funcionando **uma vez**, na avaliação: um 503 foi seguido de nova tentativa após 0,5 s e de resposta 200 (`attempts=2` no log). Fora isso, só foi testado com erros simulados. Um evento não mede a taxa de recuperação.
- Os cursos e links que o modelo recomenda **não são checados** e podem não existir.
- O modelo, os prompts e a data da avaliação determinam o resultado: mudar qualquer um exige rodá-la de novo.

## Segurança

Já tratado e testado: SECRET_KEY mínima, CORS restrito, tipos de token separados, reset de senha de uso único, blacklist no logout, ausência de ecos de dados em erros de validação, equalização de tempo no login e rate limiting.

Conhecido e **não** resolvido:

- **Cadastro revela contas:** `POST /auth/register` responde `409` quando o e-mail já existe. Corrigir exige mudar o fluxo (por exemplo, confirmar por e-mail) e o contrato com o frontend.
- **JWT em `localStorage` no frontend**, exposto a XSS. A alternativa (cookie `HttpOnly` + proteção CSRF) não foi implementada.
- **A rotação do refresh é simples, sem detecção de roubo:** reusar um refresh já revogado dá 401, mas **não** derruba as outras sessões da pessoa. Perder a resposta de uma renovação, ou duas abas renovando quase ao mesmo tempo, também dá 401 e obriga a entrar de novo. O comportamento do frontend no navegador **não foi testado** (não há testes de frontend; só verifiquei lint e build).
- **Os limites padrão são estimativas minhas**, sem base em dados de uso.
- **Sem `REDIS_URL`**, o limite fica na memória de cada processo e não protege um deploy com vários workers.
- Não foi feita revisão de dependências nem varredura de vulnerabilidades (`pip-audit` ou equivalente).

## Arquitetura e código

- Convenções de nome ainda inconsistentes em partes antigas (`*_services` vs `*_service`), e duas áreas de token/segurança (`core/security` e `utils/token_utils`) que mereciam ser unificadas.
- A limpeza agendada de tokens roda **dentro do processo da API** (APScheduler, uma vez por dia). Com vários workers, cada um agenda a sua; é idempotente, mas redundante.
- O `mypy` está em modo moderado fora dos módulos novos; o projeto não passa em `--strict`.
- Os testes de integração cobrem autenticação, transação, liberação de conexão, rate limit e divergência de schema. **Não** cobrem todos os endpoints de ponta a ponta.

## Frontend

O frontend vive em [`career-path-ai-web`](https://github.com/daviolvr/career-path-ai-web), que tem as próprias limitações documentadas. O que importa para a API:

- **Não verifiquei** como ele exibe os erros `429` (limite) e `503` (indisponível), nem o `422` com `details` por campo fora dos formulários que já leem o envelope.
- Ele não tem testes automatizados; o CI dele só roda lint, build e o build da imagem.
- Backend e frontend precisam ser implantados juntos quando o contrato muda (foi o caso da rotação do refresh token).

## O que foi medido, e a validade dessas medições

Todas as medições deste projeto são de **uma máquina, poucas amostras e, quando indicado, uma chamada só**; servem para decidir e para registrar o raciocínio, não como benchmark.

| Medição | Valor | Limite |
|---|---|---|
| Latência da trilha, `thinking` padrão vs `0` | 21,7 s vs 8,8 s | 1 chamada por configuração |
| Diferença de tempo no login (e-mail existente vs não) | ≈219 ms de diferença → 222 ms contra 221 ms | medição local, poucas repetições |
| Requisição com o Redis parado | ~3 s em toda requisição → 0,22 s após a 1ª | stack local no Docker |
| Erros do `mypy` | 105 → 0 | configuração atual |
| Testes | 314 (268 sem banco + 46 de integração/Redis) | só passam as 46 com PostgreSQL e Redis disponíveis |
