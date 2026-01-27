import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

try:
    from app.services.embeddings import EmbeddingService
    print(f"Imported EmbeddingService: {EmbeddingService}")
    
    if hasattr(EmbeddingService, 'get_dimension'):
        print("SUCCESS: get_dimension attribute exists.")
        print(f"Dimension value: {EmbeddingService.get_dimension()}")
    else:
        print("FAILURE: get_dimension attribute MISSING.")
        print(f"Dir: {dir(EmbeddingService)}")
        
except Exception as e:
    print(f"Import failed: {e}")
