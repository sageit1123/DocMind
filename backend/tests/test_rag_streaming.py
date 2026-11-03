
import pytest

from app.llm.fake import FakeLLMClient
from app.services import rag


@pytest.mark.asyncio
async def test_stream_answer_question_returns_tokens_and_complete(
    monkeypatch,
):
    passages = [
        {
            "chunk_id": 101,
            "document_id": 10,
            "filename": "guide.pdf",
            "page": 3,
            "text": "The library opens at 9 AM.",
        }
    ]

    monkeypatch.setattr(
        rag,
        "retrieve_chunks",
        lambda query, top_k: passages,
    )

    monkeypatch.setattr(
        rag,
        "build_prompt",
        lambda question, passages: [
            {"role": "system", "content": "Test system prompt"},
            {"role": "user", "content": question},
        ],
    )

    fake_llm = FakeLLMClient(
        "The library opens at 9 AM. [1]"
    )

    events = []

    async for event in rag.stream_answer_question(
        query="When does the library open?",
        llm_client=fake_llm,
    ):
        events.append(event)

    token_events = [
        event for event in events
        if event["type"] == "token"
    ]

    complete_events = [
        event for event in events
        if event["type"] == "complete"
    ]

    assert len(token_events) > 0
    assert len(complete_events) == 1

    final_event = complete_events[0]

    assert final_event["answer"] == (
        "The library opens at 9 AM. [1]"
    )

    assert len(final_event["citations"]) == 1
    assert final_event["citations"][0]["chunk_id"] == 101
    assert final_event["sources"][0]["filename"] == "guide.pdf"


@pytest.mark.asyncio
async def test_stream_answer_question_refuses_without_passages(
    monkeypatch,
):
    monkeypatch.setattr(
        rag,
        "retrieve_chunks",
        lambda query, top_k: [],
    )

    fake_llm = FakeLLMClient()

    events = []

    async for event in rag.stream_answer_question(
        query="What is the library timing?",
        llm_client=fake_llm,
    ):
        events.append(event)

    assert events[0] == {
        "type": "token",
        "content": rag.REFUSAL_MESSAGE,
    }

    assert events[1] == {
        "type": "complete",
        "answer": rag.REFUSAL_MESSAGE,
        "citations": [],
        "sources": [],
    }


@pytest.mark.asyncio
async def test_stream_answer_question_rejects_empty_query():
    fake_llm = FakeLLMClient()

    with pytest.raises(ValueError):
        async for _ in rag.stream_answer_question(
            query="   ",
            llm_client=fake_llm,
        ):
            pass
