# DocMind

DocMind is a multi-user document intelligence platform that enables users to upload documents and ask questions about their contents. It aims to provide grounded answers with citations to relevant source passages and page references.

## Project Goals

- Support document uploads and background ingestion.
- Retrieve relevant document passages for user questions.
- Generate answers grounded in retrieved evidence.
- Provide citations linking answers to their sources.
- Refuse to answer when the available documents do not support an answer.
- Support multiple users and workspaces with appropriate access controls.
- Evaluate retrieval quality and answer grounding.

## Planned Technology Stack

- **Backend:** FastAPI
- **Database:** PostgreSQL with pgvector
- **Background processing:** Redis and Celery
- **Frontend:** Next.js, TypeScript, and Tailwind CSS
- **Answer delivery:** Server-Sent Events (SSE)
- **Embeddings and language models:** Open-source embeddings and a hosted LLM provider

## Development

This project is being developed incrementally according to the DocMind project guide. Each phase has explicit completion criteria before the next phase begins.
