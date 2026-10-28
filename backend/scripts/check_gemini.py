"""Verificação manual da chave do Gemini: lista os modelos visíveis e faz uma chamada mínima.

Uso (a partir de backend/):
    python -m scripts.check_gemini [--env-file .env] [--model NOME]

A chave nunca é impressa. Não faz parte da suíte de testes (usa a rede e a cota real).
"""
import argparse
import asyncio
import sys

from dotenv import dotenv_values
from google import genai

from app.core.exceptions import AppException
from app.llm.client import GeminiClient, GenerationParams
from app.llm.prompts import Prompt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--model", help="modelo para o teste de chamada (padrão: GEMINI_MODEL do env-file)")
    args = parser.parse_args()

    env = dotenv_values(args.env_file)
    api_key = env.get("GEMINI_API_KEY") or ""
    if not api_key:
        print(f"GEMINI_API_KEY ausente em {args.env_file}")
        return 1

    client = genai.Client(api_key=api_key)
    print("Modelos que aceitam generateContent para esta chave:")
    for model in client.models.list():
        if "generateContent" in (model.supported_actions or []):
            print(f"  {model.name.removeprefix('models/')}")

    model_name = args.model or env.get("GEMINI_MODEL") or "gemini-2.5-flash"
    print(f"\nChamada mínima com {model_name}...")
    gemini = GeminiClient(api_key=api_key, model=model_name, timeout_seconds=30)
    params = GenerationParams(temperature=0, top_p=1, top_k=1, max_output_tokens=1024)  # modelos com thinking gastam parte do limite raciocinando
    try:
        text = asyncio.run(gemini.generate(Prompt(system="", user="Responda apenas: ok"), params))
    except AppException as exc:
        print(f"Falhou: {exc.code} - {exc.message}")
        return 1
    print(f"OK, resposta: {text[:40]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
