# Code Repository Search Agent

A code repository search chatbot built with Qwen Agent that allows you to search and understand your codebase through natural language queries.

## Features

- Semantic code search using vector embeddings
- Hybrid search combining vector and keyword-based approaches
- Support for filtering by language, framework, and element type
- Detailed code snippets with relevant context

## Setup

### Requirements

1. Install the required dependencies:

```bash
cd reposearch_agent
pip install -r requirements.txt
```

### Quick Setup

The easiest way to get started is to use the setup script:

```bash
cd reposearch_agent
python setup.py --repo-path /path/to/your/code --repo-name your-repo-name
```

This will:
- Initialize the vector database
- Index your codebase
- Configure the agent to use your repository by default

Additional options:
```
--db-path            Path to the database file (default: code_rag.db)
--embedding-model    Path to the embedding model (default: ./model/bge-m3)
--embedding-dim      Dimension of the embeddings (default: 1024)
--file-extensions    Comma-separated list of file extensions to index (e.g., .py,.js,.jsx)
```

### Manual Setup

If you prefer to set up manually:

1. Initialize the database:

```bash
cd script/vec_db
python cli.py init
```

2. Index your codebase:

```bash
python cli.py index --dir-path /path/to/your/code --repo-name your-repo-name
```

### Configuration

You can configure the agent by setting environment variables:

- `CODEBASE_DB_PATH`: Path to the vector database file (default: "code_rag.db")
- `EMBEDDING_MODEL`: Path to the embedding model (default: "./model/bge-m3")
- `EMBEDDING_DIM`: Dimension of the embeddings (default: 1024)
- `MODEL_CACHE_DIR`: Directory to cache the models (optional)
- `DEFAULT_TOP_K`: Default number of results to return (default: 5)
- `DEFAULT_SEARCH_TYPE`: Default search type (default: "vector", options: "vector", "keyword", "hybrid")
- `DEFAULT_REPO_NAME`: Default repository name to search in (optional)

Alternatively, you can modify the values in `reposearch_agent/config.py`.

## Usage

### Start the Web UI

```bash
cd reposearch_agent
python start.py
```

This will launch a web interface where you can interact with the code search agent.

### Example Queries

- "How is database connection implemented?"
- "Find functions that handle file parsing"
- "Show me authentication-related code"
- "Explain how error handling works"
- "Find code that processes network requests"

### Filtering Results

You can refine your search using specific parameters:

- Repository: "Search for API handlers in the backend repository"
- Language: "Find Python code that implements caching"
- Framework: "Show React components for user interface"
- Element Type: "Show me class definitions for data models"

## Advanced Usage

For automated testing or scripting, you can use the CLI mode:

```bash
cd reposearch_agent
python -c "from start import test; test('find database connection code')"
```

Or run in terminal UI mode:

```bash
cd reposearch_agent
python -c "from start import app_tui; app_tui()"
```
