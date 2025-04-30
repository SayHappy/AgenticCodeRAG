"""Configuration settings for the reposearch agent"""

import os

# Database configuration
DB_PATH = os.environ.get("CODEBASE_DB_PATH", "code_rag.db")

# Embedding model configuration
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "./model/bge-m3")
EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", "1024"))
CACHE_DIR = os.environ.get("MODEL_CACHE_DIR", None)

# Search configuration
DEFAULT_TOP_K = int(os.environ.get("DEFAULT_TOP_K", "10"))
DEFAULT_SEARCH_TYPE = os.environ.get("DEFAULT_SEARCH_TYPE", "hybrid")

# Repository configuration
DEFAULT_REPO_NAME = "your_repo_name"
DEFAULT_REPO_DIR = "your_repo_path"