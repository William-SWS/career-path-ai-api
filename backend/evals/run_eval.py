"""Avaliação manual da geração com a chave real. Fora da suíte padrão: gasta cota e usa a rede.

Uso (a partir de backend/):
    python -m evals.run_eval --dry-run
    python -m evals.run_eval --env-file .env.docker [--reps 2] [--cases junior_backend,sparse_input]
                             [--model gemini-2.5-flash] [--thinking-budget 0]

Chama o mesmo caminho dos serviços (builder de prompt -> GeminiClient -> schema) e aplica
os critérios de evals/checks.py. Os resultados completos vão para evals/results/ (ignorado pelo git).
A chave nunca é impressa.
"""
import argparse
import asyncio
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Importar os builders carrega as settings da API; esta avaliação só precisa da chave do Gemini.
for _key, _value in {
    "FRONTEND_HOST": "x", "POSTGRES_DB": "x", "POSTGRES_HOST": "x", "POSTGRES_PORT": "1",
    "POSTGRES_USER": "x", "POSTGRES_PASSWORD": "x", "SECRET_KEY": "k" * 44, "DEBUG": "false",
    "MAIL_USERNAME": "x", "MAIL_PASSWORD": "x", "MAIL_FROM": "a@b.co", "GEMINI_API_KEY": "x",
}.items():
    os.environ.setdefault(_key, _value)

from dotenv import dotenv_values  # noqa: E402

from app.core.exceptions import AppException  # noqa: E402
from app.llm.client import GeminiClient  # noqa: E402
from app.llm.responses import parse_structured_response  # noqa: E402
from app.schemas.ai_outputs import (  # noqa: E402
    DevelopmentTrailOutput,
    InterviewGuideOutput,
    ResumeAnalysisOutput,
)
from app.utils.development_trail_utils import (  # noqa: E402
    DEVELOPMENT_TRAIL_PARAMS,
    create_adaptive_development_trail_prompt,
)
from app.utils.interview_guide_utils import INTERVIEW_GUIDE_PARAMS, build_interview_guide_prompt  # noqa: E402
from app.utils.resume_analysis_utils import RESUME_ANALYSIS_PARAMS, build_resume_analysis_prompt  # noqa: E402
from evals.cases import CASES  # noqa: E402
from evals.checks import check_guide, check_resume, check_trail  # noqa: E402

# Falhas de infraestrutura/cota não dizem nada sobre a qualidade da saída: ficam fora das taxas.
INFRA_ERRORS = {"ai_quota_exceeded", "ai_timeout", "ai_provider_error", "ai_unavailable"}
MAX_CONSECUTIVE_QUOTA_ERRORS = 2

USE_CASES = {
    "trilha": (
        lambda c: create_adaptive_development_trail_prompt(c.trail), DEVELOPMENT_TRAIL_PARAMS,
        DevelopmentTrailOutput, check_trail,
    ),
    "guia": (
        lambda c: build_interview_guide_prompt(c.resume_text, c.job_description), INTERVIEW_GUIDE_PARAMS,
        InterviewGuideOutput, check_guide,
    ),
    "analise": (
        lambda c: build_resume_analysis_prompt(c.resume_text), RESUME_ANALYSIS_PARAMS,
        ResumeAnalysisOutput, check_resume,
    ),
}


async def run_one(client: GeminiClient, use_case: str, case) -> dict:
    build, params, schema, checker = USE_CASES[use_case]
    record = {"use_case": use_case, "case": case.name}
    started = time.perf_counter()
    try:
        text = await client.generate(build(case), params, response_schema=schema)
        output = parse_structured_response(schema, text).model_dump()
    except AppException as exc:
        record.update(latency=time.perf_counter() - started, error=exc.code, checks={"chamada_valida": [False, exc.code]})
        return record
    record.update(
        latency=time.perf_counter() - started,
        output=output,
        checks={"chamada_valida": [True, ""], **{name: list(result) for name, result in checker(case, output)}},
    )
    return record


def summarize(records: list[dict]) -> str:
    lines = []
    unanswered = [r for r in records if r.get("error") in INFRA_ERRORS]
    records = [r for r in records if r.get("error") not in INFRA_ERRORS]
    if unanswered:
        by_error = defaultdict(int)
        for r in unanswered:
            by_error[r["error"]] += 1
        lines.append(f"\n!! {len(unanswered)} chamadas sem resposta do provedor, fora das taxas abaixo: {dict(by_error)}")
    for use_case in USE_CASES:
        subset = [r for r in records if r["use_case"] == use_case]
        if not subset:
            continue
        latencies = sorted(r["latency"] for r in subset)
        lines.append(f"\n== {use_case}: {len(subset)} chamadas, latência média {sum(latencies)/len(latencies):.1f}s, máx {latencies[-1]:.1f}s")
        per_check = defaultdict(lambda: [0, 0])
        for r in subset:
            for name, (ok, _) in r["checks"].items():
                per_check[name][0] += ok
                per_check[name][1] += 1
        for name, (ok, total) in per_check.items():
            lines.append(f"   {'ok ' if ok == total else 'FALHA'} {name}: {ok}/{total}")
    failures = [
        f"   {r['use_case']}/{r['case']}: {name} -> {detail}"
        for r in records for name, (ok, detail) in r["checks"].items() if not ok
    ]
    lines.append("\n== Falhas (critério -> detalhe)" if failures else "\n== Nenhuma falha")
    lines.extend(failures)

    # Consistência: o mesmo currículo deve receber o mesmo nível nas repetições.
    levels = defaultdict(set)
    for r in records:
        if r["use_case"] == "analise" and "output" in r:
            levels[r["case"]].add(r["output"]["experience_level"])
    unstable = {case: sorted(v) for case, v in levels.items() if len(v) > 1}
    lines.append(f"\n== Consistência do nível entre repetições: {'instável em ' + str(unstable) if unstable else 'estável'}")
    return "\n".join(lines)


async def main_async(args) -> int:
    selected = [c for c in CASES if not args.cases or c.name in args.cases.split(",")]
    plan = [(u, c) for c in selected for u in USE_CASES for _ in range(args.reps)]
    print(f"{len(plan)} chamadas planejadas ({len(selected)} casos x {len(USE_CASES)} usos x {args.reps} repetições)")
    if args.dry_run:
        return 0

    api_key = dotenv_values(args.env_file).get("GEMINI_API_KEY") or ""
    if not api_key:
        print(f"GEMINI_API_KEY ausente em {args.env_file}")
        return 1
    client = GeminiClient(api_key=api_key, model=args.model, timeout_seconds=120, thinking_budget=args.thinking_budget)

    records = []
    quota_streak = 0
    for index, (use_case, case) in enumerate(plan, 1):  # em sequência: não pressiona a cota nem provoca 503
        record = await run_one(client, use_case, case)
        records.append(record)
        print(f"[{index}/{len(plan)}] {use_case}/{case.name}: {record['latency']:.1f}s {'ERRO ' + record['error'] if 'error' in record else ''}", flush=True)
        quota_streak = quota_streak + 1 if record.get("error") == "ai_quota_exceeded" else 0
        if quota_streak >= MAX_CONSECUTIVE_QUOTA_ERRORS:
            print(f"\nInterrompido: {quota_streak} erros de cota seguidos. Aguarde a cota renovar e rode de novo.")
            break
        await asyncio.sleep(args.pace_seconds)

    print(summarize(records))
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    path = results_dir / f"{datetime.now():%Y%m%d-%H%M%S}-{args.model}-think{args.thinking_budget}.json"
    path.write_text(json.dumps({"model": args.model, "thinking_budget": args.thinking_budget, "records": records}, ensure_ascii=False, indent=2))
    print(f"\nResultado completo: {path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--model", default="gemini-2.5-flash")
    parser.add_argument("--thinking-budget", type=int, default=0)
    parser.add_argument("--reps", type=int, default=2)
    parser.add_argument("--pace-seconds", type=float, default=4.0, help="pausa entre chamadas")
    parser.add_argument("--cases", help="nomes separados por vírgula (padrão: todos)")
    parser.add_argument("--dry-run", action="store_true", help="só mostra quantas chamadas seriam feitas")
    return asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
