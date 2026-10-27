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
