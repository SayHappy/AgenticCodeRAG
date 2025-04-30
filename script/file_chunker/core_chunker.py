#!/usr/bin/env python3
"""
Core implementation of the code chunking functionality.
"""
import re
import os
import traceback
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Union

from grep_ast import filename_to_lang
from grep_ast.tsl import USING_TSL_PACK, get_language, get_parser  # Assuming grep_ast is installed

from .models import Span, ChunkInfo
from .utils import non_whitespace_len, get_line_number
from .base_chunker import BaseChunker
from .language_configs import LANGUAGE_CONFIGS, WEB_FRAMEWORK_PATTERNS

# Import parser registry to get file parsers
try:
    # Try different import approaches
    try:
        # Try relative import first (if within same package structure)
        sys.path.append(str(Path(__file__).parent.parent.parent))
        from script.file_parser.base_parser import ParserRegistry
    except ImportError:
        # Try direct import (assuming package is installed)
        from file_parser.base_parser import ParserRegistry
    PARSERS_AVAILABLE = True
except ImportError:
    PARSERS_AVAILABLE = False
    print("[Warning] file_parser module not available. Parser fragments will not be included in chunks.")


def get_language_config(file_path: str) -> Dict[str, Any]:
    """Get language-specific configuration based on file extension."""
    lang = filename_to_lang(file_path)
    
    # Map from grep_ast language identifiers to our config keys if needed
    lang_mapping = {
        "typescript": "typescript",
        "jsx": "jsx", 
        "tsx": "tsx",
        "javascript": "javascript",
        "typescript.jsx": "jsx",
        "typescript.tsx": "tsx",
        "javascriptreact": "jsx",
        "typescriptreact": "tsx",
        "html": "html",
        "css": "css",
        "java": "java",
        "python": "python",
        "go": "go",
        # Add more mappings as needed
    }
    
    # Get the normalized language key
    config_key = lang_mapping.get(lang, lang)
    
    # Check if there's a language config with an alias
    config = LANGUAGE_CONFIGS.get(config_key, LANGUAGE_CONFIGS["default"])
    if isinstance(config, dict) and "alias" in config:
        config_key = config["alias"]
        config = LANGUAGE_CONFIGS.get(config_key, LANGUAGE_CONFIGS["default"])
    
    return config


def detect_framework(code: str, file_path: str) -> Optional[str]:
    """Detect web framework used in the code."""
    for framework, patterns in WEB_FRAMEWORK_PATTERNS.items():
        indicators = patterns.get("indicators", [])
        for indicator in indicators:
            if re.search(indicator, code, re.MULTILINE):
                return framework
    return None


def preprocess_code(code: str, file_path: str, verbose: bool = False) -> Dict[str, Any]:
    """
    Preprocess code based on language-specific rules.
    Returns a dict with preprocessing metadata.
    """
    lang = filename_to_lang(file_path)
    
    if not lang:
        if verbose:
            print(f"[Warning] Cannot determine language for {file_path}.")
        return {"preprocessed": False}
    
    result = {"lang": lang, "preprocessed": True}
    lang_config = get_language_config(file_path)
    
    # Identify important structural elements (class definitions, methods, etc.)
    structure_points = []
    
    for pattern in lang_config.get("structure_markers", []):
        for match in re.finditer(pattern, code, re.MULTILINE):
            line_num = code[:match.start()].count('\n')
            structure_points.append(line_num)
    
    result["structure_points"] = sorted(structure_points)
    
    if verbose:
        print(f"[Info] Preprocessed {file_path} as {lang}")
        print(f"[Info] Found {len(structure_points)} structural elements")
    
    # Add framework detection
    framework = detect_framework(code, file_path)
    if framework and verbose:
        print(f"[Info] Detected {framework} framework")
    
    result["framework"] = framework
    
    return result


def analyze_chunk_content(chunk_text: str, file_path: str) -> Dict[str, Any]:
    """Analyze chunk content to determine its type and other metadata."""
    # Get language-specific patterns
    lang_config = get_language_config(file_path)
    ignore_patterns = lang_config.get("ignore_patterns", [])
    structure_markers = lang_config.get("structure_markers", [])
    
    lines = chunk_text.splitlines()
    if not lines:
        return {"type": "empty", "quality": 0}
    
    # Count lines matching ignore patterns
    ignore_lines = 0
    for pattern in ignore_patterns:
        for line in lines:
            if re.search(pattern, line):
                ignore_lines += 1
    
    # Count structural elements
    structure_elements = 0
    for pattern in structure_markers:
        for line in lines:
            if re.search(pattern, line):
                structure_elements += 1
    
    # Calculate content quality metrics
    ignore_ratio = ignore_lines / len(lines) if lines else 0
    structure_ratio = structure_elements / len(lines) if lines else 0
    
    # Determine chunk type based on content
    chunk_type = "code"
    if ignore_ratio > 0.7:
        chunk_type = "imports"
    elif ignore_ratio > 0.3:
        chunk_type = "mixed"
    elif structure_ratio > 0.3:
        chunk_type = "structural"
    
    # Look for special patterns based on language
    special_patterns = lang_config.get("special_handling", {})
    special_matches = {}
    
    for pattern_name, pattern in special_patterns.items():
        if re.search(pattern, chunk_text, re.MULTILINE):
            special_matches[pattern_name] = True
    
    # Framework detection in the chunk
    framework = None
    for fw_name, fw_patterns in WEB_FRAMEWORK_PATTERNS.items():
        for indicator in fw_patterns.get("indicators", []):
            if re.search(indicator, chunk_text, re.MULTILINE):
                framework = fw_name
                break
        if framework:
            break
    
    return {
        "type": chunk_type,
        "quality": 1.0 - ignore_ratio + structure_ratio,  # Higher is better
        "ignore_ratio": ignore_ratio,
        "structure_ratio": structure_ratio,
        "special_matches": special_matches,
        "framework": framework
    }


def filter_parser_elements_for_chunk(elements, chunk_span):
    """
    Filter parser elements that belong to a specific chunk span.
    
    Args:
        elements: List of parser elements
        chunk_span: The Span object representing the chunk's line range
        
    Returns:
        List of parser elements that overlap with the chunk
    """
    chunk_fragments = []
    
    for element in elements:
        # Check if element is within this chunk's line range
        if hasattr(element, 'line') and hasattr(element, 'end_line'):
            # Calculate overlap percentage to determine if the element belongs to this chunk
            element_span = (element.line, element.end_line)
            chunk_range = range(chunk_span.start, chunk_span.end)
            
            # Element is fully contained in chunk
            if element.line >= chunk_span.start and element.end_line < chunk_span.end:
                chunk_fragments.append(element)
            # Element contains the chunk entirely
            elif element.line <= chunk_span.start and element.end_line >= chunk_span.end:
                chunk_fragments.append(element)
            # Element overlaps with chunk (significant overlap)
            elif (element.line in chunk_range or element.end_line in chunk_range):
                # Calculate overlap percentage
                overlap_start = max(element.line, chunk_span.start)
                overlap_end = min(element.end_line, chunk_span.end)
                overlap_lines = overlap_end - overlap_start
                
                element_lines = element.end_line - element.line
                if element_lines > 0 and (overlap_lines / element_lines) > 0.3:  # At least 30% overlap
                    chunk_fragments.append(element)
    
    return chunk_fragments


class GenericChunker(BaseChunker):
    """
    Generic implementation of the code chunker that works for all languages.
    Uses tree-sitter for syntax-aware chunking.
    """
    
    def get_language_name(self) -> str:
        """Get the name of this chunker."""
        return "generic"
    
    def get_file_extensions(self) -> List[str]:
        """Get all supported file extensions."""
        extensions = []
        for lang in LANGUAGE_CONFIGS:
            if lang != "default" and not LANGUAGE_CONFIGS[lang].get("alias"):
                # Map language to extensions using grep_ast mappings as a reference
                if lang == "python":
                    extensions.extend([".py", ".pyw"])
                elif lang == "java":
                    extensions.append(".java")
                elif lang == "go":
                    extensions.append(".go")
                elif lang == "javascript":
                    extensions.extend([".js", ".mjs"])
                elif lang == "typescript":
                    extensions.extend([".ts"])
                elif lang == "jsx":
                    extensions.extend([".jsx"])
                elif lang == "tsx":
                    extensions.extend([".tsx"])
                elif lang == "html":
                    extensions.extend([".html", ".htm", ".xhsml"])
                elif lang == "css":
                    extensions.extend([".css", ".sass", ".scss"])
        return extensions
    
    def chunk_code(self, code: str, file_path: str, max_chars: Optional[int] = None,
                  coalesce_chars: Optional[int] = None, verbose: bool = False) -> List[Span]:
        """
        Chunks the given code string based on syntax structure using grep-ast.

        Args:
            code: The source code as a string.
            file_path: The path to the file (used to determine language).
            max_chars: The approximate maximum number of characters per chunk.
            coalesce_chars: Minimum non-whitespace characters for a chunk to not be merged.
            verbose: If True, print verbose logging.

        Returns:
            A list of Span objects representing the line ranges (0-indexed) of the chunks.
        """
        # Get language-specific configuration
        lang_config = get_language_config(file_path)
        
        # Use provided parameters or language defaults
        max_chars = max_chars or lang_config.get("max_chars", LANGUAGE_CONFIGS["default"]["max_chars"])
        coalesce = coalesce_chars or lang_config.get("coalesce_chars", LANGUAGE_CONFIGS["default"]["coalesce_chars"])
        
        # Get language for parsing
        lang = filename_to_lang(file_path)
        if not lang:
            if verbose:
                print(f"[Warning] Cannot determine language for {file_path}. Falling back to naive chunking.")
            # TODO: Implement naive line-based chunking fallback here
            return []  # Placeholder for naive chunker

        try:
            language = get_language(lang)
            parser = get_parser(lang)
            if verbose:
                print(f"[Info] Using language '{lang}' for parsing {file_path}.")
        except Exception as e:
            print(f"[Error] Failed to load parser for language '{lang}' ({file_path}): {e}")
            print(traceback.format_exc())
            # TODO: Implement naive line-based chunking fallback here
            return []  # Placeholder for naive chunker

        code_bytes = code.encode("utf-8")
        tree = None
        try:
            tree = parser.parse(code_bytes)
        except Exception as e:
            print(f"[Error] Failed to parse {file_path}: {e}")
            # TODO: Implement naive line-based chunking fallback here
            return []  # Placeholder for naive chunker

        if not tree or not tree.root_node:
            if verbose:
                print(f"[Warning] Parsing resulted in an empty tree for {file_path}.")
            return []

        # --- 1. Recursive Chunking (based on byte offsets initially) ---
        def chunk_node(node) -> List[Span]:
            """Recursively chunks a tree-sitter node based on byte size."""
            chunks: List[Span] = []
            # Start with an empty span at the node's start byte
            current_chunk: Span = Span(node.start_byte, node.start_byte) 
            
            for child in node.children:
                child_byte_len = child.end_byte - child.start_byte
                current_chunk_byte_len = len(current_chunk)

                if child_byte_len > max_chars:
                    # Child is too large, finalize current chunk and recursively chunk child
                    if len(current_chunk) > 0:  # Don't add empty chunks
                        chunks.append(current_chunk)
                    # Start new chunk after this large child
                    current_chunk = Span(child.end_byte, child.end_byte) 
                    chunks.extend(chunk_node(child))
                elif child_byte_len + current_chunk_byte_len > max_chars:
                    # Adding child makes current chunk too large, finalize current chunk
                    if len(current_chunk) > 0:  # Don't add empty chunks
                        chunks.append(current_chunk)
                    # Start new chunk with this child
                    current_chunk = Span(child.start_byte, child.end_byte)
                else:
                    # Add child to current chunk by extending the end byte
                    # Uses the Span.__add__ logic: Span(start, end) + Span(child_start, child_end) -> Span(start, child_end)
                    current_chunk += Span(child.start_byte, child.end_byte)
                    
            # Append the last chunk if it's not empty
            if len(current_chunk) > 0 and current_chunk.end > current_chunk.start:
                # Ensure the last chunk ends where the node ends if it hasn't been updated
                if current_chunk.end <= current_chunk.start and node.end_byte > node.start_byte:
                    current_chunk.end = node.end_byte  # Should not happen if children cover node? Safety check.
                elif current_chunk.end < node.end_byte and current_chunk.start == node.start_byte and not chunks:
                    # If it's the *only* chunk for this node, make sure it covers the whole node
                    current_chunk.end = node.end_byte

                # Avoid adding zero-length or negative spans
                if current_chunk.end > current_chunk.start:
                    chunks.append(current_chunk)

            return chunks

        byte_chunks = chunk_node(tree.root_node)

        if not byte_chunks:
            if verbose:
                print(f"[Info] No byte chunks generated for {file_path}. Whole file might be smaller than max_chars.")
            # If the whole file is one chunk, create a single span
            if tree.root_node.end_byte > 0:
                byte_chunks = [Span(0, tree.root_node.end_byte)]
            else:
                return []  # Empty file

        # --- 2. Fill Gaps ---
        # Ensure chunks are contiguous by setting end of chunk i to start of chunk i+1
        # This handles potential gaps left by the tree-sitter parser or chunking logic.
        for i in range(len(byte_chunks) - 1):
            # Only adjust if there's a gap or minor overlap inconsistency
            if byte_chunks[i].end != byte_chunks[i+1].start:
                byte_chunks[i].end = byte_chunks[i+1].start
        # Ensure the last chunk ends at the end of the root node
        if byte_chunks and byte_chunks[-1].end < tree.root_node.end_byte:
            byte_chunks[-1].end = tree.root_node.end_byte

        # --- 3. Coalesce Small Chunks ---
        coalesced_byte_chunks = []
        current_chunk = Span(0, 0)  # Initialize an empty span
        is_first_chunk = True

        for chunk in byte_chunks:
            if is_first_chunk:
                current_chunk = chunk  # Start with the first chunk
                is_first_chunk = False
            else:
                # Add the next chunk to the current one being built
                current_chunk += chunk  # Uses Span.__add__

            chunk_content = current_chunk.extract(code_bytes)
            # Check non-whitespace length and if it contains a newline
            if non_whitespace_len(chunk_content) > coalesce and b"\n" in chunk_content:
                coalesced_byte_chunks.append(current_chunk)
                # Start a new empty chunk at the end of the one just added
                current_chunk = Span(chunk.end, chunk.end) 

        # Add the last potentially coalesced chunk if it has content
        if len(current_chunk) > 0 and current_chunk.end > current_chunk.start: 
            # Ensure the very last chunk ends at the end of the file content
            if current_chunk.end < tree.root_node.end_byte:
                current_chunk.end = tree.root_node.end_byte
            coalesced_byte_chunks.append(current_chunk)
            
        # Handle edge case: if no chunks qualified after coalescing (e.g., very small file)
        # return the original (gap-filled) byte chunks.
        if not coalesced_byte_chunks and byte_chunks:
            coalesced_byte_chunks = byte_chunks

        # --- 4. Convert Bytes to Lines ---
        line_chunks = []
        for chunk in coalesced_byte_chunks:
            start_line = get_line_number(chunk.start, code_bytes)
            end_line = get_line_number(chunk.end, code_bytes)
            
            # For more accurate end_line calculation
            effective_end_byte = chunk.end
            if chunk.end > 0 and chunk.end == tree.root_node.end_byte:
                # If it's the very end of the file, get line number for the last byte
                effective_end_byte = chunk.end - 1
            elif chunk.end > chunk.start:
                # Otherwise, consider the character *before* the end byte index
                effective_end_byte = chunk.end - 1

            if effective_end_byte < chunk.start:  # Handle zero-length or weird chunks
                effective_end_byte = chunk.start  # Avoid negative length issues

            end_line = get_line_number(effective_end_byte, code_bytes)

            # The Span represents lines [start, end), so add 1 to end_line for the upper bound.
            line_chunks.append(Span(start_line, end_line + 1))

        # --- 5. Eliminate Empty or Invalid Line Chunks ---
        # Remove chunks where start >= end
        final_line_chunks = [chunk for chunk in line_chunks if chunk.end > chunk.start]
        
        # --- 6. Post-process based on language-specific structure ---
        # Get preprocessing metadata
        metadata = preprocess_code(code, file_path, verbose)
        
        if metadata.get("preprocessed", False):
            # Process ignore sections (imports, etc.)
            if metadata.get("ignore_sections"):
                # If we have sections to potentially ignore (like imports),
                # we might want to create a separate chunk just for them
                if verbose:
                    print(f"[Info] Adjusting chunks based on language-specific structure")
        
        if verbose:
            print(f"[Info] Generated {len(final_line_chunks)} chunks for {file_path}")
            
        return final_line_chunks
    
    def create_chunk_infos(self, spans: List[Span], code: str, file_path: str) -> List[ChunkInfo]:
        """Create ChunkInfo objects from spans with enhanced metadata."""
        chunk_infos = []
        
        # Get parser fragments if available
        parser_elements = []
        if PARSERS_AVAILABLE:
            parser = ParserRegistry.get_parser_for_file(file_path)
            if parser:
                detector = parser.create_element_detector()
                try:
                    parser_elements = detector.detect_elements(file_path)
                except Exception as e:
                    print(f"[Warning] Failed to parse elements from {file_path}: {e}")
        
        for span in spans:
            chunk_text = span.extract_lines(code)
            analysis = analyze_chunk_content(chunk_text, file_path)
            
            # Find parser elements that belong to this chunk using the filter function
            chunk_fragments = filter_parser_elements_for_chunk(parser_elements, span)
            
            chunk_info = ChunkInfo(
                span=span,
                text=chunk_text,
                chunk_type=analysis["type"],
                metadata={
                    "non_whitespace_len": non_whitespace_len(chunk_text),
                    "line_count": span.end - span.start,
                    "quality": analysis.get("quality", 0),
                    "special_matches": analysis.get("special_matches", {}),
                    "framework": analysis.get("framework")
                },
                parser_fragments=chunk_fragments
            )
            
            chunk_infos.append(chunk_info)
        
        return chunk_infos
        
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
        # Read file content only once
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
        except UnicodeDecodeError:
            # Try with a different encoding if UTF-8 fails
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    code = f.read()
                if verbose:
                    print(f"[Warning] File {file_path} was read with latin-1 encoding instead of utf-8")
            except Exception as e:
                if verbose:
                    print(f"[Error] Failed to read file {file_path}: {e}")
                return {"chunks": [], "summary": {}, "structure": {}, "metadata": {"error": str(e)}}
        except Exception as e:
            if verbose:
                print(f"[Error] Failed to read file {file_path}: {e}")
            return {"chunks": [], "summary": {}, "structure": {}, "metadata": {"error": str(e)}}
            
        # Get language information
        lang = filename_to_lang(file_path)
        lang_config = get_language_config(file_path)
        
        # Extract and process parser elements in a single pass (if available)
        parser_elements = []
        file_structure = {}
        element_hierarchy = {}
        
        if PARSERS_AVAILABLE:
            parser = ParserRegistry.get_parser_for_file(file_path)
            if parser:
                detector = parser.create_element_detector()
                try:
                    # Single parser pass - reuse for both file summary and chunks
                    parser_elements = detector.detect_elements(file_path)
                    
                    # Group elements by type for file structure
                    for elem in parser_elements:
                        # Try to get type attribute in different ways
                        elem_type = None
                        for attr in ['type', 'type_info', 'element_type']:
                            if hasattr(elem, attr):
                                elem_type = getattr(elem, attr)
                                break
                                
                        if elem_type is None:
                            elem_type = 'unknown'
                        
                        if elem_type not in file_structure:
                            file_structure[elem_type] = []
                        
                        # Extract key information from element
                        element_info = {
                            'name': getattr(elem, 'name', 'unnamed'),
                            'line': getattr(elem, 'line', 0),
                            'end_line': getattr(elem, 'end_line', 0)
                        }
                        
                        # Add other interesting attributes if available
                        for attr in ['is_public', 'is_static', 'is_abstract', 'params', 'return_type']:
                            if hasattr(elem, attr):
                                element_info[attr] = getattr(elem, attr)
                                
                        file_structure[elem_type].append(element_info)
                    
                    # Build hierarchical dependency structure (parent-child relationships)
                    for i, elem1 in enumerate(parser_elements):
                        if hasattr(elem1, 'line') and hasattr(elem1, 'end_line'):
                            # Try to get type attribute
                            elem1_type = None
                            for attr in ['type', 'type_info', 'element_type']:
                                if hasattr(elem1, attr):
                                    elem1_type = getattr(elem1, attr)
                                    break
                            if elem1_type is None:
                                elem1_type = 'unknown'
                                
                            elem1_name = getattr(elem1, 'name', 'unnamed')
                            elem1_id = f"{elem1_type}:{elem1_name}:{elem1.line}"
                            
                            for j, elem2 in enumerate(parser_elements):
                                if i != j and hasattr(elem2, 'line') and hasattr(elem2, 'end_line'):
                                    # Check if elem2 is nested within elem1
                                    if (elem2.line >= elem1.line and elem2.end_line <= elem1.end_line and 
                                        (elem1.line != elem2.line or elem1.end_line != elem2.end_line)):
                                        
                                        # Try to get type attribute
                                        elem2_type = None
                                        for attr in ['type', 'type_info', 'element_type']:
                                            if hasattr(elem2, attr):
                                                elem2_type = getattr(elem2, attr)
                                                break
                                        if elem2_type is None:
                                            elem2_type = 'unknown'
                                            
                                        elem2_name = getattr(elem2, 'name', 'unnamed')
                                        elem2_id = f"{elem2_type}:{elem2_name}:{elem2.line}"
                                        
                                        if elem1_id not in element_hierarchy:
                                            element_hierarchy[elem1_id] = []
                                        element_hierarchy[elem1_id].append(elem2_id)
                                        
                except Exception as e:
                    if verbose:
                        print(f"[Warning] Failed to parse elements from {file_path}: {e}")
        
        # Generate preprocessing metadata
        file_metadata = preprocess_code(code, file_path, verbose)
        
        # Generate chunks in a single pass
        spans = self.chunk_code(code, file_path, max_chars, coalesce_chars, verbose)
        
        # Generate chunk infos reusing the already parsed elements
        chunk_infos = []
        for span in spans:
            chunk_text = span.extract_lines(code)
            analysis = analyze_chunk_content(chunk_text, file_path)
            
            # Find parser elements that belong to this chunk using the filter function
            chunk_fragments = filter_parser_elements_for_chunk(parser_elements, span)
            
            chunk_info = ChunkInfo(
                span=span,
                text=chunk_text,
                chunk_type=analysis["type"],
                metadata={
                    "non_whitespace_len": non_whitespace_len(chunk_text),
                    "line_count": span.end - span.start,
                    "quality": analysis.get("quality", 0),
                    "special_matches": analysis.get("special_matches", {}),
                    "framework": analysis.get("framework")
                },
                parser_fragments=chunk_fragments
            )
            
            chunk_infos.append(chunk_info)
            
        # Generate basic statistics
        total_lines = code.count('\n') + 1
        total_elements = len(parser_elements)
        element_type_counts = {}
        
        for element in parser_elements:
            # Try to get type attribute in different ways
            elem_type = None
            for attr in ['type', 'type_info', 'element_type']:
                if hasattr(element, attr):
                    elem_type = getattr(element, attr)
                    break
            if elem_type is None:
                elem_type = 'unknown'
                
            if elem_type not in element_type_counts:
                element_type_counts[elem_type] = 0
            element_type_counts[elem_type] += 1
            
        # Create summary
        summary = {
            "filename": os.path.basename(file_path),
            "filepath": file_path,  # Add full file path
            "language": lang,
            "total_lines": total_lines,
            "total_chunks": len(chunk_infos),
            "total_elements": total_elements,
            "element_type_counts": element_type_counts,
            "framework": file_metadata.get("framework"),
            "structure_points": file_metadata.get("structure_points", []),
        }
        
        # Generate formatted structure
        formatted_structure = format_file_structure(file_path, parser_elements, element_hierarchy)
        
        # Combine everything into a comprehensive result
        result = {
            "chunks": chunk_infos,
            "summary": summary,
            "structure": file_structure,
            "hierarchy": element_hierarchy,
            "metadata": file_metadata,
            "formatted_structure": formatted_structure
        }
        
        return result


def is_parser_available():
    """Check if the parser module is available and loaded correctly.
    
    Returns:
        bool: True if the parser module is available, False otherwise.
        str: Information message about the parser status.
    """
    global PARSERS_AVAILABLE
    
    message = ""
    if PARSERS_AVAILABLE:
        try:
            # Try to access a method in the ParserRegistry to verify it's loaded correctly
            from script.file_parser.base_parser import ParserRegistry
            available_parsers = ParserRegistry.available_parsers()
            message = f"Parser module loaded successfully. Available parsers: {', '.join(available_parsers)}"
            return True, message
        except Exception as e:
            PARSERS_AVAILABLE = False
            message = f"Parser module import succeeded but failed to use: {str(e)}"
            return False, message
    else:
        message = "Parser module not available. Chunks will not include parser fragments."
        return False, message

def format_file_structure(file_path: str, parser_elements: List, hierarchy: Dict[str, List[str]] = None) -> str:
    """
    Format the file structure data into a tree-like string representation.
    
    Args:
        file_path: Path to the file
        parser_elements: List of parsed elements with type, name, line number information
        hierarchy: Dictionary containing hierarchical relationships (optional)
        
    Returns:
        String representation of the file structure in tree format
    """
    if not parser_elements:
        return f"{file_path}\n└── No structure information available"
    
    # Start with the full file path
    result = [file_path]
    
    # Group elements by type
    elements_by_type = {}
    for elem in parser_elements:
        # Try to get type attribute in different ways
        elem_type = None
        for attr in ['type', 'type_info', 'element_type']:
            if hasattr(elem, attr):
                elem_type = getattr(elem, attr)
                break
                
        if elem_type is None:
            elem_type = 'unknown'
            
        if elem_type not in elements_by_type:
            elements_by_type[elem_type] = []
        
        # Try to get name attribute
        elem_name = getattr(elem, 'name', 'unnamed')
        
        # Get line numbers, defaulting to 0 if not available
        start_line = getattr(elem, 'line', 0) + 1  # Convert to 1-indexed
        end_line = getattr(elem, 'end_line', 0) + 1  # Convert to 1-indexed
        
        line_range = f"(Lines: {start_line}-{end_line})" if start_line != end_line else f"(Line: {start_line})"
        
        elements_by_type[elem_type].append((elem_name, line_range, elem))
    
    # Define the display order and titles
    display_order = ["package", "import", "class", "interface", "function", "method", "field", "variable"]
    type_display = {
        "package": "Package",
        "import": "Imports",
        "class": "Classes",
        "interface": "Interfaces",
        "function": "Functions", 
        "method": "Methods",
        "field": "Fields",
        "variable": "Variables"
    }
    
    # Process each category
    for elem_type in display_order:
        if elem_type in elements_by_type and elements_by_type[elem_type]:
            # Add section header
            section_title = type_display.get(elem_type, elem_type.capitalize())
            result.append(f"├── {section_title}")
            
            # Sort elements by name or line number
            sorted_elements = sorted(elements_by_type[elem_type], key=lambda x: x[0])
            
            # Add each element
            for i, (name, line_range, elem) in enumerate(sorted_elements):
                # Check if this is the last element in the category
                is_last = i == len(sorted_elements) - 1
                prefix = "    " if is_last else "│   "
                tree_char = "└── " if is_last else "├── "
                
                # Add element line
                result.append(f"{prefix}{tree_char}{name} {line_range}")
    
    # Process any other categories not in the display order
    other_types = [t for t in elements_by_type.keys() if t not in display_order]
    for elem_type in other_types:
        if elements_by_type[elem_type]:
            # Add section header
            section_title = elem_type.capitalize()
            result.append(f"└── {section_title}")
            
            # Sort elements by name
            sorted_elements = sorted(elements_by_type[elem_type], key=lambda x: x[0])
            
            # Add each element
            for i, (name, line_range, _) in enumerate(sorted_elements):
                is_last = i == len(sorted_elements) - 1
                prefix = "    " if is_last else "│   "
                tree_char = "└── " if is_last else "├── "
                result.append(f"{prefix}{tree_char}{name} {line_range}")
    
    return "\n".join(result)

def parse_file_with_summary(file_path: str, max_chars: Optional[int] = None,
                           coalesce_chars: Optional[int] = None, verbose: bool = False) -> Dict[str, Any]:
    """
    High-performance utility function to parse a file and generate both chunks and summary at once.
    This is the main entry point for external code to parse files with the chunker system.
    
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
    # Check if file exists
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        error_msg = f"File not found: {file_path}"
        if verbose:
            print(f"[Error] {error_msg}")
        return {
            "chunks": [], 
            "summary": {}, 
            "structure": {}, 
            "metadata": {"error": error_msg}
        }
    
    # Try to get a specific chunker for this file type
    try:
        from .main import ChunkerRegistry
        chunker = ChunkerRegistry.get_chunker_for_file(file_path)
        if chunker and hasattr(chunker, 'parse_file_with_summary'):
            if verbose:
                print(f"[Info] Using specialized chunker for {file_path}")
            return chunker.parse_file_with_summary(file_path, max_chars, coalesce_chars, verbose)
    except (ImportError, Exception) as e:
        if verbose:
            print(f"[Warning] Could not use chunker registry: {str(e)}. Using generic chunker.")
    
    # Use the generic chunker
    generic_chunker = GenericChunker()
    try:
        result = generic_chunker.parse_file_with_summary(file_path, max_chars, coalesce_chars, verbose)
        
        # Check if the generic chunker returned empty chunks
        if not result.get("chunks", []):
            # Try using the markdown chunker as fallback
            try:
                from .markdown_chunker import MarkdownChunker
                if verbose:
                    print(f"[Info] Generic chunker returned no results, trying markdown chunker for {file_path}")
                markdown_chunker = MarkdownChunker()
                md_result = markdown_chunker.parse_file_with_summary(file_path, max_chars, coalesce_chars, verbose)
                # Add a note that this was processed by the fallback chunker
                if "metadata" in md_result and md_result["metadata"] is not None:
                    md_result["metadata"]["fallback_chunker"] = "markdown"
                # Add a note to the summary
                if "summary" in md_result and md_result["summary"] is not None:
                    md_result["summary"]["fallback_chunker"] = "markdown"
                return md_result
            except Exception as md_e:
                if verbose:
                    print(f"[Warning] Markdown chunker also failed for {file_path}: {md_e}")
                # Return the original empty result from the generic chunker
        
        return result
    except Exception as e:
        if verbose:
            print(f"[Error] Generic chunker failed for {file_path}: {e}")
        
        # Try using the markdown chunker as fallback
        try:
            from .markdown_chunker import MarkdownChunker
            if verbose:
                print(f"[Info] Using markdown chunker as fallback for {file_path}")
            markdown_chunker = MarkdownChunker()
            md_result = markdown_chunker.parse_file_with_summary(file_path, max_chars, coalesce_chars, verbose)
            # Add a note that this was processed by the fallback chunker
            if "metadata" in md_result and md_result["metadata"] is not None:
                md_result["metadata"]["fallback_chunker"] = "markdown"
            # Add a note to the summary
            if "summary" in md_result and md_result["summary"] is not None:
                md_result["summary"]["fallback_chunker"] = "markdown"
            return md_result
        except Exception as md_e:
            if verbose:
                print(f"[Warning] Markdown chunker also failed for {file_path}: {md_e}")
            
            # Both chunkers failed, return an error result
            return {
                "chunks": [],
                "summary": {
                    "filename": os.path.basename(file_path),
                    "filepath": file_path,
                    "language": "unknown",
                    "total_lines": 0,
                    "total_chunks": 0,
                    "error": f"Failed to parse with both generic and markdown chunkers: {e}, {md_e}"
                },
                "structure": {},
                "metadata": {"error": f"Failed to parse: {e}"}
            } 