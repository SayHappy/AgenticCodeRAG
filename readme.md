# Code Analysis Tools

This directory contains tools for parsing and analyzing code files across multiple programming languages.

## Quick Start
python3.10

```shell
# step.1
$ pip install -r requirements.txt

# step.2 download embedding model
# read model/README.md

# step.3 build index
# read script/vec_db/README.md
$ python -m script.vec_db.cli index --dir-path path/to/code --repo-name my-repo

# step.4 fill api_key and base repo overview
# reposearch_agent/start.py
# llm_cfg = {'model': 'qwen-turbo-2025-02-11', "api_key": ""}
# Project Overview:
# language java: 98%,shell: 2%
# ```shell
# $ ls
# Dockerfile
# ...


# step.5 file you repo_dir reposearch_agent/config.py
# DEFAULT_REPO_DIR = "your_repo_path"

# step.6 start server
python -m reposearch_agent.start
```

## Tools

### File Parser (`file_parser.py`)

A multi-language file parser based on the abstract factory pattern that analyzes source code files and extracts their structure.

**Usage:**
```bash
python3 script/file_parser.py <file_path>
```

**Supported file types:**
- Markdown (`.md`) - Extracts headings, code blocks
- TypeScript/React (`.tsx`) - Extracts imports, components, hooks, functions, methods
- Java (`.java`) - Extracts package, imports, classes, methods, fields

**Example output:**
```
# For markdown files
├── Primary Headings
├── Secondary Headings
├── Tertiary Headings
└── Code Blocks

# For TypeScript/React files
├── Imports
├── Components
├── Hooks
├── Functions
├── Methods
└── Variables

# For Java files
├── Package
├── Imports
├── Classes
├── Methods
└── Fields
```

### File Chunker (`file_chunker.py`)

Intelligently splits source code files into logical chunks for easier processing or analysis.

**Usage:**
```bash
python3 script/file_chunker.py <file_path>
```

**Features:**
- Splits files into meaningful chunks based on code structure
- Identifies semantic sections (imports, code blocks, etc.)
- Maintains line number references for traceability

**Example output:**
```
--- Generated 4 Chunks for script/testfile/javafile.java ---

--- Chunk 1 (IMPORTS) (Lines 0-28) ---
...

--- Chunk 2 (CODE) [spring] (services) (Lines 29-101) ---
...

--- Chunk 3 (CODE) (Lines 101-154) ---
...

--- Chunk 4 (CODE) (Lines 154-181) ---
...
```

## Use Cases

- Code analysis and understanding
- Preprocessing code for LLM input
- Structural visualization of codebases
- Identifying code organization patterns
