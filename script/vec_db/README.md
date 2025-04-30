# Code RAG System with SQLite-Vec

A vectorized code repository search system that provides semantic search and retrieval of code snippets using SQLite-Vec. The system leverages your custom chunker to intelligently split code files and extract semantic structure.

## Features

- **SQLite-Vec Integration**: Uses SQLite-Vec for efficient vector similarity search
- **Code Chunking**: Leverages your intelligent code chunker to break code into meaningful segments
- **Semantic Structure**: Preserves code structure (functions, classes, imports) for better search context
- **Framework Detection**: Automatically identifies web frameworks used in code files
- **Version Tracking**: Supports Git commit tracking for code versioning
- **Multiple Search Options**: Vector, keyword, and hybrid search capabilities
- **Filtering**: Filter by language, framework, repository, and element type
- **Command-line Interface**: Easy-to-use CLI for all operations

## Installation

### Prerequisites

- Python 3.7+
- SQLite 3
- SQLite-Vec extension

### Setup

1. Clone this repository:
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. Install dependencies:
   ```bash
   pip install -r script/vec_db/requirements.txt
   ```

3. Initialize the database:
   ```bash
   python -m script.vec_db.cli init --db-path code_rag.db
   ```

## Database Schema

The system uses a structured database schema:

- **code_files**: Stores file metadata and structure information
- **code_blocks**: Stores individual code chunks with metadata
- **semantic_elements**: Stores semantic elements (functions, classes, etc.)
- **embeddings**: Stores vector embeddings for code blocks using SQLite-Vec
- **special_patterns**: Stores special pattern matches (e.g., REST endpoints, React components)
- **file_versions**: Tracks Git versions of files

## Usage

### Indexing Files

Index a single file:
```bash
python -m script.vec_db.cli index --file-path path/to/file.py --repo-name my-repo
```

Index a directory:
```bash
python -m script.vec_db.cli index --dir-path path/to/code --repo-name my-repo --file-extensions .py,.java,.js
```

### Searching Code

Vector search (default):
```bash
python -m script.vec_db.cli search "implement a binary search tree"
```

Keyword search:
```bash
python -m script.vec_db.cli search "database connection" --search-type keyword
```

Hybrid search with filtering:
```bash
python -m script.vec_db.cli search "authentication middleware" --search-type hybrid --language javascript --framework react
```

Show context with results:
```bash
python -m script.vec_db.cli search "parse JSON" --show-context --context-lines 10
```

### Database Management

View database statistics:
```bash
python -m script.vec_db.cli stats
```

Delete repository:
```bash
python -m script.vec_db.cli delete --repo-name my-repo
```

## API Usage

You can also use the system programmatically:

```python
from script.vec_db.api import CodeRAGAPI

# Initialize API
api = CodeRAGAPI(db_path="code_rag.db")

# Index files
api.initialize_database()
api.index_file(file_path="main.py", repo_name="my-project")

# Search code
results = api.search(
    query="implement oauth authentication",
    top_k=5,
    language="python",
    search_type="vector"
)

# Process results
for result in results:
    print(f"File: {result['file_path']} (Lines {result['start_line']+1}-{result['end_line']})")
    print(result['content'])

# Close connection
api.close()
```

## Chunker Integration

The system integrates with your custom code chunker to:

1. Split files into semantic chunks based on language-specific patterns
2. Extract parser fragments for semantic structure
3. Detect special patterns and frameworks
4. Calculate chunk quality metrics

Chunks are stored with metadata including:
- Line range (start_line, end_line)
- Content statistics (non_whitespace_len, quality_score)
- Type classification (code, imports, mixed, etc.)
- Framework detection

## Embedding Generation

Code embeddings are generated using:

1. **Primary**: sentence-transformers with bge-m3 (default)
2. **Fallback**: Simple hash-based embeddings for testing without dependencies

Metadata is included in embedding context for better semantic understanding:
- Language
- Framework 
- Element type
- Code structure

## SQLite-Vec Integration

The system uses SQLite-Vec's MATCH operator for efficient vector similarity search:

```sql
SELECT 
    code_block_id,
    content,
    distance
FROM embeddings
WHERE embedding MATCH ?
ORDER BY distance
LIMIT 5
```

## Performance Considerations

- **Batch Processing**: Use directory indexing for large repositories
- **Embedding Model**: The default "bge-m3" model offers a good balance of quality and size
- **Hardware Acceleration**: GPU support is enabled automatically when available
- **Database Size**: Each indexed file requires approximately:
  - 1 code_files record
  - 3-10 code_blocks records (depending on file size/complexity)
  - 5-20 semantic_elements records (depending on code structure)
  - 1 embedding record per code block (384 dimensions by default)

## License

[MIT License](LICENSE) 