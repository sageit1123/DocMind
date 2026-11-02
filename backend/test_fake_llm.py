import asyncio

from app.llm.fake import FakeLLMClient


async def main():
    client = FakeLLMClient()

    messages = [
        {"role": "system", "content": "Answer using context."},
        {"role": "user", "content": "What is RAG?"},
    ]

    # Test complete response
    answer = await client.generate(messages)
    print("Complete response:", answer)

    # Test streaming response
    print("\nStreaming response:")

    async for chunk in client.stream(messages):
        print(chunk, end="", flush=True)

    print()


if __name__ == "__main__":
    asyncio.run(main())