"""
Document Parser Service
Supports PDF and TXT file formats
"""

import fitz  # PyMuPDF
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class DocumentParseError(Exception):
    """Exception raised when document parsing fails"""
    pass


class DocumentParser:
    """Parses documents and extracts text content"""
    
    SUPPORTED_FORMATS = {".pdf", ".txt"}
    
    @classmethod
    def parse(cls, file_path: str) -> str:
        """
        Parse a document and extract text content
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Extracted text content
            
        Raises:
            DocumentParseError: If parsing fails or format is unsupported
        """
        path = Path(file_path)
        
        if not path.exists():
            raise DocumentParseError(f"File not found: {file_path}")
        
        extension = path.suffix.lower()
        
        if extension not in cls.SUPPORTED_FORMATS:
            raise DocumentParseError(
                f"Unsupported file format: {extension}. "
                f"Supported formats: {', '.join(cls.SUPPORTED_FORMATS)}"
            )
        
        if extension == ".pdf":
            return cls._parse_pdf(file_path)
        elif extension == ".txt":
            return cls._parse_txt(file_path)
        
        raise DocumentParseError(f"Parser not implemented for: {extension}")
    
    @staticmethod
    def _parse_pdf(file_path: str) -> str:
        """
        Extract text from PDF file using PyMuPDF
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Extracted text content
        """
        try:
            text_parts = []
            
            with fitz.open(file_path) as doc:
                for page_num, page in enumerate(doc):
                    try:
                        text = page.get_text("text")
                        if text.strip():
                            text_parts.append(text)
                    except Exception as e:
                        logger.warning(f"Failed to extract text from page {page_num}: {e}")
                        continue
            
            if not text_parts:
                raise DocumentParseError("No text content found in PDF")
            
            return "\n\n".join(text_parts)
            
        except fitz.FileDataError as e:
            raise DocumentParseError(f"Failed to read PDF file: {e}")
        except Exception as e:
            raise DocumentParseError(f"PDF parsing error: {e}")
    
    @staticmethod
    def _parse_txt(file_path: str) -> str:
        """
        Read text from TXT file
        
        Args:
            file_path: Path to TXT file
            
        Returns:
            File text content
        """
        encodings = ["utf-8", "latin-1", "cp1252"]
        
        for encoding in encodings:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    content = f.read()
                    if content.strip():
                        return content
                    raise DocumentParseError("Empty text file")
            except UnicodeDecodeError:
                continue
            except Exception as e:
                raise DocumentParseError(f"Failed to read TXT file: {e}")
        
        raise DocumentParseError("Failed to decode text file with supported encodings")
    
    @classmethod
    def get_supported_formats(cls) -> list:
        """Get list of supported file extensions"""
        return list(cls.SUPPORTED_FORMATS)
