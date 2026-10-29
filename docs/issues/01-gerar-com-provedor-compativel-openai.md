# 01: Gerar com um provedor compatível com OpenAI (tracer bullet)

**What to build:** com `LLM_PROVIDER=openai_compatible` e URL base, chave e modelo de um provedor compatível no `.env` (ex.: Ollama local), a API gera uma trilha de desenvolvimento, um guia de entrevista e uma análise de currículo reais, com saída estruturada no modo `json_schema` validada pelo contrato existente. Sem `LLM_PROVIDER`, tudo continua com o Gemini exatamente como hoje, e a API sobe sem `GEMINI_API_KEY` quando o provedor é outro. Spec: `0000-spec-llm-providers.md`.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Configuração aceita `LLM_PROVIDER` (`gemini` | `openai_compatible`, padrão `gemini`) e o grupo `OPENAI_COMPATIBLE_*` (API_KEY, BASE_URL, MODEL, TIMEOUT_SECONDS, MAX_ATTEMPTS); nenhuma variável `GEMINI_*` muda de nome ou padrão; `GEMINI_API_KEY` passa a ser opcional
- [ ] Novo adaptador compatível com OpenAI implementa o protocolo de cliente de LLM existente usando o SDK `openai` com o retry interno desligado
- [ ] Instruções de sistema viram mensagem `system`, o texto do usuário vira mensagem `user`; `temperature`, `top_p` e máximo de tokens são enviados; `top_k` não é enviado
- [ ] Com schema, envia `response_format` do tipo JSON Schema gerado a partir do modelo Pydantic do caso de uso
- [ ] Sem URL base ou modelo configurado, a geração responde "IA indisponível" (`ai_unavailable`) e o resto da API funciona
- [ ] A fábrica de cliente escolhe o adaptador pelo `LLM_PROVIDER` (import tardio do módulo novo); nenhum import existente muda e o cliente Gemini não é alterado
- [ ] Testes sem rede pela seam da spec (SDK falso injetado): caminho feliz com `response_format`, ausência de `top_k`, cliente indisponível; testes de configuração (padrão `gemini`, valor inválido rejeitado, `GEMINI_API_KEY` opcional) e da fábrica
- [ ] Novas variáveis listadas (vazias, com comentário curto) nos `.env.example`
- [ ] Verificado manualmente contra um Ollama local gerando ao menos um caso de uso pelo endpoint
