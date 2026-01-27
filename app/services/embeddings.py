"""
Embedding Service using Google Gemini API
Generates embeddings for text chunks
"""

import google.generativeai as genai
from typing import List
import logging
import time

from app.config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingError(Exception):
    """Exception raised when embedding generation fails"""
    pass


class EmbeddingService:
    """
    Generates text embeddings using Google Gemini API
    
    Uses the embedding-001 model which produces 768-dimensional vectors
    """
    
    EMBEDDING_DIMENSION = 768
    
    def __init__(self):
        """Initialize the embedding service with Gemini API"""
        settings = get_settings()
        
        if not settings.gemini_api_key:
            raise EmbeddingError("GEMINI_API_KEY not configured")
        
        genai.configure(api_key=settings.gemini_api_key)
        self.model = settings.embedding_model
        
        logger.info(f"EmbeddingService initialized with model: {self.model}")
    
    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        if not text or not text.strip():
            raise EmbeddingError("Cannot embed empty text")
        
        try:
            start_time = time.time()
            
            result = genai.embed_content(
                model=self.model,
                content=text,
                task_type="retrieval_document"
            )
            
            latency_ms = (time.time() - start_time) * 1000
            logger.debug(f"Generated embedding in {latency_ms:.2f}ms")
            
            return result['embedding']
            
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise EmbeddingError(f"Failed to generate embedding: {e}")
    
    def embed_query(self, query: str) -> List[float]:
        """
        Generate embedding for a query (uses different task type)
        
        Args:
            query: Query text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        if not query or not query.strip():
            raise EmbeddingError("Cannot embed empty query")
        
        try:
            start_time = time.time()
            
            result = genai.embed_content(
                model=self.model,
                content=query,
                task_type="retrieval_query"
            )
            
            latency_ms = (time.time() - start_time) * 1000
            logger.debug(f"Generated query embedding in {latency_ms:.2f}ms")
            
            return result['embedding']
            
        except Exception as e:
            logger.error(f"Query embedding generation failed: {e}")
            raise EmbeddingError(f"Failed to generate query embedding: {e}")
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        embeddings = []
        total_start = time.time()
        
        for i, text in enumerate(texts):
            try:
                embedding = self.embed_text(text)
                embeddings.append(embedding)
                
                # Rate limiting - small delay between requests
                if i < len(texts) - 1:
                    time.sleep(0.05)  # 50ms delay
                    
            except Exception as e:
                logger.error(f"Failed to embed text {i}: {e}")
                raise EmbeddingError(f"Batch embedding failed at index {i}: {e}")
        
        total_latency = (time.time() - total_start) * 1000
        logger.info(f"Batch embedded {len(texts)} texts in {total_latency:.2f}ms")
        
        return embeddings
    
    @classmethod
    def get_dimension(cls) -> int:
        """Get the embedding dimension"""
        return cls.EMBEDDING_DIMENSION
