#!/usr/bin/env python3
"""
Main module for code file chunking with language-specific processing.
"""
import argparse
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

from .models import Span, ChunkInfo
from .base_chunker import ChunkerRegistry
from .utils import display_chunks
import json

# Ensure all language configs and chunkers are registered
from . import language_configs
from . import __init_chunkers__

def chunk_file(file_path: str, max_chars: Optional[int] = None, 
              coalesce_chars: Optional[int] = None, verbose: bool = False) -> List[ChunkInfo]:
    """Chunk a single file using the appropriate chunker.
    
    Args:
        file_path: Path to the file to chunk
        max_chars: Maximum characters per chunk (overrides language default)
        coalesce_chars: Minimum characters for chunks to not be coalesced (overrides language default)
        verbose: Whether to print verbose information
        
    Returns:
        A list of ChunkInfo objects containing chunks and metadata
    """
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        print(f"[Error] File not found: {file_path}")
        return []

    # Get the chunker for this file type
    chunker = ChunkerRegistry.get_chunker_for_file(file_path)
    if not chunker:
        print(f"[Warning] Unsupported file type: {path.suffix}")
        return []
    
    # Read the file content
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            file_content = f.read()
    except Exception as e:
        print(f"[Error] Failed to read file {file_path}: {e}")
        return []
    
    # Generate the chunks
    spans = chunker.chunk_code(
        file_content, 
        file_path, 
        max_chars=max_chars, 
        coalesce_chars=coalesce_chars, 
        verbose=verbose
    )
    
    # Create ChunkInfo objects with metadata
    chunk_infos = chunker.create_chunk_infos(spans, file_content, file_path)
    
    if verbose:
        print(f"[Info] Generated {len(chunk_infos)} chunks for {file_path}")
    
    return chunk_infos

def parse_file(file_path: str, max_chars: Optional[int] = None,
              coalesce_chars: Optional[int] = None, verbose: bool = False) -> Dict[str, Any]:
    """
    Parse a file and generate both chunks and a comprehensive file summary in a single efficient pass.
    This is the main entry point for external code to parse files with the chunker system.
    
    Args:
        file_path: Path to the file to process
        max_chars: Maximum characters per chunk (overrides language default)
        coalesce_chars: Minimum characters for chunks to not be coalesced (overrides language default)
        verbose: Whether to print verbose information
        
    Returns:
        Dictionary containing:
            - chunks: List of ChunkInfo objects
            - summary: Dictionary with file summary information
            - structure: Hierarchical representation of file structure
            - metadata: Additional file metadata
    """
    # Import the implementation from core_chunker to avoid circular imports
    try:
        from .core_chunker import parse_file_with_summary
        return parse_file_with_summary(file_path, max_chars, coalesce_chars, verbose)
    except ImportError:
        if verbose:
            print("[Warning] Could not import parse_file_with_summary from core_chunker.")
        
        # Fallback implementation using chunk_file
        chunks = chunk_file(file_path, max_chars, coalesce_chars, verbose)
        return {
            "chunks": chunks,
            "summary": {
                "filename": Path(file_path).name,
                "total_chunks": len(chunks)
            },
            "structure": {},
            "metadata": {}
        }

def get_available_languages() -> List[str]:
    """Get a list of supported languages for chunking."""
    return ChunkerRegistry.available_languages()

def main():
    """Main entry point for the chunker CLI."""
    parser = argparse.ArgumentParser(description="Intelligent code file chunker")
    parser.add_argument("file_path", help="Path to the file to chunk", nargs="?")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show verbose output")
    parser.add_argument("-l", "--list", action="store_true", help="List supported languages and file extensions")
    parser.add_argument("--max-chars", type=int, default=1000, 
                        help="Maximum characters per chunk (default: 1000)")
    parser.add_argument("--coalesce-chars", type=int, default=300, 
                        help="Minimum non-whitespace characters for chunks to not be merged (default: 300, higher values = larger chunks)")
    parser.add_argument("--parse-mode", action="store_true", help="Use parse_file instead of chunk_file (includes file summary and structure)")
    args = parser.parse_args()
    
    print("[Intelligent Code File Chunker]")
    print("-" * 50)
    
    if args.list:
        print("Supported languages and file extensions:")
        for lang in ChunkerRegistry.available_languages():
            chunker = ChunkerRegistry.get_chunker_by_language(lang)
            if chunker:
                exts = ", ".join(chunker.get_file_extensions())
                print(f"- {lang}: {exts}")
        return
    
    if not args.file_path:
        parser.print_help()
        return
    
    # Print parameter information
    if args.verbose:
        print(f"Using parameters: max_chars={args.max_chars}, coalesce_chars={args.coalesce_chars}")
    
    if args.parse_mode:
        # Use parse_file with summary when parse mode is specified
        result = parse_file(
            args.file_path,
            max_chars=args.max_chars,
            coalesce_chars=args.coalesce_chars,
            verbose=args.verbose
        )
        
        if result["chunks"]:
            # Display the file summary information
            print("\nFile Summary:")
            for key, value in result["summary"].items():
                if isinstance(value, (list, dict)):
                    print(f"- {key}: (complex data, length: {len(value)})")
                else:
                    print(f"- {key}: {value}")
            
            # Display the formatted file structure
            if "formatted_structure" in result:
                print("\nFile Structure:")
                print(result["formatted_structure"])
                    
            result["chunks"] = [chunk for chunk in result["chunks"] if chunk.text]
            # result 写入json
            with open("result.json", "w") as f:
                # Convert ChunkInfo objects to JSON-serializable format
                serializable_result = {
                    "chunks": [chunk.to_json() for chunk in result["chunks"]],
                    "summary": result["summary"],
                    "structure": result["structure"],
                    "metadata": result["metadata"]
                }
                
                # Include formatted structure if available
                if "formatted_structure" in result:
                    serializable_result["formatted_structure"] = result["formatted_structure"]
                    
                json.dump(serializable_result, f)
            
                    
            # Display chunks
            display_chunks(args.file_path, result["chunks"], args.verbose)
    else:
        # Use the original chunk_file behavior
        chunk_infos = chunk_file(
            args.file_path, 
            max_chars=args.max_chars, 
            coalesce_chars=args.coalesce_chars, 
            verbose=args.verbose
        )
        
        if chunk_infos:
            display_chunks(args.file_path, chunk_infos, args.verbose)

if __name__ == "__main__":
    main() 