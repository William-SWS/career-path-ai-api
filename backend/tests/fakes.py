class FakeSession:
    """Sessão que só registra o que o caso de uso fez, para afirmar a fronteira transacional."""

    def __init__(self, commit_error: Exception | None = None):
        self.commit_error = commit_error
        self.commits = 0
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass

    async def refresh(self, obj):
        pass

    async def commit(self):
        if self.commit_error:
            raise self.commit_error
        self.commits += 1


class FakeLLM:
    """LLM determinístico: devolve um texto roteirizado (ou falha) e registra as chamadas."""

    def __init__(self, text: str = "{}", error: Exception | None = None):
        self.text = text
        self.error = error
        self.calls = []

    async def generate(self, prompt, params, response_schema=None):
        self.calls.append((prompt, params, response_schema))
        if self.error:
            raise self.error
        return self.text


def sample_output(schema):
    """Instância mínima e válida de um schema de saída da IA, como dict pronto para json.dumps."""
    from typing import Literal, get_args, get_origin

    from pydantic import BaseModel

    def build(annotation):
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            return {n: build(f.annotation) for n, f in annotation.model_fields.items()}
        if get_origin(annotation) is list:
            return [build(get_args(annotation)[0])]
        if get_origin(annotation) is Literal:
            return get_args(annotation)[0]
        return "x"

    return build(schema)
