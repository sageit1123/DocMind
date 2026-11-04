
import asyncio
import os

from dotenv import load_dotenv
from google import genai

load_dotenv()


async def main():
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    print("Checking Gemini models available to this API key...\n")

    async for model in await client.aio.models.list():
        supported = getattr(model, "supported_actions", []) or []

        if "generateContent" in supported:
            print(model.name)


if __name__ == "__main__":
    asyncio.run(main())
