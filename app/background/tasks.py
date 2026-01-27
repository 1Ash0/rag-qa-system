"""
Background Task Handlers
Processes document ingestion asynchronously
"""

import os
import uuid
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict
import threading

from app.config import get_settings
from app.services.document_parser import DocumentParser, DocumentParseError
from app.services.chunker import TextChunker
from app.services.embeddings import EmbeddingService, EmbeddingError
from app.services.vector_store import get_vector_store, ChunkMetadata, VectorStoreError
from app.models.schemas import ProcessingStatus

logger = logging.getLogger(__name__)


class DocumentStore:
    """
    Simple document metadata store using JSON file
    Tracks document processing status and metadata
    """
    
    def __init__(self):
        settings = get_settings()
        self.store_path = Path(settings.upload_dir)
        self.store_path.mkdir(parents=True, exist_ok=True)
        self.metadata_file = self.store_path / "documents.json"
        self._lock = threading.Lock()
        self._documents: Dict[str, dict] = {}
        self._load()
    
    def _load(self):
        """Load existing document metadata"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, "r") as f:
                    self._documents = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load document store: {e}")
                self._documents = {}
    
    def _save(self):
        """Save document metadata to disk"""
        try:
            with open(self.metadata_file, "w") as f:
                json.dump(self._documents, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save document store: {e}")
    
    def create_document(self, document_id: str, filename: str, file_path: str) -> dict:
        """Create a new document entry"""
        with self._lock:
            doc = {
                "document_id": document_id,
                "filename": filename,
                "file_path": file_path,
                "file_type": Path(filename).suffix.lower(),
                "status": ProcessingStatus.PENDING.value,
                "chunk_count": 0,
                "uploaded_at": datetime.now().isoformat(),
                "processed_at": None,
                "error": None
            }
            self._documents[document_id] = doc
            self._save()
            return doc
    
    def update_status(
        self,
        document_id: str,
        status: ProcessingStatus,
        chunk_count: int = None,
        error: str = None
    ):
        """Update document processing status"""
        with self._lock:
            if document_id in self._documents:
                self._documents[document_id]["status"] = status.value
                if chunk_count is not None:
                    self._documents[document_id]["chunk_count"] = chunk_count
                if error is not None:
                    self._documents[document_id]["error"] = error
                if status == ProcessingStatus.COMPLETED:
                    self._documents[document_id]["processed_at"] = datetime.now().isoformat()
                self._save()
    
    def get_document(self, document_id: str) -> Optional[dict]:
        """Get document by ID"""
        return self._documents.get(document_id)
    
    def get_all_documents(self) -> list:
        """Get all documents"""
        return list(self._documents.values())
    
    def delete_document(self, document_id: str) -> bool:
        """Delete a document entry"""
        with self._lock:
            if document_id in self._documents:
                # Delete the actual file
                file_path = self._documents[document_id].get("file_path")
                if file_path and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        logger.warning(f"Failed to delete file {file_path}: {e}")
                
                del self._documents[document_id]
                self._save()
                return True
            return False


# Singleton instance
_document_store: Optional[DocumentStore] = None


def get_document_store() -> DocumentStore:
    """Get the global document store instance"""
    global _document_store
    if _document_store is None:
        _document_store = DocumentStore()
    return _document_store


async def process_document(document_id: str, file_path: str, filename: str):
    """
    Background task to process an uploaded document
    
    Pipeline:
    1. Parse document (PDF/TXT)
    2. Chunk text
    3. Generate embeddings
    4. Store in vector database
    
    This runs as a background task and updates document status.
    """
    store = get_document_store()
    settings = get_settings()
    
    logger.info(f"Starting processing for document: {document_id} ({filename})")
    store.update_status(document_id, ProcessingStatus.PROCESSING)
    
    try:
        # Step 1: Parse document
        logger.info(f"Parsing document: {filename}")
        text = DocumentParser.parse(file_path)
        
        if not text or len(text.strip()) < 10:
            raise DocumentParseError("Document contains no usable text content")
        
        logger.info(f"Extracted {len(text)} characters from document")
        
        # Step 2: Chunk text
        chunker = TextChunker(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap
        )
        chunks = chunker.chunk_text(text)
        
        if not chunks:
            raise DocumentParseError("No chunks created from document")
        
        logger.info(f"Created {len(chunks)} chunks from document")
        
        # Step 3: Generate embeddings
        embedding_service = EmbeddingService()
        chunk_texts = [chunk.content for chunk in chunks]
        embeddings = embedding_service.embed_batch(chunk_texts)
        
        logger.info(f"Generated {len(embeddings)} embeddings")
        
        # Step 4: Create metadata and store
        chunk_metadata = [
            ChunkMetadata(
                document_id=document_id,
                filename=filename,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                start_char=chunk.start_char,
                end_char=chunk.end_char
            )
            for chunk in chunks
        ]
        
        vector_store = get_vector_store()
        vector_store.add_embeddings(embeddings, chunk_metadata)
        vector_store.save()
        
        # Update status to completed
        store.update_status(
            document_id,
            ProcessingStatus.COMPLETED,
            chunk_count=len(chunks)
        )
        
        logger.info(f"Successfully processed document: {document_id}")
        
    except DocumentParseError as e:
        logger.error(f"Parse error for {document_id}: {e}")
        store.update_status(document_id, ProcessingStatus.FAILED, error=str(e))
        
    except EmbeddingError as e:
        logger.error(f"Embedding error for {document_id}: {e}")
        store.update_status(document_id, ProcessingStatus.FAILED, error=str(e))
        
    except VectorStoreError as e:
        logger.error(f"Vector store error for {document_id}: {e}")
        store.update_status(document_id, ProcessingStatus.FAILED, error=str(e))
        
    except Exception as e:
        logger.error(f"Unexpected error processing {document_id}: {e}")
        store.update_status(document_id, ProcessingStatus.FAILED, error=f"Processing failed: {e}")
