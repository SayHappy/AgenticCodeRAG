# phased_verification_script/02_chunk_single_file/code_chunker.py

import re
import os
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Union, Optional, Dict, Any, Callable
from grep_ast import filename_to_lang
from grep_ast.tsl import USING_TSL_PACK, get_language, get_parser # Assuming grep_ast is installed

# Constants from design docs (can be adjusted)
# Average characters per line (heuristic)
AVG_CHAR_IN_LINE = 80 
# Target chunk size in characters (approx. 200 lines)
DEFAULT_MAX_CHARS = AVG_CHAR_IN_LINE * 200 
# Minimum chunk size in characters before coalescing (approx. 50 lines)
DEFAULT_COALESCE_CHARS = AVG_CHAR_IN_LINE * 50 

# Language-specific configurations
LANGUAGE_CONFIGS = {
    # Backend Languages
    "java": {
        "max_chars": AVG_CHAR_IN_LINE * 40,  # ~40 lines per chunk for Java
        "coalesce_chars": AVG_CHAR_IN_LINE * 15,
        "ignore_patterns": [
            r"import\s+[^;]+;",  # Import statements
            r"^\s*package\s+[^;]+;",  # Package declarations
            r"//.*$",  # Single line comments
            r"/\*[\s\S]*?\*/",  # Multi-line comments
        ],
        "structure_markers": [
            r"(public|private|protected)?\s+(static)?\s+(class|interface|enum)\s+\w+",  # Class declarations
            r"(public|private|protected)?\s+(static)?\s+\w+(<[^>]+>)?\s+\w+\s*\([^)]*\)",  # Method declarations
            r"@\w+(\([^)]*\))?",  # Annotations
            r"@Service|@Controller|@Repository|@Component|@Entity",  # Spring annotations
            r"@RestController|@RequestMapping|@GetMapping|@PostMapping",  # Spring REST annotations
        ],
        "special_handling": {
            "controller_methods": r"@(Get|Post|Put|Delete|Patch)Mapping",  # REST endpoints
            "entity_classes": r"@Entity|@Table",  # Database entities
            "services": r"@Service",  # Service classes
        }
    },
    "python": {
        "max_chars": AVG_CHAR_IN_LINE * 50,  # ~50 lines per chunk for Python
        "coalesce_chars": AVG_CHAR_IN_LINE * 20,
        "ignore_patterns": [
            r"^\s*import\s+.*$",  # Import statements
            r"^\s*from\s+.*\s+import\s+.*$",  # From import statements
            r"^\s*#.*$",  # Comments
            r'"""[\s\S]*?"""',  # Docstrings (triple double quotes)
            r"'''[\s\S]*?'''",  # Docstrings (triple single quotes)
        ],
        "structure_markers": [
            r"^\s*def\s+\w+\s*\(",  # Function definitions
            r"^\s*class\s+\w+",  # Class definitions
            r"^\s*@\w+",  # Decorators
            r"^\s*@(app|router)\.(get|post|put|delete|patch)",  # FastAPI/Flask route decorators
        ],
        "special_handling": {
            "flask_routes": r"@app\.(get|post|put|delete|patch)",  # Flask routes
            "fastapi_routes": r"@(router|app)\.(get|post|put|delete|patch)",  # FastAPI routes
            "django_views": r"class\s+\w+View\(",  # Django class-based views
        }
    },
    "go": {
        "max_chars": AVG_CHAR_IN_LINE * 40,  # ~40 lines per chunk for Go
        "coalesce_chars": AVG_CHAR_IN_LINE * 15,
        "ignore_patterns": [
            r"^\s*import\s+\(",  # Import blocks
            r'^\s*import\s+"[^"]+"',  # Single imports
            r"//.*$",  # Single line comments
            r"/\*[\s\S]*?\*/",  # Multi-line comments
        ],
        "structure_markers": [
            r"func\s+\w+\s*\(",  # Function declarations
            r"func\s+\(\w+\s+\*?\w+\)\s+\w+\s*\(",  # Method declarations
            r"type\s+\w+\s+struct",  # Struct declarations
            r"type\s+\w+\s+interface",  # Interface declarations
        ],
        "special_handling": {
            "handlers": r"func\s+\w+\(w\s+http\.ResponseWriter,\s*r\s+\*http\.Request\)",  # HTTP handlers
            "middleware": r"func\s+\w+\(.*\)\s+http\.Handler",  # HTTP middleware
            "gin_handlers": r"func\s+\w+\(c\s+\*gin\.Context\)",  # Gin handlers
        }
    },
    
    # Frontend Languages
    "javascript": {
        "max_chars": AVG_CHAR_IN_LINE * 40,  # ~40 lines per chunk for JavaScript
        "coalesce_chars": AVG_CHAR_IN_LINE * 15,
        "ignore_patterns": [
            r"^\s*import\s+.*$",  # ES6 imports
            r"^\s*const\s+.*\s*=\s*require\(.*\);",  # CommonJS requires
            r"//.*$",  # Single line comments
            r"/\*[\s\S]*?\*/",  # Multi-line comments
        ],
        "structure_markers": [
            r"function\s+\w+\s*\(",  # Function declarations
            r"const\s+\w+\s*=\s*\(.*\)\s*=>",  # Arrow function constants
            r"let\s+\w+\s*=\s*\(.*\)\s*=>",  # Arrow function variables
            r"class\s+\w+",  # Class declarations
            r"export\s+(default\s+)?(function|class|const)",  # Export declarations
            r"export\s+default\s+{",  # Default exports
        ],
        "special_handling": {
            "react_components": r"(function|const)\s+(\w+)\s*=.*React|React\.Component|React\.PureComponent|extends\s+(React\.)?Component",
            "event_handlers": r"(function|const)\s+handle\w+\s*=",
            "hooks": r"(const|let)\s+\[\w+,\s*set\w+\]\s*=\s*useState",
        }
    },
    "typescript": {
        "max_chars": AVG_CHAR_IN_LINE * 40,  # ~40 lines per chunk for TypeScript
        "coalesce_chars": AVG_CHAR_IN_LINE * 15,
        "ignore_patterns": [
            r"^\s*import\s+.*$",  # ES6 imports
            r"//.*$",  # Single line comments
            r"/\*[\s\S]*?\*/",  # Multi-line comments
        ],
        "structure_markers": [
            r"function\s+\w+<?\w*>?\s*\(",  # Function declarations with optional generics
            r"const\s+\w+\s*=\s*\(.*\)\s*:",  # Arrow functions with type annotations
            r"class\s+\w+<?\w*>?",  # Class declarations with optional generics
            r"interface\s+\w+",  # Interface declarations
            r"type\s+\w+\s*=",  # Type aliases
            r"export\s+(default\s+)?(function|class|const|interface|type)",  # Export declarations
        ],
        "special_handling": {
            "react_components": r"(function|const)\s+(\w+)(\s*:\s*React|\s*=.*React\.FC|\s*=.*React|React\.Component|React\.PureComponent|extends\s+(React\.)?Component)",
            "hooks": r"(const|let)\s+\[\w+,\s*set\w+\]\s*=\s*useState",
            "reducers": r"(function|const)\s+\w+Reducer",
        }
    },
    "jsx": {
        "max_chars": AVG_CHAR_IN_LINE * 35,  # ~35 lines per chunk for JSX
        "coalesce_chars": AVG_CHAR_IN_LINE * 15,
        "ignore_patterns": [
            r"^\s*import\s+.*$",  # ES6 imports
            r"//.*$",  # Single line comments
            r"/\*[\s\S]*?\*/",  # Multi-line comments
        ],
        "structure_markers": [
            r"function\s+\w+\s*\(",  # Function declarations
            r"const\s+\w+\s*=\s*\(.*\)\s*=>",  # Arrow function constants
            r"class\s+\w+\s+extends\s+React\.Component",  # Class components
            r"return\s+\(\s*<",  # JSX return statements
            r"<\w+\s+\w+.*>",  # JSX elements with props
        ],
        "special_handling": {
            "components": r"(function|const)\s+(\w+)\s*=.*?\(\s*\)\s*=>\s*\{.*?return\s+<",
            "hooks": r"(const|let)\s+\[\w+,\s*set\w+\]\s*=\s*useState",
            "effects": r"useEffect\(\(\)\s*=>",
        }
    },
    "tsx": {
        "max_chars": AVG_CHAR_IN_LINE * 35,  # ~35 lines per chunk for TSX
        "coalesce_chars": AVG_CHAR_IN_LINE * 15,
        "ignore_patterns": [
            r"^\s*import\s+.*$",  # ES6 imports
            r"//.*$",  # Single line comments
            r"/\*[\s\S]*?\*/",  # Multi-line comments
        ],
        "structure_markers": [
            r"function\s+\w+<?\w*>?\s*\(",  # Function declarations with optional generics
            r"const\s+\w+\s*=\s*\(.*\)\s*:",  # Arrow functions with type annotations
            r"class\s+\w+<?\w*>?\s+extends\s+React\.Component",  # Class components with generics
            r"return\s+\(\s*<",  # JSX return statements
            r"<\w+\s+\w+.*>",  # JSX elements with props
            r"interface\s+\w+Props",  # Props interfaces
        ],
        "special_handling": {
            "components": r"(function|const)\s+(\w+)\s*:\s*React\.FC|=.*?\(\s*\)\s*=>\s*\{.*?return\s+<",
            "hooks": r"(const|let)\s+\[\w+,\s*set\w+\]\s*=\s*useState",
            "effects": r"useEffect\(\(\)\s*=>",
        }
    },
    "html": {
        "max_chars": AVG_CHAR_IN_LINE * 50,  # ~50 lines per chunk for HTML
        "coalesce_chars": AVG_CHAR_IN_LINE * 20,
        "ignore_patterns": [
            r"<!--.*?-->",  # HTML comments
            r"<link\s+.*?>",  # Link tags
            r"<meta\s+.*?>",  # Meta tags
            r"<script\s+src=.*?></script>",  # Script imports (no content)
            r"<style\s+src=.*?></style>",  # Style imports (no content)
        ],
        "structure_markers": [
            r"<div\s+.*?class=.*?>",  # Div with class
            r"<(header|footer|main|nav|section|article|aside)>",  # Semantic elements
            r"<form\s+.*?>",  # Forms
            r"<template\s+.*?>",  # Templates
        ],
        "special_handling": {
            "scripts": r"<script>[\s\S]*?</script>",  # Script tags with content
            "styles": r"<style>[\s\S]*?</style>",  # Style tags with content
            "forms": r"<form[\s\S]*?</form>",  # Complete forms
        }
    },
    "css": {
        "max_chars": AVG_CHAR_IN_LINE * 50,  # ~50 lines per chunk for CSS
        "coalesce_chars": AVG_CHAR_IN_LINE * 20,
        "ignore_patterns": [
            r"/\*[\s\S]*?\*/",  # CSS comments
            r"@import\s+.*?;",  # CSS imports
        ],
        "structure_markers": [
            r"(\.|#)\w+\s*{",  # Class or ID selectors
            r"@media\s+.*?{",  # Media queries
            r"@keyframes\s+.*?{",  # Keyframe animations
        ],
        "special_handling": {
            "media_queries": r"@media\s+.*?{[\s\S]*?}",  # Complete media queries
            "animations": r"@keyframes\s+.*?{[\s\S]*?}",  # Complete keyframe animations
        }
    },
    # Legacy language mappings (for compatibility)
    "typescript.tsx": {"alias": "tsx"},
    "typescript.jsx": {"alias": "jsx"},
    "javascriptreact": {"alias": "jsx"},
    "typescriptreact": {"alias": "tsx"},
    
    # Default configuration for other languages
    "default": {
        "max_chars": DEFAULT_MAX_CHARS,
        "coalesce_chars": DEFAULT_COALESCE_CHARS,
        "ignore_patterns": [],
        "structure_markers": [],
        "special_handling": {}
    },
}

# Add more detailed handling for web frameworks
WEB_FRAMEWORK_PATTERNS = {
    # Backend frameworks
    "spring": {
        "indicators": [
            r"@SpringBootApplication",
            r"@Controller",
            r"@RestController",
            r"@Service",
            r"@Repository",
            r"@Component",
        ],
        "special_handling": {
            "controllers": r"@(Rest)?Controller\s+class\s+\w+",
            "services": r"@Service\s+class\s+\w+",
            "repositories": r"@Repository\s+class\s+\w+",
            "endpoints": r"@(GetMapping|PostMapping|PutMapping|DeleteMapping|RequestMapping)",
        }
    },
    "django": {
        "indicators": [
            r"from\s+django",
            r"@login_required",
            r"class\s+\w+View\(",
            r"class\s+\w+ModelAdmin\(",
        ],
        "special_handling": {
            "views": r"class\s+\w+View\(",
            "models": r"class\s+\w+\(models\.Model\)",
            "forms": r"class\s+\w+Form\(",
            "urls": r"urlpatterns\s*=",
        }
    },
    "flask": {
        "indicators": [
            r"from\s+flask",
            r"@app\.route",
            r"Flask\(__name__\)",
        ],
        "special_handling": {
            "routes": r"@app\.route\(['\"](.+?)['\"]",
            "blueprints": r"Blueprint\(['\"](.+?)['\"]",
            "error_handlers": r"@app\.errorhandler",
        }
    },
    
    # Frontend frameworks
    "react": {
        "indicators": [
            r"import\s+.+?\s+from\s+['\"]react['\"]",
            r"React\.Component",
            r"extends\s+Component",
            r"useState",
            r"useEffect",
        ],
        "special_handling": {
            "functional_components": r"function\s+(\w+)\s*\(.*?\)\s*{.*?return\s+<",
            "class_components": r"class\s+(\w+)\s+extends\s+(React\.)?Component",
            "hooks": r"use[A-Z]\w+\(",
        }
    },
    "vue": {
        "indicators": [
            r"import\s+.+?\s+from\s+['\"]vue['\"]",
            r"createApp",
            r"<template>",
            r"<script\s+setup>",
        ],
        "special_handling": {
            "components": r"<script>[\s\S]*?export\s+default\s*{",
            "composition_api": r"<script\s+setup>",
            "templates": r"<template>[\s\S]*?</template>",
        }
    },
    "angular": {
        "indicators": [
            r"import\s+.+?\s+from\s+['\"]@angular",
            r"@Component",
            r"@NgModule",
            r"@Injectable",
        ],
        "special_handling": {
            "components": r"@Component\(\{[^}]*\}\)\s*export\s+class\s+(\w+Component)",
            "services": r"@Injectable\(\{[^}]*\}\)\s*export\s+class\s+(\w+Service)",
            "modules": r"@NgModule\(\{[^}]*\}\)\s*export\s+class\s+(\w+Module)",
        }
    },
}

@dataclass
class Span:
    """Represents a slice of text using start and end points (byte or line)."""
    start: int
    end: int

    def extract(self, s: Union[str, bytes]) -> Union[str, bytes]:
        """Extracts the substring/subbytes corresponding to the span."""
        return s[self.start:self.end]

    def extract_lines(self, s: str) -> str:
        """Extracts lines from a string based on 0-indexed line numbers."""
        lines = s.splitlines()
        # Ensure start and end are within bounds
        start_line = max(0, self.start)
        end_line = min(len(lines), self.end)
        return "\n".join(lines[start_line:end_line])

    def __add__(self, other: Union['Span', int]) -> 'Span':
        """
        Adds two spans or shifts a span by an integer.
        Span(a, b) + Span(c, d) = Span(a, d) (Concatenation, assumes b approx c)
        Span(a, b) + int = Span(a + int, b + int) (Shift)
        """
        if isinstance(other, int):
            return Span(self.start + other, self.end + other)
        elif isinstance(other, Span):
            # Concatenate: assumes spans are contiguous or overlapping for simplification
            # Takes the start of the first and end of the second.
            return Span(self.start, other.end)
        else:
            raise NotImplementedError(f"Cannot add Span and {type(other)}")

    def __len__(self) -> int:
        """Returns the length of the span (end - start)."""
        return self.end - self.start

def non_whitespace_len(s: Union[str, bytes]) -> int:
    """Calculates the length of the string/bytes excluding whitespace."""
    if isinstance(s, bytes):
        s = s.decode('utf-8', errors='ignore') # Decode safely
    return len(re.sub(r"\s", "", s))

def get_line_number(byte_index: int, source_code: bytes) -> int:
    """Converts a byte index to a 0-indexed line number."""
    total_bytes = 0
    line_number = 0
    # Use splitlines(True) to keep newline characters for accurate byte counting
    lines = source_code.splitlines(True) 
    for i, line_bytes in enumerate(lines):
        if total_bytes + len(line_bytes) > byte_index:
            return i # Return 0-indexed line number
        total_bytes += len(line_bytes)
    # If byte_index is at or beyond the end, return the last line number
    return len(lines) -1 if lines else 0 

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
    
    # Identify imports and other metadata sections
    ignore_sections = []
    
    for pattern in lang_config.get("ignore_patterns", []):
        for match in re.finditer(pattern, code, re.MULTILINE):
            start_line = code[:match.start()].count('\n')
            end_line = start_line + code[match.start():match.end()].count('\n')
            ignore_sections.append((start_line, end_line + 1))  # +1 to include the last line
    
    result["ignore_sections"] = ignore_sections
    
    # Identify important structural elements (class definitions, methods, etc.)
    structure_points = []
    
    for pattern in lang_config.get("structure_markers", []):
        for match in re.finditer(pattern, code, re.MULTILINE):
            line_num = code[:match.start()].count('\n')
            structure_points.append(line_num)
    
    result["structure_points"] = sorted(structure_points)
    
    if verbose:
        print(f"[Info] Preprocessed {file_path} as {lang}")
        print(f"[Info] Found {len(ignore_sections)} sections to potentially ignore")
        print(f"[Info] Found {len(structure_points)} structural elements")
    
    # Add framework detection
    framework = detect_framework(code, file_path)
    if framework and verbose:
        print(f"[Info] Detected {framework} framework")
    
    result["framework"] = framework
    
    # If framework detected, add framework-specific patterns
    if framework and framework in WEB_FRAMEWORK_PATTERNS:
        framework_patterns = WEB_FRAMEWORK_PATTERNS[framework]
        special_handling = framework_patterns.get("special_handling", {})
        
        # Find framework-specific structural elements
        framework_elements = {}
        for element_type, pattern in special_handling.items():
            matches = []
            for match in re.finditer(pattern, code, re.MULTILINE):
                line_num = code[:match.start()].count('\n')
                matches.append((line_num, match.group(0)))
            framework_elements[element_type] = matches
        
        result["framework_elements"] = framework_elements
    
    return result

def explain_chunk_with_llm(openai_client, chunk_text: str, model: str = "gpt-4o-mini") -> str:
    """Explain the chunk content using a small-sized LLM."""
    # Initialize the LLM
    explain_prompt = f"""
    Use simple and concise language to explain the following code chunk:
    {chunk_text}
    """
    messages =[
        {"role": "system", "content": "You are a helpful assistant that explains code chunks."},
        {"role": "user", "content": explain_prompt}
    ]
    response = openai_client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0
    )
    # According to the annotation conect explain chunk
    explain = response.choices[0].message.content
    # 拼接新chunk
    new_chunk = f"{explain}\n{chunk_text}"
    return new_chunk

def chunk_code(
    code: str,
    file_path: str,
    max_chars: Optional[int] = None,
    coalesce: Optional[int] = None,
    verbose: bool = False,
) -> List[Span]:
    """
    Chunks the given code string based on syntax structure using grep-ast.

    Args:
        code: The source code as a string.
        file_path: The path to the file (used to determine language).
        max_chars: The approximate maximum number of characters per chunk.
        coalesce: Minimum non-whitespace characters for a chunk to not be merged.
        verbose: If True, print verbose logging.

    Returns:
        A list of Span objects representing the line ranges (0-indexed) of the chunks.
    """
    # Get language-specific configuration
    lang_config = get_language_config(file_path)
    
    # Use provided parameters or language defaults
    max_chars = max_chars or lang_config.get("max_chars", DEFAULT_MAX_CHARS)
    coalesce = coalesce or lang_config.get("coalesce_chars", DEFAULT_COALESCE_CHARS)
    
    # Get language for parsing
    lang = filename_to_lang(file_path)
    if not lang:
        if verbose:
            print(f"[Warning] Cannot determine language for {file_path}. Falling back to naive chunking.")
        # TODO: Implement naive line-based chunking fallback here
        return [] # Placeholder for naive chunker

    try:
        language = get_language(lang)
        parser = get_parser(lang)
        if verbose:
             print(f"[Info] Using language '{lang}' for parsing {file_path}.")
    except Exception as e:
        print(f"[Error] Failed to load parser for language '{lang}' ({file_path}): {e}")
        print(traceback.format_exc())
        # TODO: Implement naive line-based chunking fallback here
        return [] # Placeholder for naive chunker

    code_bytes = code.encode("utf-8")
    tree = None
    try:
        tree = parser.parse(code_bytes)
    except Exception as e:
        print(f"[Error] Failed to parse {file_path}: {e}")
        # TODO: Implement naive line-based chunking fallback here
        return [] # Placeholder for naive chunker

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
                if len(current_chunk) > 0 : # Don't add empty chunks
                     chunks.append(current_chunk)
                # Start new chunk after this large child
                current_chunk = Span(child.end_byte, child.end_byte) 
                chunks.extend(chunk_node(child))
            elif child_byte_len + current_chunk_byte_len > max_chars:
                # Adding child makes current chunk too large, finalize current chunk
                if len(current_chunk) > 0: # Don't add empty chunks
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
                 current_chunk.end = node.end_byte # Should not happen if children cover node? Safety check.
             elif current_chunk.end < node.end_byte and current_chunk.start == node.start_byte and not chunks :
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
        if tree.root_node.end_byte > 0 :
             byte_chunks = [Span(0, tree.root_node.end_byte)]
        else:
             return [] # Empty file

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
    current_chunk = Span(0, 0) # Initialize an empty span
    is_first_chunk = True

    for chunk in byte_chunks:
        if is_first_chunk:
            current_chunk = chunk # Start with the first chunk
            is_first_chunk = False
        else:
             # Add the next chunk to the current one being built
            current_chunk += chunk # Uses Span.__add__

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
         # Ensure end_line is at least start_line + 1 for non-empty chunks,
         # or exactly start_line if start/end bytes fall within the same line.
         # Also handle the case where chunk.end points exactly to the start of a line.

         # If end byte is start of next line, the span should end *before* that line.
         # But get_line_number might return the index *of* that next line.
         # Let's refine: if end byte isn't the very end of the file, and it matches
         # the start byte of the *next* chunk (if one exists), maybe end one line earlier?
         # Simpler: Use end_byte-1 for end_line calculation unless it's the last byte.
         
         effective_end_byte = chunk.end
         if chunk.end > 0 and chunk.end == tree.root_node.end_byte:
             # If it's the very end of the file, get line number for the last byte
             effective_end_byte = chunk.end - 1
         elif chunk.end > chunk.start :
             # Otherwise, consider the character *before* the end byte index
             effective_end_byte = chunk.end -1

         if effective_end_byte < chunk.start: # Handle zero-length or weird chunks
              effective_end_byte = chunk.start # Avoid negative length issues

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

            # Create separate chunks for imports or other ignorable sections
            # This is a simplified approach - for a more sophisticated implementation,
            # we'd need to consider how these sections interact with existing chunks
    
    if verbose:
        print(f"[Info] Generated {len(final_line_chunks)} chunks for {file_path}")
        
    return final_line_chunks

@dataclass
class ChunkInfo:
    """Enhanced information about a code chunk."""
    span: Span
    text: str
    chunk_type: str = "code"  # code, imports, mixed, etc.
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def start_line(self) -> int:
        return self.span.start
    
    @property
    def end_line(self) -> int:
        return self.span.end

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

def create_chunk_infos(spans: List[Span], code: str, file_path: str) -> List[ChunkInfo]:
    """Create ChunkInfo objects from spans with enhanced metadata."""
    chunk_infos = []
    
    for span in spans:
        chunk_text = span.extract_lines(code)
        analysis = analyze_chunk_content(chunk_text, file_path)
        
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
            }
        )
        
        chunk_infos.append(chunk_info)
    
    return chunk_infos

# --- Example Usage (Optional) ---
if __name__ == "__main__":
    import sys
    import re
    
    # Check if a file path is provided as a command line argument
    if len(sys.argv) < 2:
        print("Usage: python chunker.py <file_path>")
        print("Example: python chunker.py /path/to/your/file.py")
        sys.exit(1)
        
    file_path = sys.argv[1]
    
    # Check if the file exists
    if not os.path.exists(file_path):
        print(f"[Error] File not found: {file_path}")
        sys.exit(1)
        
    # Read the file content
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            file_content = f.read()
    except Exception as e:
        print(f"[Error] Failed to read file {file_path}: {e}")
        sys.exit(1)
        
    print(f"--- Analyzing {file_path} ---")
    
    # Get language-specific configuration
    lang_config = get_language_config(file_path)
    
    print(f"[Info] Using configuration for {filename_to_lang(file_path) or 'unknown'} language")
    print(f"[Info] Max chars per chunk: {lang_config['max_chars'] // AVG_CHAR_IN_LINE} lines (~{lang_config['max_chars']} chars)")
    
    # Analyze the file with our enhanced chunker
    chunks = chunk_code(
        file_content,
        file_path,
        max_chars=lang_config["max_chars"],
        coalesce=lang_config["coalesce_chars"],
        verbose=True
    )
    
    # Create enhanced chunk information
    chunk_infos = create_chunk_infos(chunks, file_content, file_path)
    
    print(f"\n--- Generated {len(chunk_infos)} Chunks: ---")
    for i, chunk_info in enumerate(chunk_infos):
        # Create a descriptive chunk type label
        chunk_type_str = f" ({chunk_info.chunk_type.upper()})"
        
        # Add framework info if available
        framework = chunk_info.metadata.get("framework")
        if framework:
            chunk_type_str += f" [{framework}]"
            
        # Add special pattern matches if any
        special_matches = chunk_info.metadata.get("special_matches", {})
        if special_matches:
            special_types = list(special_matches.keys())
            if special_types:
                chunk_type_str += f" ({', '.join(special_types)})"
        
        print(f"\n--- Chunk {i+1}{chunk_type_str} (Lines {chunk_info.start_line}-{chunk_info.end_line-1}) ---")
        
        # Print quality score for debugging
        quality = chunk_info.metadata.get("quality", 0)
        print(f"[Quality: {quality:.2f}]")
        
        print(chunk_info.text)