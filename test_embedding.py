"""Test script to debug Gemini embedding API"""
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

import google.generativeai as genai

# Get API key
api_key = os.getenv("GEMINI_API_KEY")
print(f"API Key loaded: {api_key[:20]}..." if api_key else "No API key found!")

# Configure API
genai.configure(api_key=api_key)

# Test embedding
try:
    print("\nTesting embedding with models/text-embedding-004...")
    result = genai.embed_content(
        model="models/text-embedding-004",
        content="This is a test document.",
        task_type="retrieval_document"
    )
    print(f"SUCCESS! Embedding dimension: {len(result['embedding'])}")
    print(f"First 5 values: {result['embedding'][:5]}")
except Exception as e:
    print(f"ERROR with text-embedding-004: {e}")

# Try alternative model
try:
    print("\nTesting embedding with models/embedding-001...")
    result = genai.embed_content(
        model="models/embedding-001",
        content="This is a test document.",
        task_type="retrieval_document"
    )
    print(f"SUCCESS! Embedding dimension: {len(result['embedding'])}")
except Exception as e:
    print(f"ERROR with embedding-001: {e}")
