
from pathlib import Path

from app.celery_app import celery_app
from app.database import get_connection
from app.services.file_storage import get_pdf_path
from app.services.ingestion import process_pdf


@celery_app.task(
    name="app.tasks.process_document",
    bind=True,
)
def process_document(self, document_id: int):

    # 1. Fetch document metadata.
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT storage_path, status
                FROM documents
                WHERE id = %s;
                """,
                (document_id,),
            )
            document = cur.fetchone()

    if document is None:
        return {
            "document_id": document_id,
            "status": "not_found",
        }

    storage_path, current_status = document

    if current_status == "ready":
        return {
            "document_id": document_id,
            "status": "ready",
            "message": "Document already processed.",
        }

    if current_status not in ("queued", "failed"):
        return {
            "document_id": document_id,
            "status": current_status,
            "message": "Document is already being processed.",
        }

    # 2. Claim the document.
    # Only one worker can successfully change queued/failed to processing.
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE documents
                SET status = 'processing'
                WHERE id = %s
                  AND status IN ('queued', 'failed')
                RETURNING id;
                """,
                (document_id,),
            )

            claimed = cur.fetchone()

    if claimed is None:
        return {
            "document_id": document_id,
            "status": "skipped",
            "message": "Another worker claimed this document.",
        }

    try:
        # 3. Read the PDF from persistent storage.
        if not storage_path:
            raise ValueError("Document has no storage path.")

        pdf_path = get_pdf_path(storage_path)
        contents = pdf_path.read_bytes()

        # 4. Extract text, create chunks and generate embeddings.
        chunks = process_pdf(contents)

        # 5. Replace chunks and mark ready in one transaction.
        with get_connection() as conn:
            with conn.cursor() as cur:

                # Remove old chunks to prevent duplicates on retry.
                cur.execute(
                    """
                    DELETE FROM document_chunks
                    WHERE document_id = %s;
                    """,
                    (document_id,),
                )

                for chunk in chunks:
                    embedding_values = (
                        "["
                        + ",".join(
                            str(float(value))
                            for value in chunk["embedding"]
                        )
                        + "]"
                    )

                    cur.execute(
                        """
                        INSERT INTO document_chunks
                            (document_id, page_number, chunk_text, embedding)
                        VALUES (%s, %s, %s, %s::vector);
                        """,
                        (
                            document_id,
                            chunk["page"],
                            chunk["text"],
                            embedding_values,
                        ),
                    )

                # This update commits together with all chunk inserts.
                cur.execute(
                    """
                    UPDATE documents
                    SET status = 'ready'
                    WHERE id = %s;
                    """,
                    (document_id,),
                )

        return {
            "document_id": document_id,
            "status": "ready",
            "chunk_count": len(chunks),
        }

    except Exception as exc:

        # 6. Mark the document as failed.
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE documents
                        SET status = 'failed'
                        WHERE id = %s
                          AND status = 'processing';
                        """,
                        (document_id,),
                    )
        except Exception:
            # Preserve the original processing error.
            pass

        raise
