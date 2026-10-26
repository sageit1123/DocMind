import re
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from fastapi import UploadFile, File, HTTPException
from pypdf import PdfReader
from io import BytesIO
from sentence_transformers import SentenceTransformer

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=3, ge=1, le=10)

# Load the embedding model once, not once per request.
embedding_model = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2"
)

CHUNK_SIZE = 500
CHUNK_OVERLAP = 100


def create_chunks(text: str, page_number: int) -> list[dict]:
    """Create focused, sentence-aware chunks from one PDF page."""

    paragraphs = [
        " ".join(paragraph.split())
        for paragraph in re.split(r"\n\s*\n", text)
        if paragraph.strip()
    ]

    # Split paragraphs into sentences while keeping punctuation.
    sentences = []

    for paragraph in paragraphs:
        parts = re.split(r"(?<=[.!?])\s+", paragraph.strip())
        sentences.extend(part.strip() for part in parts if part.strip())

    chunks = []
    current_sentences = []
    current_length = 0

    for sentence in sentences:
        # A very long sentence must be split to respect the chunk limit.
        if len(sentence) > CHUNK_SIZE:
            if current_sentences:
                chunks.append({
                    "page": page_number,
                    "text": " ".join(current_sentences),
                })
                current_sentences = []
                current_length = 0

            for start in range(0, len(sentence), CHUNK_SIZE - CHUNK_OVERLAP):
                piece = sentence[start:start + CHUNK_SIZE].strip()
                if piece:
                    chunks.append({
                        "page": page_number,
                        "text": piece,
                    })
            continue

        extra_length = len(sentence) + (1 if current_sentences else 0)

        if current_length + extra_length > CHUNK_SIZE and current_sentences:
            chunks.append({
                "page": page_number,
                "text": " ".join(current_sentences),
            })

            # Retain a small sentence-level overlap for context.
            overlap_sentences = []
            overlap_length = 0

            for previous in reversed(current_sentences):
                if overlap_length + len(previous) > CHUNK_OVERLAP:
                    break
                overlap_sentences.insert(0, previous)
                overlap_length += len(previous)

            current_sentences = overlap_sentences
            current_length = sum(len(item) for item in current_sentences)

        current_sentences.append(sentence)
        current_length += len(sentence)

    if current_sentences:
        chunks.append({
            "page": page_number,
            "text": " ".join(current_sentences),
        })

    return chunks

# Temporary storage for the currently uploaded document.
# This is suitable for our single-user local prototype.
document_chunks = []

app = FastAPI()

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
    # 1. Check that a filename exists
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No file selected.",
        )

    # 2. Check the file extension
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed.",
        )

    # 3. Check the PDF signature
    header = await file.read(5)

    if header != b"%PDF-":
        raise HTTPException(
            status_code=400,
            detail="The uploaded file does not appear to be a valid PDF.",
        )

    # 4. Count the file size in chunks
    total_size = len(header)

    while True:
        chunk = await file.read(1024 * 1024)  # Read 1 MB at a time

        if not chunk:
            break

        total_size += len(chunk)

        if total_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail="File is too large. Maximum size is 10 MB.",
            )

    
    # Extract text from the uploaded PDF
    await file.seek(0)
    contents = await file.read()

    try:
        pdf = PdfReader(BytesIO(contents))

        new_chunks = []

        for page_number, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""

            page_chunks = create_chunks(
                page_text,
                page_number,
            )

            new_chunks.extend(page_chunks)

        if not new_chunks:
            raise HTTPException(
                status_code=400,
                detail="No extractable text found in this PDF.",
            )

        # Generate an embedding for every chunk in one batch.
        embeddings = embedding_model.encode(
            [chunk["text"] for chunk in new_chunks],
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        # Attach each vector to its corresponding chunk.
        for chunk, embedding in zip(new_chunks, embeddings):
            chunk["embedding"] = embedding

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Could not read or process this PDF.",
        )

    # Replace the active document only after successful processing.
    global document_chunks
    document_chunks = new_chunks

    return {
        "message": "PDF processed successfully for semantic search!",
        "filename": file.filename,
        "page_count": len(pdf.pages),
        "chunk_count": len(document_chunks),
    }

@app.post("/api/search")
def search_document(request: SearchRequest):
    query = request.query.strip()

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty.",
        )

    if not document_chunks:
        raise HTTPException(
            status_code=400,
            detail="Please upload a PDF before asking a question.",
        )

    # Embed the question using the same model as the document.
    query_embedding = embedding_model.encode(
        query,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    # Normalized vectors allow dot product to represent cosine similarity.
    scores = embedding_model.similarity(
        query_embedding,
        [chunk["embedding"] for chunk in document_chunks],
    )[0]

    ranked_indices = scores.argsort(descending=True)
    results = []

    for index in ranked_indices[:request.top_k]:
        chunk = document_chunks[int(index)]

        results.append({
            "page": chunk["page"],
            "text": chunk["text"],
            "similarity": round(float(scores[index]), 4),
        })

    return {
        "query": query,
        "results": results,
    }



