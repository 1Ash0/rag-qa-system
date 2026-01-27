"""
LLM Service using Google Gemini API
Generates answers based on retrieved context
"""

import google.generativeai as genai
from typing import List, Optional
import logging
import time
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import get_settings
from app.services.vector_store import ChunkMetadata

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Exception raised when LLM generation fails"""
    pass


class LLMService:
    """
    Generates answers using Google Gemini API with RAG context
    """
    
    # RAG prompt template
    SYSTEM_PROMPT = """You are a helpful assistant that answers questions based on provided context from documents. 

Instructions:
1. Answer the question based ONLY on the provided context
2. If the context doesn't contain relevant information, say "I couldn't find relevant information in the provided documents."
3. Cite which sources you used in your answer
4. Be concise but comprehensive
5. If the question is ambiguous, ask for clarification"""

    CONTEXT_TEMPLATE = """Context from documents:

{context}

---

Question: {question}

Please provide a comprehensive answer based on the context above. If you reference specific information, indicate which source it came from."""
    
    def __init__(self):
        """Initialize the LLM service with Gemini API"""
        settings = get_settings()
        
        if not settings.gemini_api_key:
            raise LLMError("GEMINI_API_KEY not configured")
        
        genai.configure(api_key=settings.gemini_api_key)
        
        # LOGGING API KEY DEBUG INFO: REMOVED FOR SECURITY
        
        self.api_key = settings.gemini_api_key # Store for debug
        
        self.model = genai.GenerativeModel(
            model_name=settings.llm_model,
            system_instruction=self.SYSTEM_PROMPT
        )
        
        logger.info(f"LLMService initialized with model: {settings.llm_model}")
    
    @retry(
        stop=stop_after_attempt(6),
        wait=wait_exponential(multiplier=2, min=5, max=90),  # Wait up to 90s for quota reset
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    def generate_answer(
        self,
        question: str,
        context_chunks: List[tuple]  # List of (ChunkMetadata, similarity_score)
    ) -> tuple[str, float]:
        """
        Generate an answer based on question and retrieved context
        
        Args:
            question: The user's question
            context_chunks: Retrieved chunks with similarity scores
            
        Returns:
            Tuple of (answer, generation_latency_ms)
        """
        if not question or not question.strip():
            raise LLMError("Empty question provided")
        
        # Build context from chunks
        context_parts = []
        for i, (chunk_meta, score) in enumerate(context_chunks, 1):
            source_info = f"[Source {i}: {chunk_meta.filename}, chunk {chunk_meta.chunk_index + 1}]"
            context_parts.append(f"{source_info}\n{chunk_meta.content}")
        
        if not context_parts:
            return "I couldn't find any relevant information in the documents to answer your question.", 0.0
        
        context = "\n\n".join(context_parts)
        prompt = self.CONTEXT_TEMPLATE.format(context=context, question=question)
        
        try:
            start_time = time.time()
            
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=1024,
                )
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Handle response
            if response.text:
                logger.info(f"Generated answer in {latency_ms:.2f}ms")
                return response.text, latency_ms
            else:
                raise LLMError("Empty response from LLM")
                
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            
            # Debug info
            masked_key = f"{self.api_key[:10]}...{self.api_key[-5:]}" if hasattr(self, 'api_key') else "UNKNOWN"
            debug_info = f"[Key: {masked_key}, Model: {self.model.model_name}]"
            
            raise LLMError(f"Failed to generate answer: {e} {debug_info}")
    
    def generate_with_no_context(self, question: str) -> str:
        """
        Handle cases where no relevant context was found
        
        This is a documented retrieval failure case - when the question
        is about topics not covered in the uploaded documents.
        """
        return (
            "I couldn't find relevant information in the provided documents to answer "
            f"your question: '{question}'\n\n"
            "This could mean:\n"
            "1. The topic isn't covered in the uploaded documents\n"
            "2. The question may need to be rephrased\n"
            "3. More relevant documents may need to be uploaded"
        )
