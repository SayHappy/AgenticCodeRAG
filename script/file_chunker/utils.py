#!/usr/bin/env python3
"""
Utility functions for the file chunker package.
"""
import re
from typing import List, Dict, Any, Union

from .models import ChunkInfo

def non_whitespace_len(s: Union[str, bytes]) -> int:
    """Calculates the length of the string/bytes excluding whitespace."""
    if isinstance(s, bytes):
        s = s.decode('utf-8', errors='ignore')  # Decode safely
    return len(re.sub(r"\s", "", s))

def get_line_number(byte_index: int, source_code: bytes) -> int:
    """Converts a byte index to a 0-indexed line number."""
    total_bytes = 0
    line_number = 0
    # Use splitlines(True) to keep newline characters for accurate byte counting
    lines = source_code.splitlines(True) 
    for i, line_bytes in enumerate(lines):
        if total_bytes + len(line_bytes) > byte_index:
            return i  # Return 0-indexed line number
        total_bytes += len(line_bytes)
    # If byte_index is at or beyond the end, return the last line number
    return len(lines) - 1 if lines else 0

def display_chunks(file_path: str, chunks: List[ChunkInfo], verbose: bool = False):
    """
    Display information about the generated chunks.
    
    Args:
        file_path: Path to the file
        chunks: List of ChunkInfo objects
        verbose: Whether to show detailed chunk information
    """
    print(f"\n--- Generated {len(chunks)} Chunks for {file_path} ---")
    
    for i, chunk in enumerate(chunks):
        # Create a descriptive chunk type label
        chunk_type_str = f" ({chunk.chunk_type.upper()})"
        
        # Add framework info if available
        framework = chunk.metadata.get("framework")
        if framework:
            chunk_type_str += f" [{framework}]"
            
        # Add special pattern matches if any
        special_matches = chunk.metadata.get("special_matches", {})
        if special_matches:
            special_types = list(special_matches.keys())
            if special_types:
                chunk_type_str += f" ({', '.join(special_types)})"
        
        print(f"\n--- Chunk {i+1}{chunk_type_str} (Lines {chunk.start_line}-{chunk.end_line-1}) ---")
        
        # Display parser fragments if available
        parser_fragments_str = chunk.format_parser_fragments()
        if parser_fragments_str:
            print("\nParser fragments in this chunk:")
            print(parser_fragments_str)
        
        if verbose:
            # Print quality score and other metadata
            quality = chunk.metadata.get("quality", 0)
            print(f"[Quality: {quality:.2f}]")
            print(f"[Non-whitespace length: {chunk.metadata.get('non_whitespace_len', 0)}]")
            
            # Print chunk content in verbose mode
            print(chunk.text)
        else:
            # Print just the first few lines in non-verbose mode
            lines = chunk.text.splitlines()
            preview_lines = lines[:10]
            if len(lines) > 3:
                preview_lines.append("...")
            print("\n".join(preview_lines)) 