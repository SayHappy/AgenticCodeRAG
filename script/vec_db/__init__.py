"""
Code RAG System - A vector database for code search and retrieval

This package provides semantic code search and retrieval using SQLite-Vec.
"""

__version__ = "0.1.0"

from script.vec_db.api import CodeRAGAPI
from script.vec_db.database import CodeRAGDatabase
from script.vec_db.embeddings import EmbeddingGenerator

__all__ = ["CodeRAGAPI", "CodeRAGDatabase", "EmbeddingGenerator"] 