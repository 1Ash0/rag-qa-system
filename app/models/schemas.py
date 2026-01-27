"""
Pydantic schemas for request/response validation
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime


class ProcessingStatus(str, Enum):
    """Document processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentUploadResponse(BaseModel):
    """Response after uploading a document"""
    document_id: str = Field(..., description="Unique identifier for the document")
    filename: str = Field(..., description="Original filename")
    status: ProcessingStatus = Field(..., description="Current processing status")
    message: str = Field(..., description="Status message")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "document_id": "doc_abc123",
                "filename": "research_paper.pdf",
                "status": "pending",
                "message": "Document queued for processing"
            }
        }
    }


class DocumentInfo(BaseModel):
    """Information about a stored document"""
    document_id: str
    filename: str
    file_type: str
    status: ProcessingStatus
    chunk_count: int = 0
    uploaded_at: datetime
    processed_at: Optional[datetime] = None
    error: Optional[str] = None


class DocumentStatusResponse(BaseModel):
    """Response for document status query"""
    document_id: str
    status: ProcessingStatus
    chunk_count: int = 0
    message: str


class QuestionRequest(BaseModel):
    """Request body for asking a question"""
    question: str = Field(..., min_length=5, max_length=500, description="The question to ask")
    document_ids: Optional[List[str]] = Field(
        default=None, 
        description="Optional list of document IDs to search within. If not provided, searches all documents."
    )
    top_k: int = Field(default=5, ge=1, le=20, description="Number of relevant chunks to retrieve")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "question": "What are the main findings of the research?",
                "document_ids": ["doc_abc123"],
                "top_k": 5
            }
        }
    }


class SourceChunk(BaseModel):
    """Information about a source chunk used in answering"""
    document_id: str
    filename: str
    chunk_index: int
    content: str
    similarity_score: float


class QueryMetrics(BaseModel):
    """Detailed metrics for query processing"""
    total_latency_ms: float = Field(..., description="Total end-to-end processing time")
    embedding_latency_ms: float = Field(..., description="Time to embed the query")
    retrieval_latency_ms: float = Field(..., description="FAISS similarity search time")
    generation_latency_ms: float = Field(..., description="LLM answer generation time")
    chunks_retrieved: int = Field(..., description="Number of chunks found")
    avg_similarity_score: float = Field(default=0.0, description="Average similarity across chunks")
    max_similarity_score: float = Field(default=0.0, description="Best chunk match score")
    min_similarity_score: float = Field(default=0.0, description="Worst included chunk score")
    timestamp: str = Field(..., description="ISO timestamp of the query")


class AnswerResponse(BaseModel):
    """Response containing the generated answer"""
    answer: str = Field(..., description="The generated answer based on retrieved context")
    sources: List[SourceChunk] = Field(..., description="Source chunks used to generate the answer")
    metrics: QueryMetrics = Field(..., description="Detailed performance metrics")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "answer": "The main findings indicate that...",
                "sources": [
                    {
                        "document_id": "doc_abc123",
                        "filename": "research_paper.pdf",
                        "chunk_index": 3,
                        "content": "The study found that...",
                        "similarity_score": 0.92
                    }
                ],
                "metrics": {
                    "total_latency_ms": 1250.45,
                    "embedding_latency_ms": 156.23,
                    "retrieval_latency_ms": 12.45,
                    "generation_latency_ms": 1081.77,
                    "chunks_retrieved": 5,
                    "avg_similarity_score": 0.7823,
                    "max_similarity_score": 0.92,
                    "min_similarity_score": 0.65,
                    "timestamp": "2024-01-28T00:15:30.123Z"
                }
            }
        }
    }


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = "healthy"
    version: str = "1.0.0"
    documents_count: int = 0
    vector_store_ready: bool = False
