# 03: Modo `json_object` para provedores sem JSON Schema (DeepSeek)

**What to build:** com `OPENAI_COMPATIBLE_STRUCTURED_OUTPUT=json_object`, o adaptador funciona com provedores que só aceitam "modo JSON" genérico, como o DeepSeek: pede um objeto JSON e coloca o JSON Schema do caso de uso nas instruções de sistema, e a resposta continua sendo validada pelo contrato existente. O padrão `json_schema` não muda. Spec: `0000-spec-llm-providers.md` (D8).

**Blocked by:** 01 — Gerar com um provedor compatível com OpenAI

**Status:** ready-for-agent

- [ ] Configuração aceita `OPENAI_COMPATIBLE_STRUCTURED_OUTPUT` (`json_schema` | `json_object`, padrão `json_schema`); valor inválido é rejeitado na inicialização
- [ ] Em `json_object`, envia `response_format` do tipo objeto JSON e anexa às instruções de sistema o JSON Schema do caso de uso com instrução explícita para responder só com JSON (contendo a palavra "json")
- [ ] Sem schema na chamada, nenhum `response_format` é enviado em nenhum dos modos
- [ ] A validação contra o contrato continua sendo a única fonte de verdade; JSON fora do contrato vira `ai_invalid_response` como hoje
- [ ] Testes sem rede: `response_format` e instruções de sistema em cada modo, ausência de `response_format` sem schema, configuração do novo campo
- [ ] Nova variável listada nos `.env.example`
- [ ] Verificado manualmente com DeepSeek (`deepseek-chat`) gerando um caso de uso válido, se houver chave disponível
