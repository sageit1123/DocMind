from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.database import get_connection
from app.services.embeddings import embedding_model
from app.services.file_storage import save_pdf, get_pdf_path
from app.tasks.document_tasks import process_document

from app.database import get_connection

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
        raise HTTPException(
            status_code=400,
            detail="No file selected.",
        )

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed.",
        )

    # Read and validate the PDF.
    header = await file.read(5)

    if header != b"%PDF-":
        raise HTTPException(
            status_code=400,
            detail="The uploaded file does not appear to be a valid PDF.",
        )

    contents = bytearray(header)

    while True:
        chunk = await file.read(1024 * 1024)

        if not chunk:
            break

        contents.extend(chunk)

        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail="File is too large. Maximum size is 10 MB.",
            )

    storage_path = None

    try:
        # Save the PDF to persistent local storage.
        storage_path = save_pdf(bytes(contents))

        # Create the document record.
        # PostgreSQL assigns status='queued' through its server default.
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO documents (filename, storage_path)
                    VALUES (%s, %s)
                    RETURNING id, status;
                    """,
                    (file.filename, storage_path),
                )

                document_id, status = cur.fetchone()

    except Exception as exc:
        # Remove the saved PDF if database insertion fails.
        if storage_path is not None:
            try:
                get_pdf_path(storage_path).unlink()
            except Exception:
                pass

        raise HTTPException(
            status_code=500,
            detail="Failed to save the uploaded document.",
        ) from exc

        # Enqueue background processing only after the database commit.
    try:
        process_document.delay(document_id)

    except Exception as exc:
        # The PDF and database record exist, but the task
        # could not be submitted to Redis.
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE documents
                        SET status = 'failed'
                        WHERE id = %s AND status = 'queued';
                        """,
                        (document_id,),
                    )
        except Exception:
            pass

        raise HTTPException(
            status_code=503,
            detail="PDF uploaded, but background processing could not be scheduled.",
        ) from exc

    return {
        "message": "PDF uploaded successfully.",
        "filename": file.filename,
        "document_id": document_id,
        "status": status,
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

@app.get("/api/documents/{document_id}/status")
def get_document_status(document_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, filename, status
                FROM documents
                WHERE id = %s;
                """,
                (document_id,)
            )

            document = cur.fetchone()

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found."
        )

    return {
        "document_id": document[0],
        "filename": document[1],
        "status": document[2]
    }

@app.delete("/api/documents/{document_id}")
def delete_document(document_id: int):

    # Step 1: Check the current document status
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT status
                FROM documents
                WHERE id = %s;
                """,
                (document_id,)
            )
            document = cur.fetchone()

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found."
        )

    if document[0] == "processing":
        raise HTTPException(
            status_code=409,
            detail="Cannot delete a document while it is processing."
        )

    # Step 2: Atomically delete the document if it is not processing
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM documents
                WHERE id = %s AND status != 'processing'
                RETURNING storage_path;
                """,
                (document_id,)
            )
            deleted_document = cur.fetchone()

    if deleted_document is None:
        raise HTTPException(
            status_code=409,
            detail="Document is currently being processed. Try again later."
        )

    storage_path = deleted_document[0]

    # Step 3: Delete the physical PDF
    if storage_path:
        try:
            pdf_path = get_pdf_path(storage_path)
            pdf_path.unlink(missing_ok=True)

        except (ValueError, OSError, FileNotFoundError) as exc:
            # Database deletion has already succeeded.
            # Log this error so orphaned files can be investigated.
            print(
                f"Could not delete PDF for document {document_id}: {exc}"
            )

    # Step 4: Return response
    return {
        "message": "Document deleted successfully.",
        "document_id": document_id
    }


