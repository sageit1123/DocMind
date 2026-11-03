import asyncio
import json

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.database import get_connection
from app.services.file_storage import save_pdf, get_pdf_path
from app.tasks.document_tasks import process_document

from app.services.retrieval import retrieve_chunks

from app.llm.fake import FakeLLMClient
from app.services.rag import answer_question, stream_answer_question

from app.services.conversations import (
    create_conversation,
    get_conversation,
    get_conversation_history,
    save_message,
)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=10)

class AskRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=10)
    conversation_id: int | None = Field(default=None, ge=1)

def format_sse_event(data: dict) -> str:
    """
    Convert a Python dictionary into an SSE message.

    SSE messages use the format:
        data: {"type": "token", "content": "Hello"}

    Each message ends with two newline characters.
    """

    json_data = json.dumps(data, ensure_ascii=False)

    return f"data: {json_data}\n\n"



# Temporary storage for the currently uploaded document.
# This is suitable for our single-user local prototype.

app = FastAPI()

llm_client = FakeLLMClient(
    response=(
        "I found relevant information in the retrieved "
        "documents. Please see the supporting passage [1]."
    )
)

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

    try:
        results = retrieve_chunks(
            query=query,
            top_k=request.top_k,
        )

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Failed to search the document database.",
        )

    return {
        "query": query,
        "results": results,
    }

@app.post("/api/ask")
async def ask_document(request: AskRequest):
    """
    Answer a question using RAG and persist the conversation.

    Workflow:
        1. Create a new conversation or retrieve an existing one.
        2. Load previous conversation history.
        3. Save the current user question.
        4. Execute the RAG pipeline with previous history.
        5. Save the assistant answer and citations.
        6. Return the conversation ID and answer.
    """

    query = request.query.strip()

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty.",
        )

    try:
        # Step 1: Create or retrieve the conversation.
        if request.conversation_id is None:
            conversation = create_conversation(
                title=query[:80]
            )

        else:
            conversation = get_conversation(
                request.conversation_id
            )

            if conversation is None:
                raise HTTPException(
                    status_code=404,
                    detail="Conversation not found.",
                )

        conversation_id = conversation["id"]

        # Step 2: Load previous messages BEFORE saving
        # the current question.
        history = get_conversation_history(
            conversation_id=conversation_id,
            limit=50,
        )

        # Step 3: Persist the current user question.
        save_message(
            conversation_id=conversation_id,
            role="user",
            content=query,
        )

        # Step 4: Run the RAG pipeline with conversation history.
        result = await answer_question(
            query=query,
            llm_client=llm_client,
            top_k=request.top_k,
            conversation_history=history,
        )

        # Step 5: Persist the assistant response and citations.
        save_message(
            conversation_id=conversation_id,
            role="assistant",
            content=result["answer"],
            citations=result["citations"],
        )

        # Step 6: Return the conversation ID with the RAG result.
        return {
            "conversation_id": conversation_id,
            **result,
        }

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        # Keep internal database/model errors out of the API response.
        print(f"Error in /api/ask: {exc}")

        raise HTTPException(
            status_code=500,
            detail="Failed to generate an answer.",
        ) from exc



@app.post("/api/ask/stream")
async def ask_document_stream(request: AskRequest):
    """
    Stream a RAG answer using Server-Sent Events.

    Workflow:
        1. Create or retrieve a conversation.
        2. Load previous conversation history.
        3. Save the current user question.
        4. Stream tokens from the RAG service.
        5. Save the complete assistant response and citations.
        6. Send the final completion event.
    """

    query = request.query.strip()

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty.",
        )

    try:
        # Step 1: Create or retrieve the conversation.
        if request.conversation_id is None:
            conversation = await asyncio.to_thread(
                create_conversation,
                title=query[:80],
            )
        else:
            conversation = await asyncio.to_thread(
                get_conversation,
                request.conversation_id,
            )

            if conversation is None:
                raise HTTPException(
                    status_code=404,
                    detail="Conversation not found.",
                )

        conversation_id = conversation["id"]

        # Step 2: Load previous history BEFORE saving
        # the current question.
        history = await asyncio.to_thread(
            get_conversation_history,
            conversation_id=conversation_id,
            limit=50,
        )

        # Step 3: Save the user's question.
        await asyncio.to_thread(
            save_message,
            conversation_id=conversation_id,
            role="user",
            content=query,
        )

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        print(f"Error preparing streaming request: {exc}")

        raise HTTPException(
            status_code=500,
            detail="Failed to prepare the streaming request.",
        ) from exc

    # Step 4: Stream the RAG response.
    async def generate_events():
        completed = False

        try:
            async for event in stream_answer_question(
                query=query,
                llm_client=llm_client,
                top_k=request.top_k,
                conversation_history=history,
            ):

                # Send incremental text to the client.
                if event["type"] == "token":
                    yield format_sse_event({
                        "type": "token",
                        "content": event["content"],
                    })

                # The RAG service has finished generating
                # and validating the complete answer.
                elif event["type"] == "complete":

                    # Step 5: Persist the complete assistant response.
                    await asyncio.to_thread(
                        save_message,
                        conversation_id=conversation_id,
                        role="assistant",
                        content=event["answer"],
                        citations=event["citations"],
                    )

                    completed = True

                    # Step 6: Send final metadata.
                    yield format_sse_event({
                        "type": "complete",
                        "conversation_id": conversation_id,
                        "answer": event["answer"],
                        "citations": event["citations"],
                        "sources": event["sources"],
                    })

            if not completed:
                yield format_sse_event({
                    "type": "error",
                    "message": "The response did not complete.",
                })

        except asyncio.CancelledError:
            # The client disconnected or cancelled the request.
            # Do not save an incomplete assistant response.
            raise

        except Exception as exc:
            print(f"Error during streaming: {exc}")

            yield format_sse_event({
                "type": "error",
                "message": "Failed to generate the response.",
            })

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


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


