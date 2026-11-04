
import asyncio
import time

from app.llm.gemini import GeminiLLMClient


async def main():
    client = GeminiLLMClient()

    messages = [
        {
            "role": "system",
            "content": "You are a concise technical assistant. "
                       "Answer in approximately 100 words.",
        },
        {
            "role": "user",
            "content": "Explain branch prediction in computer architecture.",
        },
    ]

    print("\n========== STREAMING TEST ==========\n")

    start_time = time.perf_counter()
    first_chunk_time = None
    total_chunks = 0

    try:
        async for chunk in client.stream(messages):
            if first_chunk_time is None:
                first_chunk_time = time.perf_counter()
                print(
                    f"\nFirst chunk received after "
                    f"{first_chunk_time - start_time:.2f} seconds:\n"
                )

            print(chunk, end="", flush=True)
            total_chunks += 1

        end_time = time.perf_counter()

        print("\n\n========== STREAMING METRICS ==========")
        print(f"Total chunks: {total_chunks}")
        print(f"Total time: {end_time - start_time:.2f} seconds")

        if first_chunk_time:
            print(
                f"Time to first chunk: "
                f"{first_chunk_time - start_time:.2f} seconds"
            )

    except Exception as exc:
        print(f"\nStreaming failed: {type(exc).__name__}")
        print(f"Error: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
