import pytest


@pytest.fixture(autouse=True)
def disable_live_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARCHDIAG_LLM_PROVIDER", "off")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
