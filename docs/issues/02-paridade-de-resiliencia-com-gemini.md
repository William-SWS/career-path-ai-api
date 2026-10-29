# 02: Paridade de resiliência com o Gemini

**What to build:** o adaptador compatível se comporta como o Gemini diante de falhas: instabilidades passageiras são retentadas, cota esgotada é avisada na hora, a espera total nunca passa do limite configurado e o usuário final vê as mesmas mensagens e códigos de erro qualquer que seja o provedor. O log registra só números. Spec: `0000-spec-llm-providers.md` (D10).

**Blocked by:** 01 — Gerar com um provedor compatível com OpenAI

**Status:** ready-for-agent

- [ ] Retry só em HTTP 500/502/503/504 e falhas de conexão, com backoff exponencial e jitter, até `OPENAI_COMPATIBLE_MAX_ATTEMPTS`; timeout não é retentado
- [ ] Um teto de tempo (timeout configurado + a mesma margem usada pelo Gemini) cobre todas as tentativas juntas
- [ ] 429 → `RateLimitException` com código `ai_quota_exceeded`, sem retry
- [ ] Demais erros HTTP → `ai_provider_error`; timeout → `ai_timeout`; falha de conexão → `ai_provider_error`
- [ ] Resposta sem conteúdo → `ai_invalid_response`; corte por limite de tokens (`finish_reason` "length") → aviso no log
- [ ] Log de sucesso só com modelo, latência, tentativas, tokens de prompt e de saída; nunca conteúdo de prompt/resposta; mensagens de erro do provedor logadas sem ecoar conteúdo gerado
- [ ] Loop de retry duplicado no adaptador novo; o cliente Gemini não é alterado
- [ ] Testes sem rede com SDK e `sleep` falsos cobrindo cada tradução, retry até o limite, não-retry de 429 e timeout, teto total, resposta vazia e truncamento (prior art: testes de tradução de erro do Gemini)
