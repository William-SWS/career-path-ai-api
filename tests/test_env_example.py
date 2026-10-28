"""O .env.example é a documentação das variáveis: tem que listar todas as do Settings."""

import re
from pathlib import Path

from app.core.config import Settings

# Detalhes internos que não fazem sentido configurar por ambiente.
INTERNAL = {"API_V1_STR", "APP_NAME"}


def test_env_example_lists_every_setting():
    example = Path(__file__).parent.parent / ".env.example"
    documented = {m.group(1) for m in re.finditer(r"^([A-Z_]+)=", example.read_text(), re.M)}

    missing = set(Settings.model_fields) - INTERNAL - documented

    assert not missing, f"faltam no .env.example: {sorted(missing)}"
