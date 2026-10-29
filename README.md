# DocMind

DocMind is a multi-user document intelligence platform designed to answer questions using evidence retrieved from uploaded documents. The long-term goal is to provide grounded answers with source citations, page references, and reliable handling of unsupported questions.

**Project status:** Early development — backend foundations, PDF ingestion, vector search, and initial automated tests.

## Current Features

- Upload PDF documents through a FastAPI endpoint.
- Validate PDF extensions, file signatures, and file sizes.
- Extract text from PDFs and split it into chunks.
- Generate text embeddings using `sentence-transformers/all-MiniLM-L6-v2`.
- Store documents, chunks, and embeddings in PostgreSQL with pgvector.
- Retrieve relevant chunks using vector similarity search.
- Validate search request parameters.
- Run automated backend tests with pytest and GitHub Actions.
- Manage database schema revisions with Alembic.

## Planned Features

- Grounded answers with citations and page references.
- Refusal when retrieved evidence does not support an answer.
- Background ingestion using Redis and Celery.
- Multi-user workspaces and access controls.
- Next.js, TypeScript, and Tailwind CSS frontend.
- Streaming responses using Server-Sent Events (SSE).
- Retrieval and answer-quality evaluation.

## Technology Stack

- **Backend:** FastAPI, Python
- **Database:** PostgreSQL, pgvector
- **Database migrations:** Alembic, SQLAlchemy
- **PDF processing:** pypdf
- **Embeddings:** Sentence Transformers
- **Testing:** pytest, FastAPI TestClient
- **CI:** GitHub Actions
- **Planned frontend:** Next.js, TypeScript, Tailwind CSS
- **Planned background processing:** Redis, Celery

## Prerequisites

- Python 3.12 or a compatible Python version
- PostgreSQL with the pgvector extension
- Git
- A database configured for local development

## Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/sageit1123/DocMind.git
cd DocMind
```

### 2. Create and activate a virtual environment

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
```

On Windows, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pytest httpx
```

### 4. Configure environment variables

Create a `backend/.env` file using the `.env.example` template. Set the database host, port, database name, username, and password to match your PostgreSQL setup.

Never commit real credentials to Git.

### 5. Prepare the database

Ensure PostgreSQL is running, the configured database exists, and pgvector is installed and enabled.

Apply database migrations:

```bash
alembic upgrade head
```

For a database that already contains the initial schema, follow the project's existing Alembic baseline setup rather than attempting to recreate its tables.

### 6. Start the backend

From the `backend` directory:

```bash
uvicorn app.main:app --reload
```

The API documentation is available at:

- Swagger UI: `http://127.0.0.1:8000/docs`
- Health endpoint: `http://127.0.0.1:8000/health`

### 7. Run automated tests

From the `backend` directory:

```bash
python -m pytest -v
```

GitHub Actions runs the backend test suite on pushes and pull requests.

## Development Approach

DocMind is developed incrementally. Each phase has explicit completion criteria, with emphasis on correctness, reproducibility, security, and measurable retrieval quality before adding more advanced features.

## License

See [LICENSE](LICENSE).
