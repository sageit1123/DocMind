
from app.prompts.builder import build_prompt


passages = [
    {
        "text": "Students can request a refund within 15 days.",
        "page": 3,
    },
    {
        "text": "Refund requests must be submitted through the student portal.",
        "page": 4,
    },
]

question = "What is the refund policy?"

messages = build_prompt(question, passages)

for message in messages:
    print(f"\nRole: {message['role']}")
    print(message["content"])
