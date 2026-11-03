
from app.services.conversations import (
    create_conversation,
    get_conversation,
    save_message,
    get_conversation_history,
)


def test_conversation_service_end_to_end():
    # 1. Create a conversation.
    conversation = create_conversation("DocMind Test Conversation")

    assert conversation is not None
    assert conversation["id"] is not None

    conversation_id = conversation["id"]

    # 2. Save a user message.
    user_message = save_message(
        conversation_id=conversation_id,
        role="user",
        content="What is the refund policy?",
    )

    assert user_message is not None
    assert user_message["role"] == "user"
    assert user_message["content"] == "What is the refund policy?"

    # 3. Save an assistant message with citations.
    citations = [
        {
            "number": 1,
            "chunk_id": 12,
            "document_id": 3,
            "filename": "campus_policy.pdf",
            "page": 4,
        }
    ]

    assistant_message = save_message(
        conversation_id=conversation_id,
        role="assistant",
        content="Refunds are available within 15 days [1].",
        citations=citations,
    )

    assert assistant_message is not None
    assert assistant_message["role"] == "assistant"
    assert assistant_message["citations"] == citations

    # 4. Retrieve conversation metadata.
    retrieved_conversation = get_conversation(conversation_id)

    assert retrieved_conversation is not None
    assert retrieved_conversation["id"] == conversation_id

    # 5. Retrieve conversation history.
    history = get_conversation_history(conversation_id)

    assert len(history) == 2

    # 6. Verify chronological order.
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"

    # 7. Verify message content.
    assert history[0]["content"] == "What is the refund policy?"
    assert history[1]["content"] == (
        "Refunds are available within 15 days [1]."
    )

    # 8. Verify citation persistence.
    assert history[1]["citations"] == citations
    assert history[1]["citations"][0]["number"] == 1
