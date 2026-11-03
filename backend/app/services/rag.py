
import asyncio
import re
from typing import AsyncIterator

from app.llm.base import LLMClient
from app.prompts.builder import build_prompt
from app.services.retrieval import retrieve_chunks


REFUSAL_MESSAGE = (
    "I could not find this information in the available documents."
)

VALID_ROLES = {"user", "assistant"}


def _filter_valid_passages(passages: list[dict]) -> list[dict]:
    """Keep passages containing non-empty text."""

    return [
        passage
        for passage in passages
        if isinstance(passage.get("text"), str)
        and passage["text"].strip()
    ]


def _filter_valid_history(
    history: list[dict] | None,
) -> list[dict[str, str]]:
    """
    Keep valid user and assistant messages.

    Conversation history provides context, not factual evidence.
    Retrieved passages remain the source of factual evidence.
    """

    if not history:
        return []

    valid_history = []

    for message in history:
        if not isinstance(message, dict):
            continue

        role = message.get("role")
        content = message.get("content")

        if not isinstance(role, str) or role not in VALID_ROLES:
            continue

        if not isinstance(content, str) or not content.strip():
            continue

        valid_history.append({
            "role": role,
            "content": content.strip(),
        })

    return valid_history


def _build_messages(
    query: str,
    passages: list[dict],
    conversation_history: list[dict] | None = None,
) -> list[dict[str, str]]:
    """Build the LLM messages using retrieved evidence and history."""

    messages = build_prompt(
        question=query,
        passages=passages,
    )

    if len(messages) != 2:
        raise ValueError(
            "Prompt builder must return exactly two messages: "
            "system and user."
        )

    valid_history = _filter_valid_history(conversation_history)

    return [
        messages[0],
        *valid_history,
        messages[1],
    ]


def _build_citations(
    answer: str,
    passages: list[dict],
) -> tuple[str, list[dict], list[dict]]:
    """Validate citation references and map them to retrieved passages."""

    citation_map = {
        index: passage
        for index, passage in enumerate(passages, start=1)
    }

    seen_citations = set()
    citations = []
    sources = []
    seen_sources = set()

    def replace_citation(match):
        citation_number = int(match.group(1))

        if citation_number not in citation_map:
            return ""

        if citation_number not in seen_citations:
            seen_citations.add(citation_number)

            passage = citation_map[citation_number]

            citations.append({
                "number": citation_number,
                "chunk_id": passage.get("chunk_id"),
                "document_id": passage.get("document_id"),
                "filename": passage.get("filename"),
                "page": passage.get("page"),
            })

            source_key = (
                passage.get("chunk_id"),
                passage.get("document_id"),
                passage.get("page"),
            )

            if source_key not in seen_sources:
                seen_sources.add(source_key)

                sources.append({
                    "chunk_id": passage.get("chunk_id"),
                    "document_id": passage.get("document_id"),
                    "filename": passage.get("filename"),
                    "page": passage.get("page"),
                    "text": passage["text"].strip(),
                })

        return match.group(0)

    cleaned_answer = re.sub(
        r"\[(\d+)\]",
        replace_citation,
        answer,
    )

    return cleaned_answer.strip(), citations, sources


async def answer_question(
    query: str,
    llm_client: LLMClient,
    top_k: int = 5,
    conversation_history: list[dict] | None = None,
) -> dict:
    """
    Execute the non-streaming retrieve-then-generate RAG pipeline.
    """

    if not isinstance(query, str) or not query.strip():
        raise ValueError("Question cannot be empty.")

    query = query.strip()

    passages = await asyncio.to_thread(
        retrieve_chunks,
        query=query,
        top_k=top_k,
    )

    valid_passages = _filter_valid_passages(passages)

    if not valid_passages:
        return {
            "answer": REFUSAL_MESSAGE,
            "citations": [],
            "sources": [],
        }

    messages = _build_messages(
        query=query,
        passages=valid_passages,
        conversation_history=conversation_history,
    )

    answer = await llm_client.generate(messages)

    if not isinstance(answer, str):
        raise TypeError("LLM client must return a string.")

    cleaned_answer, citations, sources = _build_citations(
        answer,
        valid_passages,
    )

    return {
        "answer": cleaned_answer,
        "citations": citations,
        "sources": sources,
    }


async def stream_answer_question(
    query: str,
    llm_client: LLMClient,
    top_k: int = 5,
    conversation_history: list[dict] | None = None,
) -> AsyncIterator[dict]:
    """
    Execute the streaming retrieve-then-generate RAG pipeline.

    Yields:
        token event:
            {"type": "token", "content": "..."}

        complete event:
            {
                "type": "complete",
                "answer": "...",
                "citations": [...],
                "sources": [...]
            }
    """

    if not isinstance(query, str) or not query.strip():
        raise ValueError("Question cannot be empty.")

    query = query.strip()

    # Retrieval and embedding are synchronous operations.
    # Run them in a worker thread to avoid blocking the event loop.
    passages = await asyncio.to_thread(
        retrieve_chunks,
        query=query,
        top_k=top_k,
    )

    valid_passages = _filter_valid_passages(passages)

    # Refuse without calling the LLM when there is no evidence.
    if not valid_passages:
        yield {
            "type": "token",
            "content": REFUSAL_MESSAGE,
        }

        yield {
            "type": "complete",
            "answer": REFUSAL_MESSAGE,
            "citations": [],
            "sources": [],
        }
        return

    messages = _build_messages(
        query=query,
        passages=valid_passages,
        conversation_history=conversation_history,
    )

    # Collect all generated chunks so we can validate citations
    # and persist the complete answer after generation finishes.
    answer_parts = []

    async for chunk in llm_client.stream(messages):

        if not isinstance(chunk, str):
            raise TypeError(
                "LLM stream must yield strings."
            )

        if not chunk:
            continue

        answer_parts.append(chunk)

        yield {
            "type": "token",
            "content": chunk,
        }

    complete_answer = "".join(answer_parts)

    cleaned_answer, citations, sources = _build_citations(
        complete_answer,
        valid_passages,
    )

    # This event is emitted only after the entire response
    # has been generated and its citations have been validated.
    yield {
        "type": "complete",
        "answer": cleaned_answer,
        "citations": citations,
        "sources": sources,
    }
