
from psycopg.types.json import Jsonb

from app.database import get_connection


VALID_ROLES = {"user", "assistant"}


def create_conversation(title: str | None = None) -> dict:
    """
    Create a new conversation.

    Args:
        title: Optional conversation title.

    Returns:
        The newly created conversation.
    """

    if title is not None:
        if not isinstance(title, str):
            raise ValueError("Conversation title must be a string.")

        title = title.strip() or None

    sql = """
        INSERT INTO conversations (title)
        VALUES (%s)
        RETURNING id, title, created_at;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (title,))
            row = cur.fetchone()

    return {
        "id": row[0],
        "title": row[1],
        "created_at": row[2],
    }


def get_conversation(conversation_id: int) -> dict | None:
    """
    Retrieve a conversation by its ID.

    Returns:
        Conversation metadata, or None if it does not exist.
    """

    if isinstance(conversation_id, bool) or not isinstance(
        conversation_id, int
    ):
        raise ValueError("Conversation ID must be an integer.")

    if conversation_id <= 0:
        raise ValueError("Conversation ID must be positive.")

    sql = """
        SELECT id, title, created_at
        FROM conversations
        WHERE id = %s;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (conversation_id,))
            row = cur.fetchone()

    if row is None:
        return None

    return {
        "id": row[0],
        "title": row[1],
        "created_at": row[2],
    }


def save_message(
    conversation_id: int,
    role: str,
    content: str,
    citations: list[dict] | None = None,
) -> dict:
    """
    Save a user or assistant message.

    Args:
        conversation_id: ID of the conversation.
        role: Either 'user' or 'assistant'.
        content: Message text.
        citations: Optional citation metadata.

    Returns:
        The saved message.

    Raises:
        ValueError: If the inputs are invalid or the conversation
                    does not exist.
    """

    if isinstance(conversation_id, bool) or not isinstance(
        conversation_id, int
    ):
        raise ValueError("Conversation ID must be an integer.")

    if conversation_id <= 0:
        raise ValueError("Conversation ID must be positive.")

    if not isinstance(role, str) or role not in VALID_ROLES:
        raise ValueError("Role must be 'user' or 'assistant'.")

    if not isinstance(content, str) or not content.strip():
        raise ValueError("Message content cannot be empty.")

    content = content.strip()

    if citations is not None and not isinstance(citations, list):
        raise ValueError("Citations must be a list or None.")

    sql = """
        INSERT INTO messages (
            conversation_id,
            role,
            content,
            citations
        )
        SELECT %s, %s, %s, %s
        WHERE EXISTS (
            SELECT 1
            FROM conversations
            WHERE id = %s
        )
        RETURNING
            id,
            conversation_id,
            role,
            content,
            citations,
            created_at;
    """

    citations_value = Jsonb(citations) if citations is not None else None

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    conversation_id,
                    role,
                    content,
                    citations_value,
                    conversation_id,
                ),
            )
            row = cur.fetchone()

    if row is None:
        raise ValueError("Conversation does not exist.")

    return {
        "id": row[0],
        "conversation_id": row[1],
        "role": row[2],
        "content": row[3],
        "citations": row[4],
        "created_at": row[5],
    }


def get_conversation_history(
    conversation_id: int,
    limit: int = 50,
) -> list[dict]:
    """
    Retrieve messages from a conversation in chronological order.

    Args:
        conversation_id: ID of the conversation.
        limit: Maximum number of messages to retrieve.

    Returns:
        A list of messages ordered from oldest to newest.
    """

    if isinstance(conversation_id, bool) or not isinstance(
        conversation_id, int
    ):
        raise ValueError("Conversation ID must be an integer.")

    if conversation_id <= 0:
        raise ValueError("Conversation ID must be positive.")

    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ValueError("Limit must be an integer.")

    if not 1 <= limit <= 100:
        raise ValueError("Limit must be between 1 and 100.")

    sql = """
        SELECT
            id,
            conversation_id,
            role,
            content,
            citations,
            created_at
        FROM messages
        WHERE conversation_id = %s
        ORDER BY created_at DESC, id DESC
        LIMIT %s;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (conversation_id, limit))
            rows = cur.fetchall()

    # The SQL retrieves the newest messages first.
    # Reverse them so the conversation is chronological.
    rows.reverse()

    return [
        {
            "id": row[0],
            "conversation_id": row[1],
            "role": row[2],
            "content": row[3],
            "citations": row[4],
            "created_at": row[5],
        }
        for row in rows
    ]
