#!/usr/bin/env python3
"""
Base chunker module defining the abstract base classes for language-specific
code chunking implementations.
"""
import abc
from pathlib import Path
from typing import List, Dict, Any, Optional

from .models import Span, ChunkInfo


class BaseChunker(abc.ABC):
    """Abstract base class for language-specific code chunking."""
    
    @abc.abstractmethod
    def chunk_code(self, code: str, file_path: str, max_chars: Optional[int] = None,
                  coalesce_chars: Optional[int] = None, verbose: bool = False) -> List[Span]:
        """
        Chunks the given code string based on syntax structure.
        
        Args:
            code: The source code as a string.
            file_path: The path to the file (used to determine language).
            max_chars: The approximate maximum number of characters per chunk.
            coalesce_chars: Minimum non-whitespace characters for a chunk to not be merged.
            verbose: If True, print verbose logging.
            
        Returns:
            A list of Span objects representing the line ranges of the chunks.
        """
        pass
    
    @abc.abstractmethod
    def create_chunk_infos(self, spans: List[Span], code: str, file_path: str) -> List[ChunkInfo]:
        """
        Create ChunkInfo objects from spans with enhanced metadata.
        
        Args:
            spans: A list of Span objects.
            code: The source code as a string.
            file_path: The path to the file.
            
        Returns:
            A list of ChunkInfo objects with metadata.
        """
        pass
    
    @abc.abstractmethod
    def parse_file_with_summary(self, file_path: str, max_chars: Optional[int] = None,
                               coalesce_chars: Optional[int] = None, verbose: bool = False) -> Dict[str, Any]:
        """
        Parse a file and generate both chunks and a comprehensive file summary in a single efficient pass.
        
        Args:
            file_path: Path to the file to process
            max_chars: The approximate maximum number of characters per chunk
            coalesce_chars: Minimum non-whitespace characters for a chunk to not be merged
            verbose: Whether to print verbose output
            
        Returns:
            Dictionary containing:
                - chunks: List of ChunkInfo objects
                - summary: Dictionary with file summary information
                - structure: Hierarchical representation of file structure
                - metadata: Additional file metadata
        """
        pass
    
    @abc.abstractmethod
    def get_file_extensions(self) -> List[str]:
        """
        Get the list of file extensions supported by this chunker.
        
        Returns:
            A list of file extensions (including the dot, e.g. ['.py', '.pyw']).
        """
        pass
    
    @abc.abstractmethod
    def get_language_name(self) -> str:
        """
        Get the name of the language supported by this chunker.
        
        Returns:
            The language name.
        """
        pass


class ChunkerRegistry:
    """Registry for language-specific chunkers."""
    _chunkers = {}
    
    @classmethod
    def register(cls, chunker: BaseChunker):
        """
        Register a language-specific chunker.
        
        Args:
            chunker: The chunker to register.
        """
        language_name = chunker.get_language_name()
        cls._chunkers[language_name] = chunker
        
        # Also register by file extension for easy lookup
        for ext in chunker.get_file_extensions():
            # Make sure the extension is a string (hashable)
            if not isinstance(ext, str):
                print(f"[Warning] Invalid extension type: {type(ext)} for {ext}. Extensions must be strings.")
                continue
                
            cls._chunkers[ext] = chunker
    
    @classmethod
    def get_chunker_for_file(cls, file_path: str) -> Optional[BaseChunker]:
        """
        Get the appropriate chunker for a file.
        
        Args:
            file_path: Path to the file.
            
        Returns:
            The appropriate BaseChunker or None if no chunker is found.
        """
        ext = Path(file_path).suffix.lower()
        return cls._chunkers.get(ext)
    
    @classmethod
    def get_chunker_by_language(cls, language_name: str) -> Optional[BaseChunker]:
        """
        Get a chunker by language name.
        
        Args:
            language_name: Name of the language.
            
        Returns:
            The language chunker or None if not found.
        """
        return cls._chunkers.get(language_name)
    
    @classmethod
    def available_languages(cls) -> List[str]:
        """
        Get the list of available chunker language names.
        
        Returns:
            A list of language names.
        """
        # Only return actual language names, not extensions
        return [name for name in cls._chunkers.keys() 
                if not name.startswith('.')] 