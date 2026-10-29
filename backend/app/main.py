from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.database import get_connection
from app.services.embeddings import embedding_model
from app.services.ingestion import process_pdf

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=3, ge=1, le=10)



# Temporary storage for the currently uploaded document.
# This is suitable for our single-user local prototype.

app = FastAPI()

@app.get("/health")
def health_check():
    return {"status": "ok"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "http://localhost:5173",
    "http://127.0.0.1:5173"
                            ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class MessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


@app.get("/")
def home():
    return {"message": "Welcome to DocMind!"}

@app.get("/api/message")
def get_message():
    return {"message": "Hello from the DocMind backend!"}

@app.post("/api/message")
def send_message(request: MessageRequest):
    message = request.message.strip()

    if not message:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail="Message cannot be empty."
        )

    return {"reply": f"You said: {message}"}


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected.")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed.",
        )

    # Validate PDF signature.
    header = await file.read(5)

    if header != b"%PDF-":
        raise HTTPException(
            status_code=400,
            detail="The uploaded file does not appear to be a valid PDF.",
        )

    # Enforce the 10 MB size limit.
    total_size = len(header)

    while True:
        chunk = await file.read(1024 * 1024)

        if not chunk:
            break

        total_size += len(chunk)

        if total_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail="File is too large. Maximum size is 10 MB.",
            )

    # Process the PDF using the ingestion service.
    await file.seek(0)
    contents = await file.read()
    new_chunks = process_pdf(contents)

    # Save the document and chunks in one transaction.
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO documents (filename)
                    VALUES (%s)
                    RETURNING id;
                    """,
                    (file.filename,),
                )

                document_id = cur.fetchone()[0]

                for chunk in new_chunks:
                    embedding_values = (
                        "[" + ",".join(
                            str(float(value))
                            for value in chunk["embedding"]
                        ) + "]"
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

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Failed to save the processed PDF to the database.",
        ) from exc

    return {
        "message": "PDF processed successfully for semantic search!",
        "filename": file.filename,
        "document_id": document_id,
        "chunk_count": len(new_chunks),
    }



@app.post("/api/search")
def search_document(request: SearchRequest):
    query = request.query.strip()

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty.",
        )

    # Generate the query embedding using the same model as uploaded chunks.
    query_embedding = embedding_model.encode(
        query,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    # Convert the embedding to pgvector's text representation.
    embedding_values = (
        "[" + ",".join(str(float(value)) for value in query_embedding) + "]"
    )

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Find the most relevant chunks using cosine distance.
                cur.execute(
                    """
                    SELECT
                        page_number,
                        chunk_text,
                        1 - (embedding <=> %s::vector) AS similarity
                    FROM document_chunks
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s;
                    """,
                    (
                        embedding_values,
                        embedding_values,
                        request.top_k,
                    ),
                )

                rows = cur.fetchall()

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Failed to search the document database.",
        )

    if not rows:
        raise HTTPException(
            status_code=400,
            detail="Please upload a PDF before asking a question.",
        )

    results = [
        {
            "page": page_number,
            "text": chunk_text,
            "similarity": round(float(similarity), 4),
        }
        for page_number, chunk_text, similarity in rows
    ]

    return {
        "query": query,
        "results": results,
    }




