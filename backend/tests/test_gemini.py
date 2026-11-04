
from types import SimpleNamespace

import pytest

from app.llm.gemini import GeminiLLMClient


class FakeGeminiError(Exception):
    def __init__(self, code: int):
        super().__init__(f"Fake Gemini error: {code}")
        self.code = code


class FakeGeminiModels:
    """
    Simulates Gemini SDK methods without making API calls.
    """

    def __init__(self, stream_outcomes=None, generate_outcomes=None):
        self.stream_outcomes = list(stream_outcomes or [])
        self.generate_outcomes = list(generate_outcomes or [])

        self.stream_calls = 0
        self.generate_calls = 0

    async def generate_content_stream(self, **kwargs):
        self.stream_calls += 1

        outcome = self.stream_outcomes.pop(0)

        async def fake_stream():
            for item in outcome:
                if isinstance(item, Exception):
                    raise item

                yield SimpleNamespace(text=item)

        return fake_stream()

    async def generate_content(self, **kwargs):
        self.generate_calls += 1

        outcome = self.generate_outcomes.pop(0)

        if isinstance(outcome, Exception):
            raise outcome

        return SimpleNamespace(text=outcome)


def make_client(models):
    """
    Construct the client without requiring an API key.
    """

    client = GeminiLLMClient.__new__(GeminiLLMClient)
    client.model = "test-model"
    client.async_client = SimpleNamespace(models=models)

    return client


async def no_wait(_seconds):
    """
    Replace retry delays so tests run immediately.
    """
    return None


@pytest.mark.asyncio
async def test_stream_retries_503_then_succeeds(monkeypatch):
    import app.llm.gemini as gemini_module

    monkeypatch.setattr(gemini_module.asyncio, "sleep", no_wait)

    models = FakeGeminiModels(
        stream_outcomes=[
            [FakeGeminiError(503)],
            ["Hello", " world"],
        ]
    )

    client = make_client(models)

    chunks = [
        chunk
        async for chunk in client.stream([
            {"role": "user", "content": "Say hello"}
        ])
    ]

    assert chunks == ["Hello", " world"]
    assert models.stream_calls == 2


@pytest.mark.asyncio
async def test_stream_stops_after_three_503_attempts(monkeypatch):
    import app.llm.gemini as gemini_module

    monkeypatch.setattr(gemini_module.asyncio, "sleep", no_wait)

    models = FakeGeminiModels(
        stream_outcomes=[
            [FakeGeminiError(503)],
            [FakeGeminiError(503)],
            [FakeGeminiError(503)],
        ]
    )

    client = make_client(models)

    with pytest.raises(FakeGeminiError):
        async for _ in client.stream([
            {"role": "user", "content": "Say hello"}
        ]):
            pass

    assert models.stream_calls == 3


@pytest.mark.asyncio
async def test_stream_does_not_retry_after_partial_output(monkeypatch):
    import app.llm.gemini as gemini_module

    monkeypatch.setattr(gemini_module.asyncio, "sleep", no_wait)

    models = FakeGeminiModels(
        stream_outcomes=[
            ["Partial answer", FakeGeminiError(503)],
            ["This must not be generated"],
        ]
    )

    client = make_client(models)

    chunks = []

    with pytest.raises(FakeGeminiError):
        async for chunk in client.stream([
            {"role": "user", "content": "Explain something"}
        ]):
            chunks.append(chunk)

    assert chunks == ["Partial answer"]
    assert models.stream_calls == 1


@pytest.mark.asyncio
async def test_stream_does_not_retry_quota_error(monkeypatch):
    import app.llm.gemini as gemini_module

    monkeypatch.setattr(gemini_module.asyncio, "sleep", no_wait)

    models = FakeGeminiModels(
        stream_outcomes=[
            [FakeGeminiError(429)],
            ["This must not be generated"],
        ]
    )

    client = make_client(models)

    with pytest.raises(FakeGeminiError):
        async for _ in client.stream([
            {"role": "user", "content": "Say hello"}
        ]):
            pass

    assert models.stream_calls == 1


@pytest.mark.asyncio
async def test_generate_retries_503_then_succeeds(monkeypatch):
    import app.llm.gemini as gemini_module

    monkeypatch.setattr(gemini_module.asyncio, "sleep", no_wait)

    models = FakeGeminiModels(
        generate_outcomes=[
            FakeGeminiError(503),
            "Successful answer",
        ]
    )

    client = make_client(models)

    answer = await client.generate([
        {"role": "user", "content": "Say hello"}
    ])

    assert answer == "Successful answer"
    assert models.generate_calls == 2
