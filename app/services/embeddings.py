import google.generativeai as genai
from typing import List, Optional
import logging
import time
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Assuming app.config is correct
from app.config import get_settings

logger = logging.getLogger(__name__)

class EmbeddingError(Exception):
    pass

class EmbeddingService:
    def __init__(self):
        settings = get_settings()
        if not settings.gemini_api_key:
            raise EmbeddingError("GEMINI_API_KEY not configured")
        
        # Best Practice: Check if configured, or move this to app startup
        try:
            genai.configure(api_key=settings.gemini_api_key)
            
            # LOGGING API KEY DEBUG INFO: REMOVED FOR SECURITY
                
                
            # Ensure model name has 'models/' prefix
            self.model = settings.embedding_model if settings.embedding_model.startswith("models/") else f"models/{settings.embedding_model}"
            self.api_key = settings.gemini_api_key  # Store for debug logging
            logger.info(f"EmbeddingService initialized with model: {self.model}")
            
        except Exception as e:
            logger.error(f"Failed to configure genai or initialize model: {e}")
            raise EmbeddingError(f"Initialization failed: {e}")

        # Dynamically fetch dimension or keep config
        self.embedding_dimension = 768 

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception) # Narrow this down to specific API errors in prod
    )
    async def embed_text(self, text: str, task_type: str = "retrieval_document") -> List[float]:
        """Async wrapper for embedding a single text with retries"""
        if not text or not text.strip():
            raise EmbeddingError("Cannot embed empty text")

        try:
            # Run the synchronous SDK method in a thread to avoid blocking the event loop
            result = await asyncio.to_thread(
                genai.embed_content,
                model=self.model,
                content=text,
                task_type=task_type
            )
            return result['embedding']
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            raise e # Raise so 'tenacity' can catch and retry

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generates embeddings in parallel batches.
        """
        if not texts:
            return []

        # OPTION A: True API Batching (If supported by your specific model version)
        # result = await asyncio.to_thread(
        #     genai.embed_content,
        #     model=self.model,
        #     content=texts, # Pass list directly
        #     task_type="retrieval_document"
        # )
        # return result['embedding']

        # OPTION B: Parallel Execution (If model doesn't support list input)
        # This runs all requests concurrently rather than serially
        try:
            start_time = time.time()
            
            # Create tasks for all texts
            tasks = [self.embed_text(text) for text in texts]
            
            # Run them all at once
            embeddings = await asyncio.gather(*tasks)
            
            logger.info(f"Batch embedded {len(texts)} texts in {time.time() - start_time:.2f}s")
            return list(embeddings)
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Embedding generation failed: {error_msg}")
            
            # Debug info
            masked_key = f"{self.api_key[:10]}...{self.api_key[-5:]}" if hasattr(self, 'api_key') else "UNKNOWN"
            debug_info = f"[Key: {masked_key}, Model: {self.model}]"
            
            # Check for quota/rate limit errors
            if "quota" in error_msg.lower() or "rate limit" in error_msg.lower() or "limit:" in error_msg.lower():
                raise EmbeddingError(
                    f"Gemini API quota exceeded. Please wait a few minutes and try again. "
                    f"Consider using smaller documents or upgrading to paid tier. Error: {e}"
                )
            
            raise EmbeddingError(f"Failed to generate embedding: {e} {debug_info}")

    # Helper for queries specifically
    async def embed_query(self, query: str) -> List[float]:
        return await self.embed_text(query, task_type="retrieval_query")

    @classmethod
    def get_dimension(cls) -> int:
        """Get the embedding dimension"""
        return 768