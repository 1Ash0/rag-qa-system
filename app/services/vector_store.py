"""
Vector Store Service using FAISS
Stores and retrieves document embeddings
"""

import faiss
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import json
import logging
import os
import threading

from app.config import get_settings
from app.services.embeddings import EmbeddingService

logger = logging.getLogger(__name__)


class VectorStoreError(Exception):
    """Exception raised for vector store operations"""
    pass


class ChunkMetadata:
    """Metadata for a stored chunk"""
    def __init__(
        self,
        document_id: str,
        filename: str,
        chunk_index: int,
        content: str,
        start_char: int,
        end_char: int
    ):
        self.document_id = document_id
        self.filename = filename
        self.chunk_index = chunk_index
        self.content = content
        self.start_char = start_char
        self.end_char = end_char
    
    def to_dict(self) -> dict:
        return {
            "document_id": self.document_id,
            "filename": self.filename,
            "chunk_index": self.chunk_index,
            "content": self.content,
            "start_char": self.start_char,
            "end_char": self.end_char
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ChunkMetadata":
        return cls(**data)


class VectorStore:
    """
    FAISS-based vector store for document embeddings
    
    Uses IndexFlatIP (inner product) for cosine similarity search
    after normalizing vectors.
    """
    
    def __init__(self, dimension: int = 768):
        """
        Initialize the vector store
        
        Args:
            dimension: Embedding dimension (768 for Gemini)
        """
        self.dimension = dimension
        self.index: Optional[faiss.IndexFlatIP] = None
        self.metadata: List[ChunkMetadata] = []
        self.document_chunks: Dict[str, List[int]] = {}  # doc_id -> chunk indices
        self._lock = threading.Lock()
        
        settings = get_settings()
        self.store_path = Path(settings.vector_store_dir)
        self.store_path.mkdir(parents=True, exist_ok=True)
        
        self._initialize_or_load()
    
    def _initialize_or_load(self):
        """Initialize new index or load existing one"""
        index_path = self.store_path / "faiss.index"
        metadata_path = self.store_path / "metadata.json"
        
        if index_path.exists() and metadata_path.exists():
            self._load()
        else:
            self._initialize_new()
    
    def _initialize_new(self):
        """Create a new empty index"""
        self.index = faiss.IndexFlatIP(self.dimension)
        self.metadata = []
        self.document_chunks = {}
        logger.info(f"Created new FAISS index with dimension {self.dimension}")
    
    def _load(self):
        """Load existing index and metadata from disk"""
        try:
            index_path = self.store_path / "faiss.index"
            metadata_path = self.store_path / "metadata.json"
            
            self.index = faiss.read_index(str(index_path))
            
            with open(metadata_path, "r") as f:
                data = json.load(f)
                self.metadata = [ChunkMetadata.from_dict(m) for m in data["chunks"]]
                self.document_chunks = data.get("document_chunks", {})
            
            logger.info(f"Loaded FAISS index with {self.index.ntotal} vectors")
            
        except Exception as e:
            logger.error(f"Failed to load index: {e}, creating new one")
            self._initialize_new()
    
    def save(self):
        """Save index and metadata to disk"""
        with self._lock:
            try:
                index_path = self.store_path / "faiss.index"
                metadata_path = self.store_path / "metadata.json"
                
                faiss.write_index(self.index, str(index_path))
                
                with open(metadata_path, "w") as f:
                    json.dump({
                        "chunks": [m.to_dict() for m in self.metadata],
                        "document_chunks": self.document_chunks
                    }, f, indent=2)
                
                logger.info(f"Saved FAISS index with {self.index.ntotal} vectors")
                
            except Exception as e:
                logger.error(f"Failed to save index: {e}")
                raise VectorStoreError(f"Failed to save vector store: {e}")
    
    def add_embeddings(
        self,
        embeddings: List[List[float]],
        chunks_metadata: List[ChunkMetadata]
    ):
        """
        Add embeddings to the vector store
        
        Args:
            embeddings: List of embedding vectors
            chunks_metadata: Corresponding metadata for each embedding
        """
        if len(embeddings) != len(chunks_metadata):
            raise VectorStoreError("Embeddings and metadata length mismatch")
        
        if not embeddings:
            return
        
        with self._lock:
            # Convert to numpy and normalize for cosine similarity
            vectors = np.array(embeddings, dtype=np.float32)
            faiss.normalize_L2(vectors)
            
            # Track starting index for new chunks
            start_idx = len(self.metadata)
            
            # Add to index
            self.index.add(vectors)
            
            # Add metadata
            for i, meta in enumerate(chunks_metadata):
                self.metadata.append(meta)
                
                # Update document -> chunk mapping
                if meta.document_id not in self.document_chunks:
                    self.document_chunks[meta.document_id] = []
                self.document_chunks[meta.document_id].append(start_idx + i)
            
            logger.info(f"Added {len(embeddings)} vectors to index (total: {self.index.ntotal})")
    
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        document_ids: Optional[List[str]] = None,
        similarity_threshold: float = 0.0
    ) -> List[Tuple[ChunkMetadata, float]]:
        """
        Search for similar chunks
        
        Args:
            query_embedding: Query vector
            top_k: Number of results to return
            document_ids: Optional filter by document IDs
            similarity_threshold: Minimum similarity score
            
        Returns:
            List of (metadata, similarity_score) tuples
        """
        if self.index is None or self.index.ntotal == 0:
            logger.warning("Search called on empty index")
            return []
        
        # Normalize query vector
        query_vector = np.array([query_embedding], dtype=np.float32)
        faiss.normalize_L2(query_vector)
        
        # Search with more results if filtering
        search_k = min(top_k * 3, self.index.ntotal) if document_ids else min(top_k, self.index.ntotal)
        
        distances, indices = self.index.search(query_vector, search_k)
        
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:
                continue
            
            metadata = self.metadata[idx]
            
            # Filter by document IDs if specified
            if document_ids and metadata.document_id not in document_ids:
                continue
            
            # Filter by similarity threshold
            if dist < similarity_threshold:
                continue
            
            results.append((metadata, float(dist)))
            
            if len(results) >= top_k:
                break
        
        return results
    
    def get_document_count(self) -> int:
        """Get number of unique documents in the store"""
        return len(self.document_chunks)
    
    def get_chunk_count(self) -> int:
        """Get total number of chunks in the store"""
        return len(self.metadata)
    
    def get_document_chunk_count(self, document_id: str) -> int:
        """Get number of chunks for a specific document"""
        return len(self.document_chunks.get(document_id, []))
    
    def delete_document(self, document_id: str) -> bool:
        """
        Delete all chunks for a document
        
        Note: FAISS IndexFlatIP doesn't support deletion, so we rebuild the index
        This is acceptable for small-medium scale usage
        """
        if document_id not in self.document_chunks:
            return False
        
        with self._lock:
            # Get indices to remove
            remove_indices = set(self.document_chunks[document_id])
            
            # Collect remaining chunks
            new_metadata = []
            embeddings_to_keep = []
            
            for i, meta in enumerate(self.metadata):
                if i not in remove_indices:
                    new_metadata.append(meta)
                    # Get the embedding from the index
                    embeddings_to_keep.append(self.index.reconstruct(i))
            
            # Rebuild index
            self._initialize_new()
            
            if embeddings_to_keep:
                vectors = np.array(embeddings_to_keep, dtype=np.float32)
                # Vectors are already normalized
                self.index.add(vectors)
            
            # Update metadata
            self.metadata = new_metadata
            
            # Rebuild document_chunks mapping
            self.document_chunks = {}
            for i, meta in enumerate(self.metadata):
                if meta.document_id not in self.document_chunks:
                    self.document_chunks[meta.document_id] = []
                self.document_chunks[meta.document_id].append(i)
            
            if document_id in self.document_chunks:
                del self.document_chunks[document_id]
            
            logger.info(f"Deleted document {document_id}, rebuilt index")
            return True
    
    def is_ready(self) -> bool:
        """Check if the vector store is ready for queries"""
        return self.index is not None


# Singleton instance
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Get the global vector store instance"""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore(dimension=EmbeddingService.get_dimension())
    return _vector_store
