# 04: Tolerar modelos de raciocínio

**What to build:** modelos que "pensam em voz alta" (ex.: qwen3 e deepseek-r1 no Ollama) podem ser usados sem quebrar a validação do JSON: o bloco `<think>…</think>` no início da resposta é descartado antes de devolver o texto, e os tokens de raciocínio aparecem no log quando o provedor os informa. Spec: `0000-spec-llm-providers.md` (D9).

**Blocked by:** 01 — Gerar com um provedor compatível com OpenAI

**Status:** ready-for-agent

- [ ] Um bloco `<think>…</think>` no início do conteúdo (com espaços/quebras de linha ao redor) é removido; conteúdo sem esse bloco não é alterado
- [ ] Se só restar o bloco de raciocínio e nada depois, a resposta é tratada como vazia (`ai_invalid_response`)
- [ ] Tokens de raciocínio do uso informado pelo provedor entram no log de sucesso quando presentes, sem quebrar quando ausentes
- [ ] Sem controle de thinking budget no adaptador compatível; `GEMINI_THINKING_BUDGET` continua só para o Gemini
- [ ] Testes sem rede: remoção do bloco, conteúdo sem bloco intacto, resposta só com bloco, log com e sem tokens de raciocínio
