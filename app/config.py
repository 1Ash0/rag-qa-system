"""
Configuration module for RAG-QA System
Uses Pydantic Settings for type-safe environment variable management
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # API Keys
    gemini_api_key: str = ""
    
    # Chunking Configuration
    chunk_size: int = 512
    chunk_overlap: int = 50
    
    # Rate Limiting
    rate_limit: str = "10/minute"
    
    # Model Configuration
    embedding_model: str = "models/embedding-001"
    llm_model: str = "gemini-1.5-flash"
    
    # Paths
    upload_dir: str = "data/uploads"
    vector_store_dir: str = "data/vector_store"
    
    # Retrieval Configuration
    top_k: int = 5
    similarity_threshold: float = 0.3
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
