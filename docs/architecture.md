# RAG-QA System Architecture

This document contains the architecture diagram for the RAG-QA system.

## System Architecture

```mermaid
flowchart TB
    subgraph Client["Client Layer"]
        U[("👤 User")]
        U -->|"POST /upload"| UP[Upload Endpoint]
        U -->|"POST /ask"| ASK[Ask Endpoint]
        U -->|"GET /documents"| DOC[Documents Endpoint]
    end
    
    subgraph API["FastAPI Server"]
        UP --> RL{{"Rate Limiter<br/>(10 req/min)"}}
        ASK --> RL
        DOC --> RL
        
        RL --> VAL["Pydantic<br/>Validation"]
    end
    
    subgraph Ingestion["Document Ingestion Pipeline"]
        direction TB
        BG["🔄 Background Task"]
        
        BG --> P["📄 Document Parser"]
        P -->|"PDF"| FITZ["PyMuPDF<br/>(fitz)"]
        P -->|"TXT"| TXT["Text Reader"]
        
        FITZ --> CH
        TXT --> CH
        
        CH["✂️ Text Chunker<br/>(512 chars, 50 overlap)"]
        CH --> EMB["🔢 Embedding Service<br/>(Gemini embedding-001)"]
        EMB --> VS
    end
    
    subgraph Storage["Storage Layer"]
        VS[("🗄️ FAISS<br/>Vector Store")]
        DS[("📁 Document Store<br/>(JSON)")]
        FS[("📂 File Storage")]
    end
    
    subgraph Retrieval["Query Pipeline"]
        direction TB
        QE["🔢 Query Embedding"]
        SS["🔍 Similarity Search<br/>(FAISS IndexFlatIP)"]
        CT["📋 Context Builder"]
        
        QE --> SS
        SS --> CT
    end
    
    subgraph Generation["Answer Generation"]
        LLM["🤖 Gemini LLM<br/>(gemini-1.5-flash)"]
        ANS["📝 Answer + Sources"]
        
        CT --> LLM
        LLM --> ANS
    end
    
    %% Connections
    VAL -->|"File Upload"| BG
    BG --> DS
    BG --> FS
    EMB --> VS
    
    VAL -->|"Question"| QE
    SS <--> VS
    
    ANS -->|"Response"| U
```

## Data Flow

### Document Upload Flow

```mermaid
sequenceDiagram
    participant U as User
    participant API as FastAPI
    participant BG as Background Task
    participant P as Parser
    participant C as Chunker
    participant E as Embeddings
    participant V as Vector Store
    
    U->>API: POST /upload (file)
    API->>API: Validate file type/size
    API->>BG: Queue processing
    API-->>U: 200 OK (document_id, pending)
    
    Note over BG: Async Processing
    
    BG->>P: Parse document
    P-->>BG: Raw text
    BG->>C: Chunk text
    C-->>BG: Text chunks
    BG->>E: Generate embeddings
    E-->>BG: Vectors
    BG->>V: Store vectors + metadata
    V-->>BG: Success
    BG->>BG: Update status: completed
```

### Question Answering Flow

```mermaid
sequenceDiagram
    participant U as User
    participant API as FastAPI
    participant E as Embeddings
    participant V as Vector Store
    participant L as LLM
    
    U->>API: POST /ask (question)
    API->>API: Rate limit check
    
    API->>E: Embed question
    E-->>API: Query vector
    
    API->>V: Similarity search
    V-->>API: Top-K chunks + scores
    
    API->>L: Generate answer (context + question)
    L-->>API: Answer text
    
    API-->>U: Answer + sources + metrics
```

## Component Diagram

```mermaid
graph LR
    subgraph Services
        DP[document_parser.py]
        CH[chunker.py]
        EM[embeddings.py]
        VS[vector_store.py]
        LM[llm.py]
    end
    
    subgraph API
        RT[routes.py]
        DE[dependencies.py]
        MA[main.py]
    end
    
    subgraph Background
        TA[tasks.py]
    end
    
    subgraph Models
        SC[schemas.py]
    end
    
    RT --> SC
    RT --> TA
    RT --> EM
    RT --> VS
    RT --> LM
    
    TA --> DP
    TA --> CH
    TA --> EM
    TA --> VS
    
    MA --> RT
    MA --> DE
```

## Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **API Framework** | FastAPI | High-performance async API |
| **Validation** | Pydantic | Request/response validation |
| **Rate Limiting** | slowapi | Request throttling |
| **PDF Parsing** | PyMuPDF | Extract text from PDFs |
| **Embeddings** | Google Gemini API | Text vectorization |
| **Vector Store** | FAISS | Similarity search |
| **LLM** | Google Gemini | Answer generation |
| **Background Tasks** | FastAPI BackgroundTasks | Async document processing |
