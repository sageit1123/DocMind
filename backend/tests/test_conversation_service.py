
from app.services.conversations import (
    create_conversation,
    get_conversation,
    save_message,
    get_conversation_history,
)


# 1. Create a conversation.
conversation = create_conversation("DocMind Test Conversation")
conversation_id = conversation["id"]

print("Created conversation:", conversation)


# 2. Save a user message.
user_message = save_message(
    conversation_id=conversation_id,
    role="user",
    content="What is the refund policy?",
)

print("\nSaved user message:", user_message)


# 3. Save an assistant message with citations.
assistant_message = save_message(
    conversation_id=conversation_id,
    role="assistant",
    content="Refunds are available within 15 days [1].",
    citations=[
        {
            "number": 1,
            "chunk_id": 12,
            "document_id": 3,
            "filename": "campus_policy.pdf",
            "page": 4,
        }
    ],
)

print("\nSaved assistant message:", assistant_message)


# 4. Retrieve conversation metadata.
retrieved_conversation = get_conversation(conversation_id)

print("\nRetrieved conversation:", retrieved_conversation)


# 5. Retrieve conversation history.
history = get_conversation_history(conversation_id)

print("\nConversation history:")

for message in history:
    print(message["role"], ":", message["content"])
    print("Citations:", message["citations"])


# 6. Verify chronological order.
assert history[0]["role"] == "user"
assert history[1]["role"] == "assistant"

# 7. Verify citation persistence.
assert history[1]["citations"][0]["number"] == 1

print("\nAll conversation service checks passed!")
