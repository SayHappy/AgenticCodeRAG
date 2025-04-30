#!/usr/bin/env python3
"""
Example usage of the Code RAG system
"""

import os
import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from script.vec_db.api import CodeRAGAPI

def example_init():
    """Initialize database example"""
    print("\n=== Initializing Database ===")
    
    # Create a temporary database for demonstration
    db_path = "example_code_rag.db"
    
    # Remove existing database if it exists
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"Removed existing database: {db_path}")
    
    # Initialize API and database
    api = CodeRAGAPI(db_path=db_path)
    api.initialize_database()
    print(f"Initialized database at: {db_path}")
    
    api.close()
    return db_path

def example_index(db_path):
    """Index code file example"""
    print("\n=== Indexing Code Files ===")
    
    # Find script directory for samples
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Use this file as a sample
    sample_file = os.path.abspath(__file__)
    print(f"Using sample file: {sample_file}")
    
    # Initialize API
    api = CodeRAGAPI(db_path=db_path, embedding_model="../../model/bge-m3")
    
    # Index the sample file
    result = api.index_file(
        file_path=sample_file,
        repo_name="example-repo"
    )
    
    if result["success"]:
        print(f"Successfully indexed file with {result['chunks_indexed']} chunks")
    else:
        print(f"Failed to index file: {result.get('error', 'Unknown error')}")
    
    # Try to find more Python files in the parent directory
    parent_dir = os.path.dirname(script_dir)
    print(f"\nIndexing Python files in: {parent_dir}")
    
    result = api.index_directory(
        dir_path=parent_dir,
        repo_name="example-repo",
        file_extensions=[".py"],
        recursive=False  # Only index files directly in the directory
    )
    
    if result["success"]:
        print(f"Successfully indexed {result['files_indexed']} files with {result['total_chunks']} chunks")
        if result["files_failed"] > 0:
            print(f"Failed to index {result['files_failed']} files")
    else:
        print(f"Failed to index directory: {result.get('error', 'Unknown error')}")
    
    api.close()

def example_search(db_path):
    """Search code example"""
    print("\n=== Searching Code ===")
    
    # Initialize API
    api = CodeRAGAPI(db_path=db_path)
    
    # Example queries
    queries = [
        "initialize database connection",
        "parse arguments from command line",
        "handle file reading operations"
    ]
    
    for query in queries:
        print(f"\nSearching for: '{query}'")
        
        # Vector search
        results = api.search(
            query=query,
            top_k=2,
            repo_name="example-repo",
            search_type="vector"
        )
        
        if results:
            print(f"Found {len(results)} results:")
            for i, result in enumerate(results):
                print(f"  Result {i+1}: {result['file_path']} (Lines {result['start_line']+1}-{result['end_line']})")
                # Print first line of the content
                first_line = result['content'].splitlines()[0] if result['content'] else ""
                if len(first_line) > 60:
                    first_line = first_line[:57] + "..."
                print(f"    {first_line}")
        else:
            print("No results found")
    
    # Try hybrid search
    print("\nTrying hybrid search for 'database connection'")
    results = api.search(
        query="database connection",
        top_k=3,
        search_type="hybrid"
    )
    
    if results:
        print(f"Found {len(results)} results:")
        for i, result in enumerate(results):
            print(f"  Result {i+1}: {result['file_path']} (Lines {result['start_line']+1}-{result['end_line']})")
    else:
        print("No results found")
    
    api.close()

def example_stats(db_path):
    """Show database statistics example"""
    print("\n=== Database Statistics ===")
    
    # Initialize API
    api = CodeRAGAPI(db_path=db_path)
    
    # Get stats
    stats = api.get_stats()
    
    print(f"Total files: {stats['total_files']}")
    print(f"Total blocks: {stats['total_blocks']}")
    print(f"Total elements: {stats['total_elements']}")
    print(f"Total embeddings: {stats['total_embeddings']}")
    
    if stats['languages']:
        print("\nLanguage Distribution:")
        for lang, count in stats['languages'].items():
            print(f"  {lang}: {count}")
    
    api.close()

def example_cleanup(db_path):
    """Clean up example"""
    print("\n=== Cleaning Up ===")
    
    # Remove database file
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"Removed database: {db_path}")

def run_all_examples():
    """Run all examples"""
    try:
        # Initialize
        db_path = example_init()
        
        # Run examples
        example_index(db_path)
        example_search(db_path)
        example_stats(db_path)
        
        # Clean up
        example_cleanup(db_path)
        
    except Exception as e:
        print(f"Error running examples: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_all_examples() 