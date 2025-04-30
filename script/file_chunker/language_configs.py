#!/usr/bin/env python3
"""
Language-specific configurations for the file chunker.
"""

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

# Web framework patterns
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