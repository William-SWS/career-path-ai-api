# 05: Evals e script de verificação multi-provedor

**What to build:** quem desenvolve consegue comparar modelos rodando o runner de evals contra um provedor compatível com OpenAI (escolhendo provedor, URL base, modelo e modo de saída estruturada) e confirmar rapidamente uma configuração com um script de verificação próprio. Rodar os evals sem as novas opções continua idêntico ao comportamento atual com Gemini. Spec: `0000-spec-llm-providers.md` (D12).

**Blocked by:** 01 — Gerar com um provedor compatível com OpenAI; 03 — Modo `json_object`

**Status:** ready-for-agent

- [ ] Runner de evals aceita provedor (`gemini` | `openai_compatible`, padrão `gemini`), URL base e modo de saída estruturada; sem essas opções, a execução e a saída ficam como hoje
- [ ] A chave é lida do arquivo de ambiente conforme o provedor (`GEMINI_API_KEY` ou `OPENAI_COMPATIBLE_API_KEY`); chave ausente gera mensagem clara (Ollama aceita chave qualquer — documentar ou usar valor padrão)
- [ ] O runner trabalha contra o protocolo de cliente de LLM, não contra uma classe concreta
- [ ] O nome do arquivo de resultado e o cabeçalho do JSON identificam provedor e modelo
- [ ] Novo script de verificação para o provedor compatível, espelhando o do Gemini (lê o arquivo de ambiente, faz uma chamada mínima, informa sucesso ou o erro traduzido); o script do Gemini não muda
- [ ] README dos evals atualizado com um exemplo de execução contra Ollama
- [ ] Verificado manualmente: um eval completo contra Ollama local e o script de verificação com configuração válida e inválida
