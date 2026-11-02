
from typing import AsyncIterator, Protocol


class LLMClient(Protocol):
    """
    Common interface for all LLM providers.

    Every implementation (OpenAI, Gemini, FakeLLM)
    should provide generate() and stream().
    """

    async def generate(
        self,
        messages: list[dict[str, str]],
    ) -> str:
        """
        Generate a complete response.

        Args:
            messages: List of conversation messages.

        Returns:
            Complete generated response.
        """
        ...

    async def stream(
        self,
        messages: list[dict[str, str]],
    ) -> AsyncIterator[str]:
        """
        Generate a response incrementally.

        Args:
            messages: List of conversation messages.

        Yields:
            Individual text chunks.
        """
        ...
