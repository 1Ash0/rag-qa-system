"""
Text Chunking Service
Splits documents into smaller chunks for embedding
"""

from typing import List, Tuple
from dataclasses import dataclass
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class TextChunk:
    """Represents a chunk of text with metadata"""
    content: str
    start_char: int
    end_char: int
    chunk_index: int


class TextChunker:
    """
    Recursive character text splitter that preserves sentence boundaries.
    
    Design Decision - Chunk Size: 512 characters with 50 character overlap
    
    Rationale:
    1. 512 chars is approximately 100-128 tokens, fitting well within embedding 
       model context windows while maintaining semantic coherence
    2. This size captures roughly 1-2 paragraphs, preserving contextual meaning
    3. The 50-char overlap (~10%) ensures important context at chunk boundaries 
       isn't lost, improving retrieval recall for questions spanning chunk borders
    4. Smaller chunks (256) fragment meaning; larger chunks (1024+) dilute 
       relevance signals and reduce retrieval precision
    
    Trade-off: Larger chunks provide more context but may include irrelevant 
    information; smaller chunks are more precise but may miss context.
    """
    
    # Separators in order of preference (paragraph > sentence > word > char)
    SEPARATORS = ["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " ", ""]
    
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        """
        Initialize the chunker
        
        Args:
            chunk_size: Target size for each chunk in characters
            chunk_overlap: Number of overlapping characters between chunks
        """
        if chunk_overlap >= chunk_size:
            raise ValueError("Chunk overlap must be less than chunk size")
        
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        logger.info(f"TextChunker initialized: size={chunk_size}, overlap={chunk_overlap}")
    
    def chunk_text(self, text: str) -> List[TextChunk]:
        """
        Split text into chunks
        
        Args:
            text: Input text to chunk
            
        Returns:
            List of TextChunk objects
        """
        if not text or not text.strip():
            return []
        
        # Clean text - normalize whitespace but preserve paragraph structure
        text = self._clean_text(text)
        
        # Split recursively
        splits = self._recursive_split(text, self.SEPARATORS)
        
        # Merge small chunks and apply overlap
        chunks = self._merge_splits_with_overlap(splits)
        
        # Create TextChunk objects with position tracking
        result = []
        current_pos = 0
        
        for idx, chunk_content in enumerate(chunks):
            # Find actual position in original text
            start = text.find(chunk_content[:50], current_pos)
            if start == -1:
                start = current_pos
            
            result.append(TextChunk(
                content=chunk_content,
                start_char=start,
                end_char=start + len(chunk_content),
                chunk_index=idx
            ))
            
            # Move position forward, accounting for overlap
            current_pos = max(start + len(chunk_content) - self.chunk_overlap, current_pos + 1)
        
        logger.info(f"Created {len(result)} chunks from {len(text)} characters")
        return result
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text while preserving structure"""
        # Replace multiple spaces with single space
        text = re.sub(r' +', ' ', text)
        # Replace multiple newlines with double newline
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Strip leading/trailing whitespace
        return text.strip()
    
    def _recursive_split(self, text: str, separators: List[str]) -> List[str]:
        """Recursively split text using separators in order of preference"""
        if not separators:
            # Base case: just return characters
            return list(text)
        
        separator = separators[0]
        remaining_separators = separators[1:]
        
        if not separator:
            # Empty separator means split by character
            return list(text)
        
        # Split by current separator
        splits = text.split(separator)
        
        result = []
        for split in splits:
            if len(split) <= self.chunk_size:
                if split.strip():
                    # Add separator back except for last split
                    result.append(split.strip())
            else:
                # Recursively split with finer separators
                sub_splits = self._recursive_split(split, remaining_separators)
                result.extend(sub_splits)
        
        return result
    
    def _merge_splits_with_overlap(self, splits: List[str]) -> List[str]:
        """Merge small splits and apply overlap between chunks"""
        if not splits:
            return []
        
        chunks = []
        current_chunk = []
        current_length = 0
        
        for split in splits:
            split_length = len(split)
            
            # Check if adding this split would exceed chunk size
            if current_length + split_length + 1 > self.chunk_size and current_chunk:
                # Save current chunk
                chunk_text = " ".join(current_chunk)
                chunks.append(chunk_text)
                
                # Calculate overlap - keep last portion for next chunk
                overlap_text = self._get_overlap_text(chunk_text)
                
                if overlap_text:
                    current_chunk = [overlap_text, split]
                    current_length = len(overlap_text) + split_length + 1
                else:
                    current_chunk = [split]
                    current_length = split_length
            else:
                current_chunk.append(split)
                current_length += split_length + (1 if current_chunk else 0)
        
        # Don't forget the last chunk
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        return chunks
    
    def _get_overlap_text(self, text: str) -> str:
        """Get the overlap portion from the end of a chunk"""
        if len(text) <= self.chunk_overlap:
            return text
        
        # Try to break at a word boundary within overlap window
        overlap_portion = text[-self.chunk_overlap:]
        space_idx = overlap_portion.find(" ")
        
        if space_idx != -1:
            return overlap_portion[space_idx + 1:]
        
        return overlap_portion
