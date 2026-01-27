"""
API Routes for RAG-QA System
"""

import os
import uuid
import time
import aiofiles
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings
from app.models.schemas import (
    DocumentUploadResponse,
    DocumentInfo,
    DocumentStatusResponse,
    QuestionRequest,
    AnswerResponse,
    SourceChunk,
    HealthResponse,
    ProcessingStatus,
    QueryMetrics
)
from app.services.embeddings import EmbeddingService, EmbeddingError
from app.services.vector_store import get_vector_store
from app.services.llm import LLMService, LLMError
from app.background.tasks import process_document, get_document_store
from app.api.dependencies import limiter
from tenacity import RetryError

router = APIRouter()
settings = get_settings()

# Allowed file extensions
ALLOWED_EXTENSIONS = {".pdf", ".txt"}


@router.post("/upload", response_model=DocumentUploadResponse)
@limiter.limit(settings.rate_limit)
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """
    Upload a document for processing
    
    Supported formats: PDF, TXT
    
    The document will be processed in the background. Use the
    /documents/{document_id}/status endpoint to check processing status.
    """
    # Validate file extension
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    
    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: {extension}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Validate file size (configurable limit)
    content = await file.read()
    max_size_bytes = settings.max_file_size_mb * 1024 * 1024
    if len(content) > max_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds {settings.max_file_size_mb}MB limit"
        )
    
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded")
    
    # Generate document ID and save file
    document_id = f"doc_{uuid.uuid4().hex[:12]}"
    
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Save with document_id prefix to avoid conflicts
    safe_filename = f"{document_id}_{file.filename}"
    file_path = upload_dir / safe_filename
    
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)
    
    # Create document record
    store = get_document_store()
    store.create_document(document_id, file.filename, str(file_path))
    
    # Add background processing task
    background_tasks.add_task(process_document, document_id, str(file_path), file.filename)
    
    return DocumentUploadResponse(
        document_id=document_id,
        filename=file.filename,
        status=ProcessingStatus.PENDING,
        message="Document uploaded and queued for processing"
    )


@router.post("/ask", response_model=AnswerResponse)
@limiter.limit(settings.rate_limit)
async def ask_question(request: Request, question_request: QuestionRequest):
    """
    Ask a question about the uploaded documents
    
    The system will:
    1. Embed the question
    2. Search for relevant document chunks
    3. Generate an answer using the retrieved context
    
    Returns the answer along with source citations and performance metrics.
    """
    from datetime import datetime
    
    total_start = time.time()
    
    question = question_request.question.strip()
    top_k = question_request.top_k
    document_ids = question_request.document_ids
    
    vector_store = get_vector_store()
    
    # Check if we have any documents
    if vector_store.get_chunk_count() == 0:
        raise HTTPException(
            status_code=400,
            detail="No documents have been processed yet. Please upload documents first."
        )
    
    try:
        # Step 1: Embed the question
        embed_start = time.time()
        embedding_service = EmbeddingService()
        query_embedding = await embedding_service.embed_query(question)
        embedding_latency_ms = round((time.time() - embed_start) * 1000, 2)
        
        # Step 2: Search for relevant chunks
        retrieval_start = time.time()
        results = vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            document_ids=document_ids,
            similarity_threshold=settings.similarity_threshold
        )
        retrieval_latency_ms = round((time.time() - retrieval_start) * 1000, 2)
        chunks_retrieved = len(results)
        
        # Calculate similarity scores
        avg_similarity_score = 0.0
        max_similarity_score = 0.0
        min_similarity_score = 0.0
        
        if results:
            scores = [score for _, score in results]
            avg_similarity_score = round(sum(scores) / len(scores), 4)
            max_similarity_score = round(max(scores), 4)
            min_similarity_score = round(min(scores), 4)
        
        # Step 3: Generate answer
        generation_start = time.time()
        llm_service = LLMService()
        
        if not results:
            # Retrieval failure case: no relevant chunks found
            answer = llm_service.generate_with_no_context(question)
            generation_latency_ms = 0.0
        else:
            answer, generation_latency = llm_service.generate_answer(question, results)
            generation_latency_ms = round(generation_latency, 2)
        
        # Build source citations
        sources = [
            SourceChunk(
                document_id=chunk_meta.document_id,
                filename=chunk_meta.filename,
                chunk_index=chunk_meta.chunk_index,
                content=chunk_meta.content[:500] + "..." if len(chunk_meta.content) > 500 else chunk_meta.content,
                similarity_score=round(score, 4)
            )
            for chunk_meta, score in results
        ]
        
        total_latency_ms = round((time.time() - total_start) * 1000, 2)
        
        # Create QueryMetrics object
        metrics = QueryMetrics(
            total_latency_ms=total_latency_ms,
            embedding_latency_ms=embedding_latency_ms,
            retrieval_latency_ms=retrieval_latency_ms,
            generation_latency_ms=generation_latency_ms,
            chunks_retrieved=chunks_retrieved,
            avg_similarity_score=avg_similarity_score,
            max_similarity_score=max_similarity_score,
            min_similarity_score=min_similarity_score,
            timestamp=datetime.utcnow().isoformat() + "Z"
        )
        
        return AnswerResponse(
            answer=answer,
            sources=sources,
            metrics=metrics
        )
        
    except RetryError as e:
        # Unwrap the retry error to get the actual cause
        logger.error(f"Processing failed after retries: {e.last_attempt.exception()}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {e.last_attempt.exception()}")
    except EmbeddingError as e:
        raise HTTPException(status_code=500, detail=f"Embedding error: {e}")
    except LLMError as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


@router.get("/documents", response_model=List[DocumentInfo])
@limiter.limit(settings.rate_limit)
async def list_documents(request: Request):
    """
    List all uploaded documents with their processing status
    """
    store = get_document_store()
    documents = store.get_all_documents()
    
    return [
        DocumentInfo(
            document_id=doc["document_id"],
            filename=doc["filename"],
            file_type=doc["file_type"],
            status=ProcessingStatus(doc["status"]),
            chunk_count=doc.get("chunk_count", 0),
            uploaded_at=doc["uploaded_at"],
            processed_at=doc.get("processed_at"),
            error=doc.get("error")
        )
        for doc in documents
    ]


@router.get("/documents/{document_id}/status", response_model=DocumentStatusResponse)
@limiter.limit(settings.rate_limit)
async def get_document_status(request: Request, document_id: str):
    """
    Get the processing status of a specific document
    """
    store = get_document_store()
    doc = store.get_document(document_id)
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    status = ProcessingStatus(doc["status"])
    
    if status == ProcessingStatus.FAILED:
        message = f"Processing failed: {doc.get('error', 'Unknown error')}"
    elif status == ProcessingStatus.COMPLETED:
        message = f"Processing complete. Created {doc.get('chunk_count', 0)} chunks."
    elif status == ProcessingStatus.PROCESSING:
        message = "Document is being processed..."
    else:
        message = "Document is queued for processing"
    
    return DocumentStatusResponse(
        document_id=document_id,
        status=status,
        chunk_count=doc.get("chunk_count", 0),
        message=message
    )


@router.delete("/documents/{document_id}")
@limiter.limit(settings.rate_limit)
async def delete_document(request: Request, document_id: str):
    """
    Delete a document and its embeddings
    """
    store = get_document_store()
    doc = store.get_document(document_id)
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete from vector store
    vector_store = get_vector_store()
    vector_store.delete_document(document_id)
    vector_store.save()
    
    # Delete from document store
    store.delete_document(document_id)
    
    return {"message": f"Document {document_id} deleted successfully"}


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint
    """
    store = get_document_store()
    vector_store = get_vector_store()
    
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        documents_count=len(store.get_all_documents()),
        vector_store_ready=vector_store.is_ready()
    )
