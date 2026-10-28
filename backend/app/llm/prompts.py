from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent / "prompts"
PROMPT_VERSION = "v1"


@dataclass(frozen=True)
class Prompt:
    """Instruções fixas (confiáveis) separadas do conteúdo da requisição (não confiável)."""

    system: str
    user: str


@lru_cache
def load_system_prompt(name: str, version: str = PROMPT_VERSION) -> str:
    """Lê as instruções versionadas de `prompts/<versão>/<nome>.md`."""
    return (_PROMPTS_DIR / version / f"{name}.md").read_text(encoding="utf-8").strip()


def untrusted_block(tag: str, text: str) -> str:
    """Envolve texto de usuário/terceiros em uma tag que as instruções tratam como dado.

    Os ângulos do texto são trocados por equivalentes visuais, para que ele não consiga
    fechar a tag e escrever fora dela.
    """
    safe = text.replace("<", "‹").replace(">", "›")
    return f"<{tag}>\n{safe}\n</{tag}>"
