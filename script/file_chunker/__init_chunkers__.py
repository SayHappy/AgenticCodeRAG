#!/usr/bin/env python3
"""
Initialize and register all the chunkers.
"""
from .base_chunker import ChunkerRegistry
from .core_chunker import GenericChunker

# Import our markdown chunker
try:
    from .markdown_chunker import MarkdownChunker
    has_markdown_chunker = True
except ImportError:
    has_markdown_chunker = False
    print("[Warning] Markdown chunker could not be imported. Some files may not be processed correctly.")

# Initialize and register the generic chunker
generic_chunker = GenericChunker()
ChunkerRegistry.register(generic_chunker)

# Register the markdown chunker if available
if has_markdown_chunker:
    markdown_chunker = MarkdownChunker()
    ChunkerRegistry.register(markdown_chunker)

# Add any language-specific chunkers here
# For example:
# from .parsers.python_chunker import PythonChunker
# python_chunker = PythonChunker()
# ChunkerRegistry.register(python_chunker) 