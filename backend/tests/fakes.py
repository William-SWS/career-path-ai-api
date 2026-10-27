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

    async def generate(self, prompt, params):
        self.calls.append((prompt, params))
        if self.error:
            raise self.error
        return self.text
