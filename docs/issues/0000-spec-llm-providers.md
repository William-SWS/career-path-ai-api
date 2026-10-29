# 0000: Spec — Provedores de LLM além do Gemini

**Status:** ready-for-agent

Decisões que originaram esta spec: `docs/decisions.md`, entradas D1–D17 de 2026-10-28.

## Problem Statement

O backend só consegue gerar trilhas de desenvolvimento, guias de entrevista e análises de currículo
usando o Gemini. Isso traz três problemas para o time:

- Para desenvolver ou rodar os evals é preciso uma chave do Gemini e gastar cota, mesmo quando um
  modelo local (Ollama) bastaria.
- Quando a cota do Gemini acaba (429) ou o custo pesa, não há como trocar de provedor sem mexer no
  código.
- Não dá para comparar a qualidade de outros modelos (DeepSeek, modelos da NVIDIA, modelos locais)
  com o Gemini usando os mesmos casos de avaliação.

## Solution

Permitir que cada instalação escolha, pelo `.env`, entre o Gemini (padrão, sem mudança alguma para
quem já usa) e qualquer provedor que exponha a API de chat compatível com a OpenAI — OpenAI,
DeepSeek, NVIDIA NIM e Ollama. Para o usuário final da aplicação nada muda: os mesmos endpoints, os
mesmos formatos de resposta, as mesmas mensagens de erro. Para quem desenvolve, basta preencher URL
base, chave e modelo do provedor; os evals e um script de verificação aceitam o novo provedor.

## User Stories

1. Como desenvolvedor, quero rodar a API apontando para um Ollama local, para desenvolver as
   features de IA sem chave nem cota do Gemini.
2. Como desenvolvedor que já usa o Gemini, quero que meu `.env` atual continue funcionando sem
   nenhuma alteração, para não ser afetado pela feature.
3. Como desenvolvedor, quero subir a API sem `GEMINI_API_KEY` quando uso outro provedor, para não
   precisar de chave falsa.
4. Como operador, quero trocar o provedor de produção mudando só variáveis de ambiente, para reagir
   a cota esgotada ou custo alto sem deploy de código.
5. Como operador, quero usar o DeepSeek mesmo ele não suportando JSON Schema estrito, para ter uma
   opção barata em produção.
6. Como operador, quero usar modelos hospedados na NVIDIA (NIM), para ter mais uma opção de
   provedor.
7. Como operador, quero usar a própria OpenAI pelo mesmo adaptador, para não depender de código
   específico por provedor.
8. Como usuário final, quero receber as mesmas mensagens de erro ("limite de uso excedido",
   "serviço indisponível", "demorou demais") qualquer que seja o provedor, para ter uma experiência
   consistente.
9. Como usuário final, quero que uma instabilidade momentânea do provedor (5xx, queda de conexão)
   seja retentada automaticamente, para não ver erro por uma falha passageira.
10. Como usuário final, quero que a espera total nunca passe do tempo limite configurado, mesmo com
    retentativas, para não ficar preso numa requisição.
11. Como usuário final, quero que cota esgotada (429) seja informada na hora, sem retentativas, para
    saber logo que devo tentar mais tarde.
12. Como mantenedor, quero que respostas fora do contrato (JSON inválido ou incompleto) continuem
    sendo rejeitadas antes de salvar, para não gravar lixo no banco, qualquer que seja o provedor.
13. Como mantenedor, quero que respostas vazias ou cortadas por limite de tokens gerem erro ou
    aviso no log, como já acontece com o Gemini.
14. Como mantenedor, quero que o log registre só números (modelo, latência, tentativas, tokens),
    nunca o conteúdo de prompts e respostas, para não vazar dados pessoais.
15. Como desenvolvedor usando modelos de raciocínio no Ollama (qwen3, deepseek-r1), quero que o
    bloco `<think>` não quebre a validação do JSON, para poder testar esses modelos.
16. Como mantenedor, quero ver no log quantos tokens de raciocínio foram gastos, quando o provedor
    informa, para acompanhar custo e latência.
17. Como desenvolvedor, quero rodar o runner de evals contra um provedor compatível com OpenAI,
    escolhendo URL base, modelo e modo de saída estruturada, para comparar modelos com os mesmos
    casos.
18. Como desenvolvedor, quero que o arquivo de resultado do eval identifique o provedor e o modelo,
    para não confundir rodadas.
19. Como desenvolvedor, quero um script rápido que confirme que URL, chave e modelo do provedor
    compatível estão corretos, como já existe para o Gemini.
20. Como desenvolvedor novo no projeto, quero exemplos prontos de `.env` para Ollama, DeepSeek e
    NVIDIA, para configurar em minutos.
21. Como desenvolvedor rodando a API no Docker, quero saber qual endereço usar para alcançar o
    Ollama da minha máquina, para não perder tempo com `localhost` dentro do container.
22. Como colaborador do projeto, quero que os nomes de variáveis e a organização do código sigam os
    padrões já existentes, para revisar e manter sem estranhamento.

## Implementation Decisions

- **Dois adaptadores atrás do mesmo contrato.** O protocolo de cliente de LLM existente (prompt +
  parâmetros de geração + schema opcional → texto) não muda. O cliente Gemini não é alterado. Um
  novo adaptador "compatível com OpenAI" implementa o mesmo protocolo usando o SDK oficial `openai`
  (já presente nas dependências), parametrizado por URL base, chave e modelo, com o retry interno do
  SDK desligado.
- **Seleção do provedor.** Um provedor por processo, escolhido por `LLM_PROVIDER`
  (`gemini` | `openai_compatible`, padrão `gemini`). A fábrica de cliente já existente (um cliente
  por processo, em cache) passa a escolher o adaptador; o módulo do novo adaptador é importado de
  forma tardia. Nenhum import existente muda.
- **Configuração aditiva.** Variáveis `GEMINI_*` inalteradas; `GEMINI_API_KEY` passa a ser opcional
  (vazia = IA indisponível, comportamento que o cliente já tem). Novo grupo `OPENAI_COMPATIBLE_*`:
  `API_KEY`, `BASE_URL`, `MODEL`, `TIMEOUT_SECONDS` (mesmos limites de validação do Gemini, com
  mínimo menor), `MAX_ATTEMPTS` (1–5), `STRUCTURED_OUTPUT` (`json_schema` | `json_object`, padrão
  `json_schema`). Sem URL base ou modelo, o adaptador responde "IA indisponível" em vez de falhar
  na inicialização.
- **Mapeamento de parâmetros.** `temperature`, `top_p` e o máximo de tokens de saída são enviados;
  `top_k` não é enviado (não existe na API compatível). Sem controle de thinking budget no adaptador
  compatível. Instruções de sistema viram uma mensagem `system`; o texto do usuário, uma mensagem
  `user`.
- **Saída estruturada.** Em `json_schema`, o schema Pydantic do caso de uso é enviado como
  `response_format` do tipo JSON Schema. Em `json_object`, é enviado `response_format` do tipo
  objeto JSON e o JSON Schema é anexado às instruções de sistema, com instrução explícita de
  responder só com JSON (o DeepSeek exige a palavra "json" no prompt). Em ambos, a validação
  existente contra o contrato continua sendo a única fonte de verdade.
- **Resiliência com a mesma semântica do Gemini.** Retry só em 500/502/503/504 e falhas de conexão,
  com backoff exponencial e jitter; timeout não é retentado; um teto de tempo cobre todas as
  tentativas juntas. Tradução de erros: 429 → limite excedido (`ai_quota_exceeded`); demais erros
  HTTP → `ai_provider_error`; timeout → `ai_timeout`; falha de conexão → `ai_provider_error`;
  resposta vazia → `ai_invalid_response`; corte por limite de tokens → aviso no log. O loop de retry
  é duplicado de propósito (ver D10).
- **Modelos de raciocínio.** Um bloco `<think>…</think>` no início do conteúdo é removido antes de
  devolver o texto. Tokens de raciocínio, quando informados no uso, entram no log.
- **Log.** Só números: modelo, latência, tentativas, tokens de prompt, de saída e de raciocínio.
- **Evals e script de verificação.** O runner de evals ganha opções de provedor (padrão `gemini`),
  URL base e modo de saída estruturada; lê a chave correspondente do arquivo de ambiente; o nome do
  arquivo de resultado inclui o provedor. O script de verificação do Gemini fica como está; entra
  um script equivalente para o provedor compatível.
- **Fora do caminho do usuário final.** Rotas, serviços, schemas de saída e banco não mudam.

## Testing Decisions

- **Bons testes** exercitam só o comportamento externo: o que `generate()` devolve ou levanta, o
  que é enviado ao SDK e o que vai para o log. Nada de testar métodos privados.
- **Seam única:** a interface pública de geração do novo adaptador, com um cliente do SDK falso
  injetado pelo construtor e uma função de `sleep` falsa, sem rede. Prior art: os testes de tradução
  de erros do Gemini, que usam exatamente esse padrão.
- **Módulos testados:**
  - Adaptador compatível: caminho feliz nos dois modos de saída estruturada (incluindo o schema nas
    instruções de sistema em `json_object`), ausência de `top_k`, tradução de 429/5xx/timeout/
    conexão, retry e limite de tentativas, teto de tempo total, resposta vazia, aviso de truncamento,
    remoção do `<think>`, cliente indisponível sem URL/modelo.
  - Configuração: `LLM_PROVIDER` com padrão `gemini`, valor inválido rejeitado, `GEMINI_API_KEY`
    opcional. Prior art: testes de settings existentes.
  - Fábrica de cliente: cada valor de `LLM_PROVIDER` produz o adaptador certo (limpando o cache).
- **Serviços e rotas** não ganham testes novos: já usam um LLM falso determinístico e não dependem
  do provedor.
- Verificação manual contra Ollama local e, quando houver chave, DeepSeek/NIM via script de
  verificação e evals.

## Out of Scope

- Fallback automático entre provedores.
- Escolha de provedor por caso de uso ou por requisição.
- Adaptador nativo do Ollama (opções como `num_ctx` por requisição).
- Controle de raciocínio (thinking budget / reasoning effort) no adaptador compatível.
- Refatorar o cliente Gemini ou extrair o loop de retry para um helper comum.
- Renomear ou remover variáveis `GEMINI_*`.
- Streaming de respostas.
- Mudanças em prompts, schemas de saída, banco ou frontend.

## Further Notes

- URLs base de referência: Ollama `http://localhost:11434/v1` (no Docker,
  `http://host.docker.internal:11434/v1`), DeepSeek `https://api.deepseek.com` (modo
  `json_object`), NVIDIA NIM `https://integrate.api.nvidia.com/v1`.
- Nem todo modelo do NIM ou do Ollama respeita JSON Schema; se um modelo falhar em `json_schema`,
  o modo `json_object` é a alternativa — a validação do contrato pega o que escapar.
- O `.env.example` do backend tem hoje uma linha quebrada (`GEMINI_API_KEY=GEMINI_MODEL=…`), a ser
  corrigida junto com a documentação.
- Tickets: `docs/issues/01-*.md` a `06-*.md`.
