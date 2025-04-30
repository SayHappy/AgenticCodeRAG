# File Chunker

A package for intelligently chunking code files based on semantic structure and language-specific patterns.

## Overview

This package provides a framework for dividing source code files into semantic chunks that preserve code context. It uses tree-sitter for syntax-aware chunking and supports various programming languages.

The chunker takes into account language-specific features such as:
- Code structure (classes, functions, methods)
- Import statements and preambles
- Special syntax elements for different languages and frameworks
- Chunk size and quality heuristics

## Usage

```python
from script.file_chunker import chunk_file

# Basic usage - chunk a file
chunks = chunk_file("path/to/your/file.py")

# With optional parameters
chunks = chunk_file(
    "path/to/your/file.py",
    max_chars=4000,  # Override maximum chunk size
    coalesce_chars=1000,  # Override minimum size for chunks not to be merged
    verbose=True  # Show detailed logging
)

# Process the chunks
for chunk in chunks:
    print(f"Chunk from lines {chunk.start_line}-{chunk.end_line-1}")
    print(f"Chunk type: {chunk.chunk_type}")
    print(chunk.text)
```

## Command-line Interface

The package also provides a command-line interface:

```bash
# List supported languages and file extensions
python -m script.file_chunker.main --list

# Chunk a file with verbose output
python -m script.file_chunker.main path/to/your/file.py -v

# Override chunk size parameters
python -m script.file_chunker.main path/to/your/file.py --max-chars 4000 --coalesce-chars 1000
```

## Extending

To add support for additional languages or specialized chunking logic:

1. Create a custom chunker by extending the `BaseChunker` class
2. Register your chunker in the `__init_chunkers__.py` file

## Package Structure

- `main.py` - Main entry point and API
- `models.py` - Data models (Span, ChunkInfo)
- `base_chunker.py` - Base interfaces and registry
- `core_chunker.py` - Core chunking implementation 
- `utils.py` - Utility functions
- `language_configs.py` - Language-specific configurations
- `__init_chunkers__.py` - Registration of chunkers 

## Parser Integration

The chunker now integrates with the file parser module to annotate chunks with language-specific code elements. When both modules are available, each chunk will include information about the code structures it contains, such as:

- Classes, methods, and functions
- Imports and variable declarations
- Other language-specific elements

This integration helps provide richer context for each chunk, making it easier to understand what parts of the codebase are contained in each chunk.

```python
# Example output showing parser fragments
--- Chunk 2 (CODE) [spring] (Lines 32-100) ---

Parser fragments in this chunk:
Classes
  └── LLMCqService (Lines: 32-182)
Methods
  └── startAnalysis (Lines: 40-62)
  └── getAnalysisStatus (Lines: 65-100)
```

### Using Parser Integration

The parser integration works automatically when both modules are available. If the file parser module is not found, the chunker will continue to work without the additional annotations.

To access the parser fragments for a chunk:

```python
from script.file_chunker import chunk_file

chunks = chunk_file("path/to/your/file.java")

for chunk in chunks:
    # Access parser fragments directly
    for fragment in chunk.parser_fragments:
        print(f"{fragment.name} ({fragment.type_info}): Lines {fragment.line}-{fragment.end_line}")
    
    # Or use the built-in formatter
    formatted_fragments = chunk.format_parser_fragments()
    print(formatted_fragments)
``` 