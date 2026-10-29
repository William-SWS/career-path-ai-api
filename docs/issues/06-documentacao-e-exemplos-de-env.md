# 06: Documentação e exemplos de `.env`

**What to build:** um desenvolvedor novo configura qualquer um dos provedores em minutos: a documentação explica como escolher o provedor, traz blocos prontos de `.env` para Ollama, DeepSeek e NVIDIA NIM, e explica como alcançar o Ollama da máquina a partir do Docker. Os `.env.example` refletem todas as variáveis novas. Spec: `0000-spec-llm-providers.md` (D13).

**Blocked by:** 01 — Gerar com um provedor compatível com OpenAI; 03 — Modo `json_object`

**Status:** ready-for-agent

- [ ] README (seção de configuração) explica `LLM_PROVIDER`, que o padrão continua sendo Gemini e que nada muda para quem já usa
- [ ] Exemplos prontos: Ollama (`http://localhost:11434/v1`, `json_schema`), DeepSeek (`https://api.deepseek.com`, `deepseek-chat`, `json_object`) e NVIDIA NIM (`https://integrate.api.nvidia.com/v1`, `json_schema`)
- [ ] Guia de Docker explica usar `http://host.docker.internal:11434/v1` para o Ollama do host (e o `extra_hosts` necessário no Linux, se aplicável ao compose do projeto)
- [ ] Todos os `.env.example` listam as variáveis `LLM_PROVIDER` e `OPENAI_COMPATIBLE_*` com comentários curtos
- [ ] Linha quebrada `GEMINI_API_KEY=GEMINI_MODEL=…` do `.env.example` do backend corrigida em duas linhas
- [ ] Nota sobre modelos que não respeitam JSON Schema: tentar `json_object`
- [ ] Nenhuma variável `GEMINI_*` documentada mudou de nome ou significado
