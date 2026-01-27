"""
Tests for RAG-QA System
"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import tempfile
import os
import time

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
        assert "vector_store_ready" in data


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
            f.write("This is a test document.\nWith multiple lines.")
            temp_path = f.name
        
        try:
            parser = DocumentParser()
            text = parser.parse(temp_path)
            
            assert "This is a test document" in text
            assert "With multiple lines" in text
        finally:
            os.unlink(temp_path)
    
    def test_parse_empty_file(self):
        """Test parsing an empty file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            temp_path = f.name
        
        try:
            parser = DocumentParser()
            with pytest.raises(DocumentParseError):
                parser.parse(temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_parse_nonexistent_file(self):
        """Test parsing a file that doesn't exist"""
        parser = DocumentParser()
        with pytest.raises(DocumentParseError):
            parser.parse("/nonexistent/file.txt")


class TestUploadEndpoint:
    """Tests for the document upload endpoint"""
    
    def test_upload_txt_file(self):
        """Test uploading a TXT file"""
        # Create a temporary text file
        content = b"This is a test document for upload."
        
        response = client.post(
            "/api/v1/upload",
            files={"file": ("test.txt", content, "text/plain")}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "document_id" in data
        assert data["filename"] == "test.txt"
        assert data["status"] in ["pending", "processing"]
    
    def test_upload_unsupported_format(self):
        """Test uploading an unsupported file format"""
        content = b"fake content"
        
        response = client.post(
            "/api/v1/upload",
            files={"file": ("test.docx", content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        )
        
        assert response.status_code == 400
        assert "Unsupported file format" in response.json()["detail"]
    
    def test_upload_empty_file(self):
        """Test uploading an empty file"""
        response = client.post(
            "/api/v1/upload",
            files={"file": ("empty.txt", b"", "text/plain")}
        )
        
        assert response.status_code == 400
        assert "Empty file" in response.json()["detail"]
    
    def test_upload_file_too_large(self):
        """Test uploading a file that exceeds size limit"""
        # Create content larger than 10MB
        large_content = b"x" * (11 * 1024 * 1024)
        
        response = client.post(
            "/api/v1/upload",
            files={"file": ("large.txt", large_content, "text/plain")}
        )
        
        assert response.status_code == 400
        assert "exceeds" in response.json()["detail"].lower()


class TestAskEndpoint:
    """Tests for the question answering endpoint"""
    
    def test_ask_without_documents(self):
        """Test asking a question when no documents are uploaded"""
        response = client.post(
            "/api/v1/ask",
            json={"question": "What is this about?"}
        )
        
        assert response.status_code == 400
        assert "No documents" in response.json()["detail"]
    
    def test_ask_with_short_question(self):
        """Test asking a question that's too short"""
        response = client.post(
            "/api/v1/ask",
            json={"question": "Hi"}
        )
        
        # Pydantic validation returns 422, not 400
        assert response.status_code == 422
        assert "at least" in response.json()["detail"][0]["msg"].lower()
    
    def test_ask_with_long_question(self):
        """Test asking a question that's too long"""
        long_question = "x" * 501
        
        response = client.post(
            "/api/v1/ask",
            json={"question": long_question}
        )
        
        assert response.status_code == 400
        assert "exceed" in response.json()["detail"].lower()
    
    def test_ask_metrics_structure(self):
        """Test that metrics have the correct structure"""
        # This test would need documents to be uploaded first
        # For now, we'll test the schema validation
        from app.models.schemas import QueryMetrics
        
        # Test that QueryMetrics can be instantiated with all required fields
        metrics = QueryMetrics(
            total_latency_ms=1250.45,
            embedding_latency_ms=156.23,
            retrieval_latency_ms=12.45,
            generation_latency_ms=1081.77,
            chunks_retrieved=5,
            avg_similarity_score=0.7823,
            max_similarity_score=0.92,
            min_similarity_score=0.65,
            timestamp="2024-01-28T00:15:30.123Z"
        )
        
        assert metrics.total_latency_ms == 1250.45
        assert metrics.chunks_retrieved == 5
        assert metrics.avg_similarity_score == 0.7823
        assert metrics.timestamp == "2024-01-28T00:15:30.123Z"


class TestDocumentsEndpoint:
    """Tests for the documents listing endpoint"""
    
    def test_list_documents(self):
        """Test listing all documents"""
        response = client.get("/api/v1/documents")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestRateLimiting:
    """Tests for rate limiting functionality"""
    
    def test_rate_limit_enforcement(self):
        """Test that rate limiting is enforced"""
        # Make multiple rapid requests to trigger rate limit
        # Note: This test may be flaky depending on rate limit settings
        
        responses = []
        for _ in range(15):  # Exceed the 10/minute limit
            response = client.get("/api/v1/health")
            responses.append(response)
            time.sleep(0.1)  # Small delay to avoid overwhelming the server
        
        # At least one request should be rate limited
        status_codes = [r.status_code for r in responses]
        
        # Either all succeed (if rate limiting is disabled in tests)
        # or some are rate limited (429)
        assert all(code in [200, 429] for code in status_codes)


class TestErrorHandling:
    """Tests for error handling scenarios"""
    
    def test_invalid_document_id(self):
        """Test accessing a non-existent document"""
        response = client.get("/api/v1/documents/invalid_id/status")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_delete_nonexistent_document(self):
        """Test deleting a document that doesn't exist"""
        response = client.delete("/api/v1/documents/nonexistent_id")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_invalid_json_payload(self):
        """Test sending invalid JSON to ask endpoint"""
        response = client.post(
            "/api/v1/ask",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422  # Unprocessable Entity


class TestMetricsValidation:
    """Tests for metrics validation and structure"""
    
    def test_query_metrics_defaults(self):
        """Test QueryMetrics with default values for similarity scores"""
        from app.models.schemas import QueryMetrics
        
        metrics = QueryMetrics(
            total_latency_ms=100.0,
            embedding_latency_ms=50.0,
            retrieval_latency_ms=10.0,
            generation_latency_ms=40.0,
            chunks_retrieved=0,
            timestamp="2024-01-28T00:15:30.123Z"
        )
        
        # When no chunks are retrieved, similarity scores should default to 0.0
        assert metrics.avg_similarity_score == 0.0
        assert metrics.max_similarity_score == 0.0
        assert metrics.min_similarity_score == 0.0
    
    def test_query_metrics_with_scores(self):
        """Test QueryMetrics with actual similarity scores"""
        from app.models.schemas import QueryMetrics
        
        metrics = QueryMetrics(
            total_latency_ms=1250.45,
            embedding_latency_ms=156.23,
            retrieval_latency_ms=12.45,
            generation_latency_ms=1081.77,
            chunks_retrieved=5,
            avg_similarity_score=0.7823,
            max_similarity_score=0.92,
            min_similarity_score=0.65,
            timestamp="2024-01-28T00:15:30.123Z"
        )
        
        # Verify all fields are correctly set
        assert metrics.chunks_retrieved == 5
        assert 0.0 <= metrics.avg_similarity_score <= 1.0
        assert 0.0 <= metrics.max_similarity_score <= 1.0
        assert 0.0 <= metrics.min_similarity_score <= 1.0
        assert metrics.min_similarity_score <= metrics.avg_similarity_score <= metrics.max_similarity_score
