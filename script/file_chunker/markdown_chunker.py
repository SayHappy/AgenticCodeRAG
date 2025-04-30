#!/usr/bin/env python3
"""
Markdown chunker implementation for handling files that core chunker can't process.
Serves as a fallback chunking mechanism for arbitrary file types.
"""
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

import tiktoken  # Import tiktoken for token counting
from markitdown import MarkItDown

from .base_chunker import BaseChunker, ChunkerRegistry
from .models import Span, ChunkInfo
from .utils import non_whitespace_len

# Maximum file size for processing (10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024

# Maximum token count for embedding model (1024 tokens)
MAX_TOKENS = 1024

# Tiktoken encoding to use for token counting
ENCODING_NAME = "cl100k_base"  # OpenAI's encoding commonly used with embeddings

# Try to load the tiktoken encoding
try:
    TOKENIZER = tiktoken.get_encoding(ENCODING_NAME)
except Exception as e:
    print(f"[Warning] Failed to load tiktoken encoding: {e}")
    TOKENIZER = None

# Binary file extensions to skip
BINARY_EXTENSIONS = [
    # Images
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".ico", ".webp", ".svg",
    # Audio/Video
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".flv", ".wmv", ".ogg", ".m4a", ".mkv",
    # Compressed
    ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz",
    # Executables
    ".exe", ".dll", ".so", ".dylib", ".bin", ".pyc", ".pyd",
    # Other binary
    ".dat", ".db", ".sqlite", ".pdf"
]

# Mapping of file extensions to approximate markdown converters
FILE_CONVERTERS = {
    # Default for text files
    ".txt": lambda content: content,
    ".md": lambda content: content,
    # Code files - just wrap in code blocks
    ".py": lambda content: "```python\n" + content + "\n```",
    ".js": lambda content: "```javascript\n" + content + "\n```",
    ".ts": lambda content: "```typescript\n" + content + "\n```",
    ".html": lambda content: "```html\n" + content + "\n```",
    ".css": lambda content: "```css\n" + content + "\n```",
    ".java": lambda content: "```java\n" + content + "\n```",
    ".go": lambda content: "```go\n" + content + "\n```",
    ".rs": lambda content: "```rust\n" + content + "\n```",
    ".c": lambda content: "```c\n" + content + "\n```",
    ".cpp": lambda content: "```cpp\n" + content + "\n```",
    ".sh": lambda content: "```bash\n" + content + "\n```",
}


def is_binary_file(file_path: str) -> bool:
    """Check if a file is likely to be binary."""
    # Check by extension first
    ext = Path(file_path).suffix.lower()
    if ext in BINARY_EXTENSIONS:
        return True
        
    # Check file size
    try:
        size = os.path.getsize(file_path)
        if size > MAX_FILE_SIZE:
            print(f"[Warning] File too large to process: {file_path} ({size} bytes)")
            return True
    except Exception as e:
        print(f"[Error] Failed to check file size: {file_path} - {e}")
        return True
    
    # Check content for binary data
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(1024)  # Read first 1KB
            if b'\x00' in chunk:  # Null bytes indicate binary
                return True
            # Additional check for high concentration of non-ASCII chars
            non_text = len([b for b in chunk if b < 9 or (b > 13 and b < 32 and b != 27)])
            if non_text / len(chunk) > 0.3 and len(chunk) > 50:  # >30% non-text chars
                return True
    except Exception as e:
        print(f"[Error] Failed to check if file is binary: {file_path} - {e}")
        return True
    
    return False


def convert_to_markdown(file_path: str) -> str:
    """
    Convert a file to markdown format using markitdown if possible.
    Falls back to simple format converters for common file types.
    """
    try:
        # Use MarkItDown for conversion
        md = MarkItDown(enable_plugins=False)
        return md.convert(file_path).text_content
    except Exception as e:
        # Fall back to simple converters
        try:
            ext = Path(file_path).suffix.lower()
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
                
            converter = FILE_CONVERTERS.get(ext, lambda x: x)
            return converter(content)
        except Exception as e2:
            print(f"[Error] Failed to convert file to markdown: {file_path} - {e2}")
            return f"# Error converting file: {file_path}\n\nError: {e2}"


def count_tokens(text: str) -> int:
    """Count the number of tokens in a text using tiktoken."""
    if TOKENIZER is None:
        # Fallback estimation if tiktoken is not available (assuming ~4 chars per token)
        return len(text) // 4
    try:
        return len(TOKENIZER.encode(text))
    except Exception as e:
        print(f"[Warning] Error counting tokens: {e}")
        return len(text) // 4  # Fallback estimation


class MarkdownChunker(BaseChunker):
    """
    Markdown chunker implementation for handling arbitrary files.
    Converts files to markdown-like format before chunking.
    """
    
    def get_language_name(self) -> str:
        """Get the name of this chunker."""
        return "markdown"
    
    def get_file_extensions(self) -> List[str]:
        """Get supported file extensions - this is a fallback chunker so it supports everything."""
        # Return common text/document formats that core chunker might not handle well
        return [
            # Markdown
            ".md", ".markdown", ".mdown", ".mkd", ".mdwn",
            # Documentation
            ".txt", ".text", ".rst", ".adoc", ".asciidoc",
            # Microsoft Office
            ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
            # Email
            ".eml", ".msg",
            # Config files
            ".ini", ".conf", ".config", ".cfg", ".toml", ".yaml", ".yml", ".json",
            # Other text formats
            ".csv", ".tsv", ".log", ".xml"
        ]
    
    def chunk_code(self, code: str, file_path: str, max_tokens: Optional[int] = None,
                  coalesce_tokens: Optional[int] = None, verbose: bool = False) -> List[Span]:
        """
        Chunks the given markdown or text content based on headers and content blocks.
        
        Args:
            code: The markdown content as a string.
            file_path: The path to the file.
            max_tokens: The maximum number of tokens per chunk.
            coalesce_tokens: Minimum tokens for a chunk to not be merged.
            verbose: If True, print verbose logging.
            
        Returns:
            A list of Span objects representing the line ranges of the chunks.
        """
        # Default values
        max_tokens = max_tokens or MAX_TOKENS
        coalesce_tokens = coalesce_tokens or MAX_TOKENS // 3  # About 1/3 of max tokens
        
        if verbose:
            print(f"[Info] Chunking markdown content for {file_path}")
        
        # Split content into lines
        lines = code.splitlines()
        if not lines:
            if verbose:
                print(f"[Warning] Empty content in {file_path}")
            return []
        
        # Find potential chunk boundaries (headers, horizontal rules, etc.)
        boundaries = []
        header_pattern = re.compile(r'^#{1,6}\s+.+$')
        
        # Add first line as a boundary
        boundaries.append(0)
        
        # Find headers and other natural boundaries
        for i, line in enumerate(lines):
            # Headers - markdown style
            if header_pattern.match(line):
                boundaries.append(i)
            # Horizontal rules
            elif re.match(r'^[-*_]{3,}\s*$', line):
                boundaries.append(i)
            # Code block start/end
            elif line.strip().startswith('```'):
                boundaries.append(i)
        
        # Add the last line + 1 as a boundary
        if len(lines) not in boundaries:
            boundaries.append(len(lines))
        
        # Sort boundaries to ensure they're in order
        boundaries = sorted(boundaries)
        
        # Generate initial spans based on boundaries
        initial_spans = []
        for i in range(len(boundaries) - 1):
            start = boundaries[i]
            end = boundaries[i + 1]
            
            if end > start:  # Only add non-empty spans
                initial_spans.append(Span(start, end))
        
        # Improved coalescing algorithm
        # First pass: Collect all spans with their token counts
        spans_with_size = []
        for span in initial_spans:
            span_text = "\n".join(lines[span.start:span.end])
            token_count = count_tokens(span_text)
            spans_with_size.append((span, token_count))
        
        # Second pass: Coalesce small spans more aggressively
        final_spans = []
        current_span = None
        current_token_count = 0
        
        for span, token_count in spans_with_size:
            if current_span is None:
                current_span = span
                current_token_count = token_count
            elif token_count < coalesce_tokens or current_token_count < coalesce_tokens:
                # This span or the current span is small, merge them if total tokens will be under limit
                if current_token_count + token_count <= max_tokens:
                    current_span = Span(current_span.start, span.end)
                    current_token_count += token_count
                    
                    # Check if the combined span is now big enough
                    if current_token_count >= coalesce_tokens:
                        final_spans.append(current_span)
                        current_span = None
                        current_token_count = 0
                else:
                    # Would exceed token limit, finalize current span and start a new one
                    final_spans.append(current_span)
                    current_span = span
                    current_token_count = token_count
            else:
                # Both spans are large enough, finalize the current one and start a new one
                final_spans.append(current_span)
                current_span = span
                current_token_count = token_count
            
            # Check if the current span is too large (by tokens)
            if current_span and current_token_count > max_tokens:
                # Split the large span at a reasonable point
                split_point = self._find_split_point(lines, current_span.start, current_span.end, max_tokens)
                
                if split_point > current_span.start:
                    final_spans.append(Span(current_span.start, split_point))
                    current_span = Span(split_point, current_span.end)
                    # Recalculate tokens for the new current span
                    current_text = "\n".join(lines[current_span.start:current_span.end])
                    current_token_count = count_tokens(current_text)
        
        # Add the last span if not empty
        if current_span and current_span.end > current_span.start:
            final_spans.append(current_span)
        
        # If we have no spans, create a single span for the whole file
        if not final_spans and lines:
            final_spans = [Span(0, len(lines))]
        
        if verbose:
            print(f"[Info] Generated {len(final_spans)} chunks for {file_path} (coalesce_tokens={coalesce_tokens})")
            
        return final_spans
    
    def _find_split_point(self, lines: List[str], start: int, end: int, max_tokens: int) -> int:
        """Find a good point to split a large chunk."""
        # Try to find natural split points (headers or empty lines) that keep chunks under token limit
        for i in range(start + 1, end):
            # Check for headers - preferred split points
            if re.match(r'^#{1,6}\s+.+$', lines[i]):
                # Check if text up to this point is under the token limit
                candidate_text = "\n".join(lines[start:i])
                if count_tokens(candidate_text) <= max_tokens:
                    return i
            # Check for empty lines - second best split points
            if not lines[i].strip():
                candidate_text = "\n".join(lines[start:i+1])
                if count_tokens(candidate_text) <= max_tokens:
                    return i + 1  # Split after the empty line
        
        # If no natural split points work, do a token-based binary search to find the best point
        left, right = start + 1, end - 1
        while left <= right:
            mid = (left + right) // 2
            candidate_text = "\n".join(lines[start:mid])
            token_count = count_tokens(candidate_text)
            
            if token_count <= max_tokens:
                # Can include more lines
                if mid == end - 1 or count_tokens("\n".join(lines[start:mid+1])) > max_tokens:
                    return mid
                left = mid + 1
            else:
                # Too many tokens, need to reduce
                right = mid - 1
        
        # Fallback - return a point that's 90% of max_tokens
        for i in range(start + 1, end):
            candidate_text = "\n".join(lines[start:i])
            if count_tokens(candidate_text) >= max_tokens * 0.9:
                return i
                
        # If all else fails, just return halfway between start and end
        return start + (end - start) // 2
    
    def create_chunk_infos(self, spans: List[Span], code: str, file_path: str) -> List[ChunkInfo]:
        """Create ChunkInfo objects from spans with enhanced metadata."""
        chunk_infos = []
        lines = code.splitlines()
        
        for span in spans:
            # Extract chunk text
            chunk_text = "\n".join(lines[span.start:span.end])
            
            # Extract title from the first header in the chunk, if any
            title = self._extract_title(chunk_text) or f"Chunk {span.start}-{span.end}"
            
            # Analyze the chunk to determine its type
            chunk_type = self._determine_chunk_type(chunk_text)
            
            # Count tokens for the chunk
            token_count = count_tokens(chunk_text)
            
            # Create ChunkInfo object
            chunk_info = ChunkInfo(
                span=span,
                text=chunk_text,
                chunk_type=chunk_type,
                metadata={
                    "title": title,
                    "non_whitespace_len": non_whitespace_len(chunk_text),
                    "line_count": span.end - span.start,
                    "has_code_blocks": '```' in chunk_text,
                    "token_count": token_count
                },
                parser_fragments=[]  # No parser fragments for markdown
            )
            
            chunk_infos.append(chunk_info)
            
        return chunk_infos
    
    def _extract_title(self, text: str) -> Optional[str]:
        """Extract a title from the first header in the text."""
        lines = text.splitlines()
        for line in lines:
            # Check for a markdown header
            header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if header_match:
                return header_match.group(2).strip()
        return None
    
    def _determine_chunk_type(self, text: str) -> str:
        """Determine the type of the chunk based on its content."""
        # Check for code blocks
        if '```' in text:
            return "code_block"
            
        # Check for headers
        if re.search(r'^#{1,6}\s+.+$', text, re.MULTILINE):
            return "section"
            
        # Check for lists
        if re.search(r'^[-*+]\s+.+$', text, re.MULTILINE):
            return "list"
            
        # Default to text
        return "text"
    
    def parse_file_with_summary(self, file_path: str, max_tokens: Optional[int] = None,
                               coalesce_tokens: Optional[int] = None, verbose: bool = False) -> Dict[str, Any]:
        """
        Parse a file and generate both chunks and a comprehensive file summary in a single efficient pass.
        
        Args:
            file_path: Path to the file to process
            max_tokens: The maximum number of tokens per chunk
            coalesce_tokens: Minimum tokens for a chunk to not be merged
            verbose: Whether to print verbose output
            
        Returns:
            Dictionary containing:
                - chunks: List of ChunkInfo objects
                - summary: Dictionary with file summary information
                - structure: Hierarchical representation of file structure
                - metadata: Additional file metadata
        """
        # Default values - explicitly set them here to ensure consistency
        max_tokens = max_tokens or MAX_TOKENS
        coalesce_tokens = coalesce_tokens or MAX_TOKENS // 3
        
        if verbose:
            print(f"[Info] Processing file: {file_path} (max_tokens={max_tokens}, coalesce_tokens={coalesce_tokens})")
            
        # Check if the file is binary or too large
        if is_binary_file(file_path):
            if verbose:
                print(f"[Warning] Skipping binary or large file: {file_path}")
            return {
                "chunks": [],
                "summary": {
                    "filename": os.path.basename(file_path),
                    "filepath": file_path,
                    "language": "binary",
                    "total_lines": 0,
                    "total_chunks": 0,
                    "total_elements": 0,
                    "skipped": True,
                    "reason": "Binary or large file"
                },
                "structure": {},
                "metadata": {"error": "Binary or large file"}
            }
        
        try:
            # Convert the file to markdown
            markdown_content = convert_to_markdown(file_path)
            
            # Count the total lines
            lines = markdown_content.splitlines()
            total_lines = len(lines)
            
            # Generate chunks
            spans = self.chunk_code(markdown_content, file_path, max_tokens, coalesce_tokens, verbose)
            chunk_infos = self.create_chunk_infos(spans, markdown_content, file_path)
            
            # Extract headers to build structure
            headers = []
            for i, line in enumerate(lines):
                header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
                if header_match:
                    level = len(header_match.group(1))
                    text = header_match.group(2).strip()
                    headers.append({
                        "level": level,
                        "text": text,
                        "line": i
                    })
            
            # Calculate total token count for the file
            total_tokens = count_tokens(markdown_content)
            
            # Create summary
            summary = {
                "filename": os.path.basename(file_path),
                "filepath": file_path,
                "language": "markdown",
                "total_lines": total_lines,
                "total_chunks": len(chunk_infos),
                "total_elements": len(headers),
                "total_tokens": total_tokens,
                "converter": "markitdown",
                "parameters": {
                    "max_tokens": max_tokens,
                    "coalesce_tokens": coalesce_tokens
                }
            }
            
            # Build a hierarchical structure based on headers
            structure = {
                "headers": headers,
                "code_blocks": []
            }
            
            # Detect code blocks
            in_code_block = False
            code_block_start = 0
            code_block_lang = ""
            
            for i, line in enumerate(lines):
                if line.strip().startswith("```"):
                    if not in_code_block:
                        in_code_block = True
                        code_block_start = i
                        code_block_lang = line.strip()[3:].strip()
                    else:
                        in_code_block = False
                        structure["code_blocks"].append({
                            "start": code_block_start,
                            "end": i,
                            "language": code_block_lang
                        })
            
            # Format the structure into a tree-like representation
            formatted_structure = self._format_structure(file_path, headers, structure["code_blocks"])
            
            return {
                "chunks": chunk_infos,
                "summary": summary,
                "structure": structure,
                "metadata": {
                    "headers": len(headers), 
                    "code_blocks": len(structure["code_blocks"]),
                    "token_counts": [info.metadata["token_count"] for info in chunk_infos]
                },
                "formatted_structure": formatted_structure
            }
        
        except Exception as e:
            if verbose:
                print(f"[Error] Failed to process file {file_path}: {e}")
            return {
                "chunks": [],
                "summary": {
                    "filename": os.path.basename(file_path),
                    "filepath": file_path,
                    "language": "unknown",
                    "error": str(e)
                },
                "structure": {},
                "metadata": {"error": str(e)}
            }
    
    def _format_structure(self, file_path: str, headers: List[Dict[str, Any]], code_blocks: List[Dict[str, Any]]) -> str:
        """Format the file structure data into a tree-like string representation."""
        result = [file_path]
        
        if headers:
            result.append("├── Headers")
            for i, header in enumerate(headers):
                is_last = i == len(headers) - 1 and not code_blocks
                prefix = "    " if is_last else "│   "
                tree_char = "└── " if is_last else "├── "
                level_indicator = "#" * header["level"]
                result.append(f"{prefix}{tree_char}{level_indicator} {header['text']} (Line: {header['line'] + 1})")
        
        if code_blocks:
            result.append("└── Code Blocks")
            for i, block in enumerate(code_blocks):
                is_last = i == len(code_blocks) - 1
                prefix = "    " if is_last else "│   "
                tree_char = "└── " if is_last else "├── "
                lang = f"[{block['language']}] " if block['language'] else ""
                result.append(f"{prefix}{tree_char}{lang}Code Block (Lines: {block['start'] + 1}-{block['end'] + 1})")
        
        return "\n".join(result)


# Register the chunker
ChunkerRegistry.register(MarkdownChunker()) 