#!/usr/bin/env python3
"""
Base parser module defining the abstract factory pattern interfaces
for language-specific AST parsing and code element detection.
"""
import abc
from pathlib import Path
from collections import namedtuple
from typing import List, Dict, Any, Optional, Tuple

# Base Tag structure
Tag = namedtuple("Tag", "rel_fname fname line name kind")
# Tag with end_line
TagWithEndLine = namedtuple('TagWithEndLine', Tag._fields + ('end_line',))
# Base class for language-specific tags
BaseExtendedTag = namedtuple("BaseExtendedTag", "rel_fname fname line end_line name kind type_info")

class ElementDetector(abc.ABC):
    """Abstract base class for language-specific element detection"""
    
    @abc.abstractmethod
    def detect_elements(self, file_path: str, verbose: bool = False) -> List[Any]:
        """Detect language-specific elements in the given file
        
        Args:
            file_path: Path to the file to analyze
            verbose: Whether to print verbose information
            
        Returns:
            List of detected elements as ExtendedTag objects
        """
        pass

    @property
    @abc.abstractmethod
    def element_types(self) -> List[str]:
        """Get the list of element types supported by this detector"""
        pass
    
    @property
    @abc.abstractmethod
    def type_display_config(self) -> Dict[str, Dict[str, str]]:
        """Get the display configuration for each element type
        
        Returns:
            Dictionary mapping element types to display properties:
            {
                "type_name": {
                    "title": "Display Title",
                    "color": "display_color"
                }
            }
        """
        pass
    
    @property
    @abc.abstractmethod
    def display_order(self) -> List[str]:
        """Get the order in which element types should be displayed"""
        pass


class LanguageParser(abc.ABC):
    """Abstract factory for language-specific parsing"""
    
    @abc.abstractmethod
    def create_element_detector(self) -> ElementDetector:
        """Create a language-specific element detector"""
        pass
    
    @abc.abstractmethod
    def get_file_extensions(self) -> List[str]:
        """Get the list of file extensions supported by this parser"""
        pass
    
    @abc.abstractmethod
    def get_language_name(self) -> str:
        """Get the name of the language supported by this parser"""
        pass
    
    @staticmethod
    def convert_tag_to_extended(tag: Tag, type_info: str) -> BaseExtendedTag:
        """Convert a standard Tag to an ExtendedTag with type information
        
        Args:
            tag: The standard Tag object
            type_info: The language-specific type information
            
        Returns:
            An ExtendedTag with the additional type information
        """
        if hasattr(tag, 'end_line'):
            end_line = tag.end_line
        else:
            end_line = tag.line
            
        return BaseExtendedTag(
            rel_fname=tag.rel_fname,
            fname=tag.fname,
            line=tag.line,
            end_line=end_line,
            name=tag.name,
            kind=tag.kind,
            type_info=type_info
        )


class ParserRegistry:
    """Registry for language parsers"""
    _parsers = {}
    
    @classmethod
    def register(cls, parser: LanguageParser):
        """Register a language parser
        
        Args:
            parser: The language parser to register
        """
        extensions = parser.get_file_extensions()
        language_name = parser.get_language_name()
        cls._parsers[language_name] = parser
        
        # Also register by file extension for easy lookup
        for ext in extensions:
            cls._parsers[ext] = parser
    
    @classmethod
    def get_parser_for_file(cls, file_path: str) -> Optional[LanguageParser]:
        """Get the appropriate parser for a file
        
        Args:
            file_path: Path to the file
            
        Returns:
            The appropriate LanguageParser or None if no parser is found
        """
        ext = Path(file_path).suffix.lower()
        return cls._parsers.get(ext)
    
    @classmethod
    def get_parser_by_name(cls, language_name: str) -> Optional[LanguageParser]:
        """Get a parser by language name
        
        Args:
            language_name: Name of the language
            
        Returns:
            The language parser or None if not found
        """
        return cls._parsers.get(language_name)
    
    @classmethod
    def available_parsers(cls) -> List[str]:
        """Get the list of available parser language names"""
        # Only return actual language names, not extensions
        return [name for name in cls._parsers.keys() 
                if not name.startswith('.')] 