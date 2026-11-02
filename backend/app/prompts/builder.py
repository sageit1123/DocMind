
from pathlib import Path


PROMPT_DIR = Path(__file__).resolve().parent
SYSTEM_PROMPT_PATH = PROMPT_DIR / "system.txt"


def load_system_prompt() -> str:
    """
    Load the system instruction from system.txt.

    Returns:
        The system prompt as a string.
    """

    if not SYSTEM_PROMPT_PATH.is_file():
        raise FileNotFoundError(
            f"System prompt not found: {SYSTEM_PROMPT_PATH}"
        )

    prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()

    if not prompt:
        raise ValueError("System prompt cannot be empty.")

    return prompt


def build_prompt(
    question: str,
    passages: list[dict],
) -> list[dict[str, str]]:
    """
    Construct the messages for the LLM.

    Args:
        question:
            The user's question.

        passages:
            Retrieved passages. Each passage should contain:
            {
                "text": "Document passage text",
                "page": 3
            }

    Returns:
        A list of messages containing system and user instructions.
    """

    question = question.strip()

    if not question:
        raise ValueError("Question cannot be empty.")

    if not passages:
        raise ValueError("At least one passage is required.")

    system_prompt = load_system_prompt()

    valid_passages = [
    passage
    for passage in passages
    if isinstance(passage.get("text"), str)
    and passage["text"].strip()
    ]

    if not valid_passages:
        raise ValueError("No valid passages were provided.")

    formatted_passages = []

    for index, passage in enumerate(valid_passages, start=1):
        text = passage["text"].strip()
        page = passage.get("page")

        formatted_passages.append(
            f"[{index}] Page: {page}\n{text}"
        )

    context = "\n\n".join(formatted_passages)

    user_prompt = f"""
Use the following retrieved document passages to answer the question.

<retrieved_context>
{context}
</retrieved_context>

<user_question>
{question}
</user_question>

Remember to follow the system instructions and cite supporting
passages using their assigned numbers.
""".strip()

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]

    return messages
