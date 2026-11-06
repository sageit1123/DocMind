
from app.database import get_connection


def retrieve_keyword_chunks(
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """
    Retrieve document chunks using PostgreSQL full-text search.

    Uses OR semantics between query terms to improve recall
    for natural-language questions.

    Args:
        query: Natural-language search query.
        top_k: Maximum number of chunks to return (1-50).

    Returns:
        Ranked chunks containing document metadata, text,
        and a keyword relevance score.
    """

    if not query or not query.strip():
        raise ValueError("Search query cannot be empty.")

    if not 1 <= top_k <= 50:
        raise ValueError("top_k must be between 1 and 50.")

    sql = """
        
        WITH parsed_query AS (
            SELECT websearch_to_tsquery(
                'english',
                regexp_replace(%s, '\s+', ' OR ', 'g')
            ) AS tsq
        ),
        ranked_matches AS (
            SELECT
                dc.id AS chunk_id,
                dc.document_id,
                dc.page_number AS page,
                dc.chunk_text AS text,
                d.filename,

                ts_rank_cd(
                    dc.search_vector,
                    parsed_query.tsq
                ) AS keyword_score,

                ROW_NUMBER() OVER (
                    PARTITION BY
                    d.filename,
                    dc.page_number,
                    dc.chunk_text
                ORDER BY
                    dc.document_id DESC,
                    dc.id DESC
            ) AS duplicate_rank

        FROM document_chunks AS dc

        JOIN documents AS d
            ON d.id = dc.document_id

        CROSS JOIN parsed_query

        WHERE
            d.status = 'ready'
            AND dc.search_vector @@ parsed_query.tsq
    )

    SELECT
        chunk_id,
        document_id,
        page,
        text,
        filename,
        keyword_score

    FROM ranked_matches

    WHERE duplicate_rank = 1

    ORDER BY
        keyword_score DESC,
        chunk_id ASC

    LIMIT %s;

    """

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (query, top_k))
            rows = cursor.fetchall()

    return [
        {
            "chunk_id": row[0],
            "document_id": row[1],
            "page": row[2],
            "text": row[3],
            "filename": row[4],
            "keyword_score": float(row[5]),
        }
        for row in rows
    ]
