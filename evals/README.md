# Avaliação da geração com IA

Conjunto **sintético** (6 perfis fictícios, nenhum dado real) para medir como o pipeline
`prompt → Gemini → schema` se comporta com a chave real. É manual e fica fora do `pytest`
padrão: usa a rede e gasta cota.

```bash
python -m evals.run_eval --dry-run                      # só conta as chamadas
python -m evals.run_eval --env-file .env         # 6 casos x 3 usos x 2 repetições = 36 chamadas
python -m evals.run_eval --env-file .env --cases junior_backend --reps 3
python -m evals.run_eval --env-file .env --thinking-budget -1   # compara com raciocínio dinâmico
```

O relatório completo (saídas e latências) vai para `evals/results/` (ignorado pelo git).

## O que é medido

Só critérios objetivos e determinísticos, testados em `tests/test_eval_checks.py`:

| Uso | Critérios |
|---|---|
| todos | chamada válida (schema), português, sem campo vazio, sem termo proibido (injeção) |
| trilha | nº de fases coerente com o prazo, projeto e tópicos em cada fase, cita o interesse do usuário, repete a disponibilidade |
| análise | encontra as skills do currículo, **não inventa** skills ausentes, nível de senioridade esperado, estabilidade do nível entre repetições |
| guia | toca em requisito da vaga, tem perguntas comportamentais, tem ações para as próximas 24 h |

## O que NÃO é medido

- **Qualidade do conteúdo** (cursos recomendados existem? o conselho é bom?). Isso exige revisão humana.
- Viés, adequação cultural, factualidade das recomendações de mercado.
- Robustez geral contra injeção: há 1 caso com injeção no currículo, o que é uma amostra, não uma garantia.

Os resultados valem para o modelo, os prompts e a data da execução; mudar qualquer um exige rodar de novo.
