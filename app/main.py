"""
RAG-QA System - FastAPI Application Entry Point
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.routes import router
from app.api.dependencies import limiter
from app.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    logger.info("Starting RAG-QA System...")
    settings = get_settings()
    logger.info(f"Chunk size: {settings.chunk_size}, Overlap: {settings.chunk_overlap}")
    logger.info(f"Rate limit: {settings.rate_limit}")
    yield
    logger.info("Shutting down RAG-QA System...")


# Create FastAPI application
app = FastAPI(
    title="RAG-QA System",
    description="""
A Retrieval-Augmented Generation (RAG) based Question Answering API.

## Features

- **Document Upload**: Upload PDF and TXT documents for processing
- **Background Processing**: Documents are processed asynchronously
- **Semantic Search**: Find relevant document chunks using embeddings
- **AI-Powered Answers**: Generate answers using Google Gemini LLM
- **Source Citations**: All answers include source references
- **Rate Limiting**: Built-in API rate limiting

## Usage

1. Upload a document using `/upload`
2. Check processing status using `/documents/{id}/status`
3. Ask questions using `/ask`
    """,
    version="1.0.0",
    lifespan=lifespan
)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api/v1", tags=["RAG-QA"])


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "RAG-QA System",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health"
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again later."}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
