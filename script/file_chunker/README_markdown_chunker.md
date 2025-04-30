# Markdown Chunker: A Fallback Chunking Mechanism

This module provides a fallback chunking mechanism for files that cannot be processed by the core chunker. It uses the `markitdown` library to convert various file formats to markdown-like text before processing them.

## Key Features

- Handles arbitrary file types by converting them to markdown text
- Automatically detects and skips binary files and very large files
- Chunks markdown content based on headers, code blocks, and other natural boundaries
- Provides rich metadata about the document structure including headers and code blocks
- Seamlessly integrates with the existing chunking system

## How It Works

The markdown chunker works in two main ways:

1. **As a registered chunker** for specific file types (markdown, txt, docs, etc.)
2. **As a fallback mechanism** when the core chunker fails to process a file

The chunking process follows these steps:

1. Check if the file is binary or too large (>50MB) and skip if so
2. Convert the file to markdown text using markitdown or simple format converters
3. Split the content based on natural boundaries (headers, horizontal rules, code blocks)
4. Coalesce small chunks and split large chunks as needed
5. Generate metadata about the document structure (headers, code blocks)

## Supported File Types

The markdown chunker explicitly supports these file types:

- **Markdown**: `.md`, `.markdown`, `.mdown`, `.mkd`, `.mdwn`
- **Documentation**: `.txt`, `.text`, `.rst`, `.adoc`, `.asciidoc`
- **Microsoft Office**: `.doc`, `.docx`, `.xls`, `.xlsx`, `.ppt`, `.pptx`
- **Email**: `.eml`, `.msg`
- **Config files**: `.ini`, `.conf`, `.config`, `.cfg`, `.toml`, `.yaml`, `.yml`, `.json`
- **Other text formats**: `.csv`, `.tsv`, `.log`, `.xml`

It will also attempt to process any other file type when used as a fallback.

## Fallback Mechanism

The core chunker has been enhanced to use the markdown chunker as a fallback in two scenarios:

1. When the core chunker returns empty chunks (no content was successfully parsed)
2. When the core chunker raises an exception while processing a file

When this happens, the system will:
1. Automatically try the markdown chunker
2. Add metadata indicating that the fallback chunker was used
3. Return the results from the markdown chunker if successful
4. Return an error result if both chunkers fail

## Testing the Chunker

You can test the chunker using the provided test script:

```bash
python script/file_chunker/test_markdown_chunker.py /path/to/file -v
```

This will:
1. Attempt to chunk the specified file
2. Display summary information
3. Show details about each generated chunk
4. Indicate if the fallback chunker was used

## Implementation Details

### Key Components

1. **File Detection**: `is_binary_file()` detects if a file is binary or too large
2. **Format Conversion**: `convert_to_markdown()` handles converting various file types to markdown
3. **Chunking Logic**: `chunk_code()` splits content based on natural markdown boundaries
4. **Structure Analysis**: `parse_file_with_summary()` generates comprehensive file structure information

### Directory Structure

```
script/file_chunker/
├── markdown_chunker.py   # Main implementation of the markdown chunker
├── core_chunker.py       # Enhanced with fallback mechanism
├── __init_chunkers__.py  # Updated to register the markdown chunker
└── test_markdown_chunker.py  # Test script for demonstration
```

## Requirements

- `markitdown`: Used for converting various file types to markdown
- Standard Python libraries: `os`, `re`, `pathlib`

## Advantages Over Naive Line-Based Chunking

The markdown chunker offers several advantages over simple line-based chunking:

1. **Semantic Boundaries**: Chunks follow natural document structure (headers, sections)
2. **Rich Metadata**: Provides information about document structure and content types
3. **Content-Aware**: Treats different content types (code blocks, lists, etc.) appropriately
4. **Format Conversion**: Can handle various file formats through conversion to markdown 