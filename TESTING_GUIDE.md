# Manual Testing Guide - RAG QA System

The server is running at **http://localhost:8000**

## Step 1: Verify Server is Running

Open your browser and go to:
- **Swagger UI**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/v1/health

## Step 2: Upload a PDF Document

### Option A: Using Swagger UI (Recommended)
1. Go to http://localhost:8000/docs
2. Find the **POST /api/v1/upload** endpoint
3. Click "Try it out"
4. Click "Choose File" and select a PDF
5. Click "Execute"
6. Note the `document_id` from the response

### Option B: Using PowerShell
```powershell
# Replace 'path\to\your\document.pdf' with actual path
$response = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/upload" `
    -Method POST `
    -Form @{file = Get-Item "path\to\your\document.pdf"}

$response.Content | ConvertFrom-Json
```

### Option C: Using curl (if installed)
```bash
curl -X POST "http://localhost:8000/api/v1/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@path/to/your/document.pdf"
```

## Step 3: Check Processing Status

### Using Swagger UI:
1. Find **GET /api/v1/documents/{document_id}/status**
2. Enter your `document_id`
3. Click "Execute"
4. Wait until status is "completed"

### Using PowerShell:
```powershell
# Replace 'doc_abc123' with your actual document_id
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/documents/doc_abc123/status"
```

## Step 4: Ask Questions

### Using Swagger UI:
1. Find **POST /api/v1/ask**
2. Click "Try it out"
3. Enter your question in the request body:
```json
{
  "question": "What is this document about?",
  "top_k": 5
}
```
4. Click "Execute"
5. **Verify the enhanced metrics in the response!**

### Using PowerShell:
```powershell
$body = @{
    question = "What is this document about?"
    top_k = 5
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/ask" `
    -Method POST `
    -Body $body `
    -ContentType "application/json"

# Display the full response including metrics
$response | ConvertTo-Json -Depth 10
```

## Step 5: Verify Enhanced Metrics

Check that the response includes ALL these fields in `metrics`:

✅ **Latency Breakdown**:
- `total_latency_ms`
- `embedding_latency_ms`
- `retrieval_latency_ms`
- `generation_latency_ms`

✅ **Retrieval Quality**:
- `chunks_retrieved`
- `avg_similarity_score`
- `max_similarity_score`
- `min_similarity_score`

✅ **Timestamp**:
- `timestamp` (ISO format)

## Example Expected Response

```json
{
  "answer": "This document discusses...",
  "sources": [
    {
      "document_id": "doc_abc123",
      "filename": "sample.pdf",
      "chunk_index": 0,
      "content": "The document content...",
      "similarity_score": 0.89
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
    "timestamp": "2026-01-28T00:34:30.123Z"
  }
}
```

## Testing Error Handling

### Test 1: Question Too Short
```json
{
  "question": "Hi"
}
```
Expected: 422 error with validation message

### Test 2: Question Too Long
```json
{
  "question": "x repeated 501 times..."
}
```
Expected: 422 error about max length

### Test 3: Empty Vector Store
Ask a question before uploading any documents.
Expected: 400 error "No documents have been processed yet"

## Quick Test with Sample PDF

If you don't have a PDF handy, you can create a simple test document:

1. Create a text file `test.txt` with some content
2. Upload it using the same process
3. Ask questions about it

## Troubleshooting

- **Server not responding**: Check if it's still running in the terminal
- **Upload fails**: Check file size (max 10MB by default)
- **No answer**: Wait for document processing to complete
- **Low similarity scores**: Question might not match document content

---

## What to Look For

✅ Upload works and returns document_id  
✅ Processing completes successfully  
✅ Questions return answers with sources  
✅ **Metrics object has all 9 fields**  
✅ Latency values are reasonable (< 5000ms)  
✅ Similarity scores are between 0 and 1  
✅ Timestamp is in ISO format  

The enhanced metrics tracking is the key improvement - make sure you see detailed latency breakdown and similarity statistics!
