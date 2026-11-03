
from app.database import get_connection
from app.services.embeddings import embedding_model


def retrieve_chunks(query: str, top_k: int = 5) -> list[dict]:
    """
    Retrieve the most relevant document chunks for a user query.

    Args:
        query: User's question or search query.
        top_k: Maximum number of chunks to retrieve (1-10).

    Returns:
        A list of dictionaries containing chunk text and source metadata.
    """

    # 1. Validate the query.
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Query cannot be empty.")

    query = query.strip()

    # 2. Validate top_k.
    if isinstance(top_k, bool) or not isinstance(top_k, int):
        raise ValueError("top_k must be an integer.")

    if not 1 <= top_k <= 10:
        raise ValueError("top_k must be between 1 and 10.")

    # 3. Generate the query embedding using the same model
    # that was used to generate document chunk embeddings.
    query_embedding = embedding_model.encode(
        query,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    # 4. Convert the embedding to pgvector's text representation.
    embedding_values = (
        "[" + ",".join(str(float(value)) for value in query_embedding) + "]"
    )

    # 5. Retrieve the most relevant chunks from ready documents.
    sql = """
        SELECT
            dc.id AS chunk_id,
            dc.document_id,
            dc.page_number,
            dc.chunk_text,
            d.filename,
            1 - (dc.embedding <=> %s::vector) AS similarity
        FROM document_chunks AS dc
        JOIN documents AS d ON d.id = dc.document_id
        WHERE d.status = 'ready'
        ORDER BY dc.embedding <=> %s::vector
        LIMIT %s;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    embedding_values,
                    embedding_values,
                    top_k,
                ),
            )
            rows = cur.fetchall()

    # 6. Convert database rows into structured results.
    results = [
        {
            "chunk_id": chunk_id,
            "document_id": document_id,
            "page": page_number,
            "filename": filename,
            "text": chunk_text,
            "similarity": round(float(similarity), 4),
        }
        for (
            chunk_id,
            document_id,
            page_number,
            chunk_text,
            filename,
            similarity,
        ) in rows
    ]

    return results
