
import asyncio
from typing import AsyncIterator

from app.llm.base import LLMClient


class FakeLLMClient:
    """
    Fake LLM implementation for testing.

    Returns deterministic responses without calling
    an external LLM provider.
    """

    def __init__(self, response: str | None = None):
        self.response = response or (
            "This is a fake LLM response. "
            "The RAG pipeline successfully called the LLM client."
        )

    async def generate(
        self,
        messages: list[dict[str, str]],
    ) -> str:
        """
        Return a complete fake response.
        """

        # Simulate a small amount of processing time.
        await asyncio.sleep(0.1)

        return self.response

    async def stream(
        self,
        messages: list[dict[str, str]],
    ) -> AsyncIterator[str]:
        """
        Stream the fake response in smaller chunks.
        """

        words = self.response.split(" ")

        for index, word in enumerate(words):
            # Preserve spaces between words.
            chunk = word if index == 0 else " " + word

            yield chunk

            # Simulate incremental generation.
            await asyncio.sleep(0.02)
