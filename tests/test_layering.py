"""`core/` é a base: não pode importar das camadas que dependem dele."""

import ast
from pathlib import Path

CORE = Path(__file__).parent.parent / "app" / "core"
UPPER_LAYERS = {"api", "llm", "models", "repository", "schemas", "security", "services", "utils"}


def imported_layers(path: Path) -> set[str]:
    layers = set()
    for node in ast.walk(ast.parse(path.read_text())):
        names = []
        if isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        elif isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        for name in names:
            parts = name.split(".")
            if parts[0] == "app" and len(parts) > 1:
                layers.add(parts[1])
    return layers


def test_core_does_not_import_from_the_layers_above_it():
    offenders = {
        path.name: sorted(imported_layers(path) & UPPER_LAYERS) for path in CORE.glob("*.py")
    }

    assert {name: layers for name, layers in offenders.items() if layers} == {}
