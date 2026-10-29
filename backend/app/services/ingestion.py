
from io import BytesIO

from fastapi import HTTPException
from pypdf import PdfReader

from app.services.chunking import create_chunks
from app.services.embeddings import embedding_model


def process_pdf(contents: bytes) -> list[dict]:
    """Extract PDF text, chunk it, and generate embeddings."""

    try:
        pdf = PdfReader(BytesIO(contents))
        chunks = []

        for page_number, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            chunks.extend(create_chunks(page_text, page_number))

        if not chunks:
            raise HTTPException(
                status_code=400,
                detail="No extractable text found in this PDF.",
            )

        embeddings = embedding_model.encode(
            [chunk["text"] for chunk in chunks],
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        for chunk, embedding in zip(chunks, embeddings):
            chunk["embedding"] = embedding.tolist()

        return chunks

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="Could not read or process this PDF.",
        ) from exc
