import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeJXA:
    """Ersetzt osa.run_jxa: merkt sich Aufrufe und liefert vorbereitete Antworten."""

    def __init__(self):
        self.calls = []
        self.response = None

    async def __call__(self, script, payload=None, timeout=None):
        self.calls.append((script, payload))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@pytest.fixture
def fake_jxa(monkeypatch):
    from notes_mcp import osa

    fake = FakeJXA()
    monkeypatch.setattr(osa, "run_jxa", fake)
    return fake
