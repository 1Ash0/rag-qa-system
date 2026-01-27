# RAG-QA System

A Retrieval-Augmented Generation (RAG) based Question Answering API built with FastAPI, FAISS, and Google Gemini.

## Features

- **Document Upload**: Support for PDF and TXT file formats
- **Intelligent Chunking**: Configurable text chunking with overlap for context preservation
- **Vector Search**: FAISS-based similarity search for relevant context retrieval
- **AI Answers**: Google Gemini-powered answer generation with source citations
- **Background Processing**: Async document ingestion pipeline
- **Rate Limiting**: Built-in API request throttling
- **Metrics Tracking**: Latency and quality metrics for every query

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FastAPI Server                          │
├─────────────────────────────────────────────────────────────────┤
│  /upload              │  /ask                │  /documents       │
│  Document Upload      │  Question Answering  │  Status & List    │
└───────┬───────────────┴──────────┬───────────┴──────────────────┘
        │                          │
        ▼                          ▼
┌───────────────────┐    ┌─────────────────────────────────────┐
│ Background Tasks  │    │           Query Pipeline             │
│ ┌───────────────┐ │    │  ┌───────────┐    ┌──────────────┐  │
│ │ Parse Doc     │ │    │  │ Embed     │───▶│ FAISS Search │  │
│ │ (PDF/TXT)     │ │    │  │ Query     │    └──────┬───────┘  │
│ └───────┬───────┘ │    │  └───────────┘           │          │
│         ▼         │    │                          ▼          │
│ ┌───────────────┐ │    │                 ┌──────────────┐    │
│ │ Chunk Text    │ │    │                 │ Build Context│    │
│ │ (512 chars)   │ │    │                 └──────┬───────┘    │
│ └───────┬───────┘ │    │                        │            │
│         ▼         │    │                        ▼            │
│ ┌───────────────┐ │    │                ┌───────────────┐    │
│ │ Generate      │ │    │                │ Gemini LLM    │    │
│ │ Embeddings    │ │    │                │ Generate      │    │
│ └───────┬───────┘ │    │                │ Answer        │    │
│         ▼         │    │                └───────────────┘    │
│ ┌───────────────┐ │    └─────────────────────────────────────┘
│ │ Store in      │ │
│ │ FAISS         │ │
│ └───────────────┘ │
└───────────────────┘
```

## Quick Start

### 1. Clone and Setup

```bash
cd C:\Users\ASMIT\.gemini\antigravity\scratch\rag-qa-system

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy environment template
copy .env.example .env

# Edit .env and add your Gemini API key
# GEMINI_API_KEY=your_key_here
```

### 3. Run the Server

```bash
uvicorn app.main:app --reload
```

### 4. Access the API

- **Swagger UI**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/v1/health

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/upload` | POST | Upload a PDF or TXT document |
| `/api/v1/ask` | POST | Ask a question about documents |
| `/api/v1/documents` | GET | List all uploaded documents |
| `/api/v1/documents/{id}/status` | GET | Check document processing status |
| `/api/v1/documents/{id}` | DELETE | Delete a document |
| `/api/v1/health` | GET | Health check |

## Usage Examples

### Upload a Document

```bash
curl -X POST "http://localhost:8000/api/v1/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@sample.pdf"
```

**Response**:
```json
{
  "document_id": "doc_abc123def456",
  "filename": "sample.pdf",
  "status": "pending",
  "message": "Document uploaded and queued for processing"
}
```

### Ask a Question

```bash
curl -X POST "http://localhost:8000/api/v1/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the main findings?",
    "top_k": 5
  }'
```

**Response**:
```json
{
  "answer": "The main findings indicate...",
  "sources": [
    {
      "document_id": "doc_abc123def456",
      "filename": "sample.pdf",
      "chunk_index": 3,
      "content": "The study found that...",
      "similarity_score": 0.89
    }
  ],
  "metrics": {
    "total_latency_ms": 1523.45,
    "chunks_retrieved": 5,
    "avg_similarity_score": 0.72
  }
}
```

## Configuration

Environment variables (set in `.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | (required) | Google Gemini API key |
| `CHUNK_SIZE` | 512 | Characters per chunk |
| `CHUNK_OVERLAP` | 50 | Overlap between chunks |
| `RATE_LIMIT` | 10/minute | API rate limit |
| `LLM_MODEL` | gemini-1.5-flash | Gemini model for answers |

## Project Structure

```
rag-qa-system/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Configuration
│   ├── models/
│   │   └── schemas.py       # Pydantic models
│   ├── services/
│   │   ├── document_parser.py   # PDF/TXT parsing
│   │   ├── chunker.py           # Text chunking
│   │   ├── embeddings.py        # Gemini embeddings
│   │   ├── vector_store.py      # FAISS operations
│   │   └── llm.py               # Answer generation
│   ├── api/
│   │   ├── routes.py            # API endpoints
│   │   └── dependencies.py      # Rate limiting
│   └── background/
│       └── tasks.py             # Document processing
├── data/
│   ├── uploads/                 # Uploaded files
│   └── vector_store/            # FAISS index
├── docs/
│   └── design_decisions.md      # Design rationale
├── requirements.txt
├── .env.example
└── README.md
```

## Design Decisions

See [docs/design_decisions.md](docs/design_decisions.md) for detailed explanations of:

- **Chunk Size Choice**: Why 512 characters with 50 character overlap
- **Retrieval Failure Cases**: Observed edge cases and mitigations
- **Metrics Tracked**: Latency and quality metrics

## Testing

```bash
# Run tests
python -m pytest tests/ -v

# With coverage
python -m pytest tests/ -v --cov=app
```

## Rate Limiting

The API enforces a rate limit of 10 requests per minute per IP address. Exceeding this limit returns a `429 Too Many Requests` response.

## License

MIT
