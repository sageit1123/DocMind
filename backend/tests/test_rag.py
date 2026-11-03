
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.services.rag import answer_question, REFUSAL_MESSAGE


def run_async(coroutine):
    """Run an async function in these synchronous pytest tests."""
    return asyncio.run(coroutine)


@patch("app.services.rag.build_prompt")
@patch("app.services.rag.retrieve_chunks")
def test_answer_question_returns_answer_and_citations(
    mock_retrieve,
    mock_build_prompt,
):
    passages = [
        {
            "chunk_id": 12,
            "document_id": 3,
            "page": 4,
            "filename": "campus_policy.pdf",
            "text": "Refunds are available within 15 days.",
            "similarity": 0.82,
        },
        {
            "chunk_id": 15,
            "document_id": 3,
            "page": 5,
            "filename": "campus_policy.pdf",
            "text": "Submit refund requests through the portal.",
            "similarity": 0.79,
        },
    ]

    mock_retrieve.return_value = passages
    mock_build_prompt.return_value = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "User prompt"},
    ]

    llm_client = AsyncMock()
    llm_client.generate.return_value = (
        "Refunds are available within 15 days [1]. "
        "Submit requests through the portal [2]."
    )

    result = run_async(
        answer_question(
            "What is the refund policy?",
            llm_client,
            top_k=5,
        )
    )

    assert "15 days [1]" in result["answer"]
    assert "portal [2]" in result["answer"]

    assert len(result["citations"]) == 2
    assert result["citations"][0]["chunk_id"] == 12
    assert result["citations"][1]["chunk_id"] == 15

    assert len(result["sources"]) == 2

    mock_retrieve.assert_called_once()
    mock_build_prompt.assert_called_once()
    llm_client.generate.assert_awaited_once()


@patch("app.services.rag.retrieve_chunks")
def test_answer_question_returns_refusal_when_no_passages(
    mock_retrieve,
):
    mock_retrieve.return_value = []

    llm_client = AsyncMock()

    result = run_async(
        answer_question(
            "What is the refund policy?",
            llm_client,
        )
    )

    assert result == {
        "answer": REFUSAL_MESSAGE,
        "citations": [],
        "sources": [],
    }

    # The LLM must not be called when retrieval is empty.
    llm_client.generate.assert_not_awaited()


def test_answer_question_rejects_empty_query():
    llm_client = AsyncMock()

    with pytest.raises(ValueError, match="Question cannot be empty"):
        run_async(
            answer_question(
                "   ",
                llm_client,
            )
        )

    llm_client.generate.assert_not_awaited()


@patch("app.services.rag.build_prompt")
@patch("app.services.rag.retrieve_chunks")
def test_answer_question_removes_invalid_citations(
    mock_retrieve,
    mock_build_prompt,
):
    passages = [
        {
            "chunk_id": 12,
            "document_id": 3,
            "page": 4,
            "filename": "campus_policy.pdf",
            "text": "Refunds are available within 15 days.",
        }
    ]

    mock_retrieve.return_value = passages
    mock_build_prompt.return_value = [
        {"role": "system", "content": "System instructions"},
        {"role": "user", "content": "Current question and retrieved context"},
    ]
    

    llm_client = AsyncMock()
    llm_client.generate.return_value = (
        "Refunds are available within 15 days [1]. "
        "Processing takes 5 days [8]."
    )

    result = run_async(
        answer_question(
            "What is the refund policy?",
            llm_client,
        )
    )

    assert "[1]" in result["answer"]
    assert "[8]" not in result["answer"]
    assert len(result["citations"]) == 1


@patch("app.services.rag.build_prompt")
@patch("app.services.rag.retrieve_chunks")
def test_answer_question_does_not_duplicate_citations(
    mock_retrieve,
    mock_build_prompt,
):
    passages = [
        {
            "chunk_id": 12,
            "document_id": 3,
            "page": 4,
            "filename": "campus_policy.pdf",
            "text": "Refunds are available within 15 days.",
        }
    ]

    mock_retrieve.return_value = passages
    mock_build_prompt.return_value = [
        {"role": "system", "content": "System instructions"},
        {"role": "user", "content": "Current question and retrieved context"},
    ]

    llm_client = AsyncMock()
    llm_client.generate.return_value = (
        "Refunds are available within 15 days [1]. "
        "The refund window is 15 days [1]."
    )

    result = run_async(
        answer_question(
            "What is the refund policy?",
            llm_client,
        )
    )

    assert result["answer"].count("[1]") == 2
    assert len(result["citations"]) == 1
    assert len(result["sources"]) == 1


@patch("app.services.rag.build_prompt")
@patch("app.services.rag.retrieve_chunks")
def test_answer_question_includes_conversation_history(
    mock_retrieve,
    mock_build_prompt,
):
    passages = [
        {
            "chunk_id": 12,
            "document_id": 3,
            "page": 4,
            "filename": "campus_policy.pdf",
            "text": "Refund requests must be submitted through the portal.",
        }
    ]

    mock_retrieve.return_value = passages

    mock_build_prompt.return_value = [
        {
            "role": "system",
            "content": "System instructions",
        },
        {
            "role": "user",
            "content": "Current question and retrieved context",
        },
    ]

    history = [
        {
            "role": "user",
            "content": "What is the refund policy?",
        },
        {
            "role": "assistant",
            "content": "Refunds are available within 15 days [1].",
        },
    ]

    llm_client = AsyncMock()
    llm_client.generate.return_value = (
        "Submit the request through the portal [1]."
    )

    result = run_async(
        answer_question(
            query="Where should I submit it?",
            llm_client=llm_client,
            top_k=5,
            conversation_history=history,
        )
    )

    messages = llm_client.generate.await_args.args[0]

    assert messages[0]["role"] == "system"

    assert messages[1] == history[0]
    assert messages[2] == history[1]

    assert messages[3]["role"] == "user"

    assert "portal [1]" in result["answer"]
    assert len(result["citations"]) == 1
