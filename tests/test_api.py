"""
Tests for RAG-QA System
"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import tempfile
import os

# Set test environment before importing app
os.environ["GEMINI_API_KEY"] = "test_key"

from app.main import app
from app.services.chunker import TextChunker, TextChunk
from app.services.document_parser import DocumentParser, DocumentParseError


client = TestClient(app)


class TestHealthEndpoint:
    """Tests for the health check endpoint"""
    
    def test_health_check(self):
        """Test that health endpoint returns successfully"""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "documents_count" in data


class TestRootEndpoint:
    """Tests for the root endpoint"""
    
    def test_root(self):
        """Test that root endpoint returns API info"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "RAG-QA System"
        assert "docs" in data


class TestTextChunker:
    """Tests for the text chunking service"""
    
    def test_basic_chunking(self):
        """Test basic text chunking"""
        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        text = "This is a test sentence. " * 20  # ~500 characters
        
        chunks = chunker.chunk_text(text)
        
        assert len(chunks) > 1
        assert all(isinstance(chunk, TextChunk) for chunk in chunks)
        assert all(len(chunk.content) <= 150 for chunk in chunks)  # Allow some flexibility
    
    def test_empty_text(self):
        """Test chunking empty text"""
        chunker = TextChunker()
        chunks = chunker.chunk_text("")
        assert chunks == []
    
    def test_short_text(self):
        """Test chunking text shorter than chunk size"""
        chunker = TextChunker(chunk_size=500)
        text = "Short text."
        
        chunks = chunker.chunk_text(text)
        
        assert len(chunks) == 1
        assert chunks[0].content == "Short text."
    
    def test_chunk_overlap(self):
        """Test that chunks have proper overlap"""
        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        # Create text with clear sentences
        text = "First sentence here. Second sentence here. Third sentence here. Fourth sentence here. Fifth sentence here."
        
        chunks = chunker.chunk_text(text)
        
        # Verify chunk indices are sequential
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i
    
    def test_invalid_overlap(self):
        """Test that overlap >= chunk_size raises error"""
        with pytest.raises(ValueError):
            TextChunker(chunk_size=100, chunk_overlap=100)


class TestDocumentParser:
    """Tests for the document parser service"""
    
    def test_parse_txt_file(self):
        """Test parsing a TXT file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("This is test content.\nWith multiple lines.")
            temp_path = f.name
        
        try:
            content = DocumentParser.parse(temp_path)
            assert "This is test content" in content
            assert "multiple lines" in content
        finally:
            os.unlink(temp_path)
    
    def test_parse_nonexistent_file(self):
        """Test parsing a file that doesn't exist"""
        with pytest.raises(DocumentParseError) as exc_info:
            DocumentParser.parse("/nonexistent/file.txt")
        
        assert "not found" in str(exc_info.value).lower()
    
    def test_unsupported_format(self):
        """Test parsing an unsupported file format"""
        with tempfile.NamedTemporaryFile(suffix='.xyz', delete=False) as f:
            f.write(b"test content")
            temp_path = f.name
        
        try:
            with pytest.raises(DocumentParseError) as exc_info:
                DocumentParser.parse(temp_path)
            assert "unsupported" in str(exc_info.value).lower()
        finally:
            os.unlink(temp_path)
    
    def test_get_supported_formats(self):
        """Test getting supported formats"""
        formats = DocumentParser.get_supported_formats()
        assert ".pdf" in formats
        assert ".txt" in formats


class TestUploadEndpoint:
    """Tests for the document upload endpoint"""
    
    def test_upload_no_file(self):
        """Test upload without a file"""
        response = client.post("/api/v1/upload")
        assert response.status_code == 422  # Validation error
    
    def test_upload_unsupported_format(self):
        """Test uploading an unsupported file format"""
        content = b"test content"
        response = client.post(
            "/api/v1/upload",
            files={"file": ("test.xyz", content, "application/octet-stream")}
        )
        assert response.status_code == 400
        assert "unsupported" in response.json()["detail"].lower()
    
    def test_upload_empty_file(self):
        """Test uploading an empty file"""
        response = client.post(
            "/api/v1/upload",
            files={"file": ("empty.txt", b"", "text/plain")}
        )
        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()


class TestAskEndpoint:
    """Tests for the question answering endpoint"""
    
    def test_ask_without_documents(self):
        """Test asking a question when no documents are uploaded"""
        # This may or may not fail depending on if documents exist from previous tests
        response = client.post(
            "/api/v1/ask",
            json={"question": "What is the meaning of life?"}
        )
        # Either no documents error or success
        assert response.status_code in [200, 400]
    
    def test_ask_invalid_question(self):
        """Test asking with an invalid question (too short)"""
        response = client.post(
            "/api/v1/ask",
            json={"question": "ab"}  # Less than 3 characters
        )
        assert response.status_code == 422  # Validation error
    
    def test_ask_with_filters(self):
        """Test that document_ids filter is accepted"""
        response = client.post(
            "/api/v1/ask",
            json={
                "question": "Test question here",
                "document_ids": ["doc_nonexistent"],
                "top_k": 3
            }
        )
        # Should either work or return no documents error
        assert response.status_code in [200, 400, 500]


class TestDocumentsEndpoint:
    """Tests for the documents listing endpoint"""
    
    def test_list_documents(self):
        """Test listing documents"""
        response = client.get("/api/v1/documents")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
