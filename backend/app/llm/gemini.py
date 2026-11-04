
import os
import asyncio
import logging
from typing import AsyncIterator

from dotenv import load_dotenv
from google import genai
from google.genai import types


load_dotenv()

logger = logging.getLogger(__name__)


class GeminiLLMClient:
    """
    Gemini implementation of the project's LLMClient interface.

    Supports:
        1. Complete response generation.
        2. Asynchronous token streaming.
        3. Bounded retries for temporary provider errors.

    Streaming policy:
        - Retry temporary errors before the first token.
        - Never restart generation after tokens have been delivered.
        - Do not retry daily quota exhaustion.
    """

    MAX_ATTEMPTS = 3
    RETRY_DELAYS = (2, 4)

    RETRYABLE_STATUS_CODES = {500, 502, 503, 504}

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError("GEMINI_API_KEY is not configured.")

        self.model = os.getenv(
            "GEMINI_MODEL",
            "gemini-3.5-flash-lite",
        )

        self.client = genai.Client(api_key=api_key)
        self.async_client = self.client.aio

    def _prepare_messages(
        self,
        messages: list[dict[str, str]],
    ) -> tuple[str, list[dict]]:
        """
        Convert application messages into Gemini's format.
        """

        system_messages = []
        contents = []

        for message in messages:
            role = message.get("role")
            content = message.get("content")

            if not isinstance(content, str):
                raise ValueError("Message content must be a string.")

            if role == "system":
                system_messages.append(content)

            elif role == "user":
                contents.append({
                    "role": "user",
                    "parts": [{"text": content}],
                })

            elif role == "assistant":
                contents.append({
                    "role": "model",
                    "parts": [{"text": content}],
                })

            else:
                raise ValueError(
                    f"Unsupported message role: {role}"
                )

        if not contents:
            raise ValueError("At least one user message is required.")

        return "\n\n".join(system_messages), contents

    def _get_status_code(self, exc: Exception) -> int | None:
        """
        Extract the HTTP status code from a Gemini SDK exception.
        """

        for attribute in ("code", "status_code"):
            value = getattr(exc, attribute, None)

            if isinstance(value, int):
                return value

        response = getattr(exc, "response", None)
        response_status = getattr(response, "status_code", None)

        if isinstance(response_status, int):
            return response_status

        return None

    def _is_retryable(self, exc: Exception) -> bool:
        """
        Retry temporary server errors only.

        In particular, 429 quota exhaustion is not retried.
        """

        status_code = self._get_status_code(exc)

        return status_code in self.RETRYABLE_STATUS_CODES

    async def _wait_before_retry(self, attempt: int) -> None:
        """
        Wait using bounded exponential backoff.

        Attempt 1 -> 2 seconds
        Attempt 2 -> 4 seconds
        """

        delay = self.RETRY_DELAYS[attempt - 1]

        logger.warning(
            "Gemini request failed temporarily. "
            "Retrying in %s seconds (attempt %s/%s).",
            delay,
            attempt + 1,
            self.MAX_ATTEMPTS,
        )

        await asyncio.sleep(delay)

    def _generation_config(
        self,
        system_instruction: str,
    ) -> types.GenerateContentConfig:
        """
        Build a consistent generation configuration.
        """

        return types.GenerateContentConfig(
            system_instruction=system_instruction or None,
            temperature=0.2,
            max_output_tokens=2048,
        )

    async def generate(
        self,
        messages: list[dict[str, str]],
    ) -> str:
        """
        Generate a complete response with bounded retries.
        """

        system_instruction, contents = self._prepare_messages(messages)
        config = self._generation_config(system_instruction)

        for attempt in range(self.MAX_ATTEMPTS):
            try:
                response = await self.async_client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=config,
                )

                answer = response.text

                if not answer:
                    raise RuntimeError(
                        "Gemini returned an empty response."
                    )

                return answer.strip()

            except Exception as exc:
                should_retry = (
                    self._is_retryable(exc)
                    and attempt < self.MAX_ATTEMPTS - 1
                )

                if not should_retry:
                    raise

                await self._wait_before_retry(attempt)

        raise RuntimeError("Gemini generation failed.")

    async def stream(
        self,
        messages: list[dict[str, str]],
    ) -> AsyncIterator[str]:
        """
        Stream a response with bounded retries.

        A retry is allowed only before the first non-empty
        response chunk has been delivered to the caller.
        """

        system_instruction, contents = self._prepare_messages(messages)
        config = self._generation_config(system_instruction)

        for attempt in range(self.MAX_ATTEMPTS):
            token_sent = False

            try:
                response_stream = (
                    await self.async_client.models.generate_content_stream(
                        model=self.model,
                        contents=contents,
                        config=config,
                    )
                )

                async for chunk in response_stream:
                    text = chunk.text

                    if text:
                        token_sent = True
                        yield text

                return

            except Exception as exc:
                # Once a token has been sent, restarting the
                # generation could duplicate or contradict text.
                if token_sent:
                    logger.exception(
                        "Gemini streaming failed after partial output."
                    )
                    raise

                should_retry = (
                    self._is_retryable(exc)
                    and attempt < self.MAX_ATTEMPTS - 1
                )

                if not should_retry:
                    raise

                logger.warning(
                    "Gemini streaming failed before the first token.",
                    exc_info=True,
                )

                await self._wait_before_retry(attempt)

        raise RuntimeError("Gemini streaming failed.")
