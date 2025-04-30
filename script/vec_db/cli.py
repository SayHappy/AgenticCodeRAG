#!/usr/bin/env python3
import argparse
import os
import sys
import json
import time
from typing import Dict, Any, List, Optional

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from script.vec_db.api import CodeRAGAPI

def format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable format"""
    if seconds < 60:
        return f"{seconds:.2f} seconds"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes} min {secs:.2f} sec"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours} hr {minutes} min"

def get_api(args) -> CodeRAGAPI:
    """Get API instance from args"""
    return CodeRAGAPI(
        db_path=args.db_path,
        embedding_model=args.embedding_model,
        embedding_dim=args.embedding_dim,
        cache_dir=args.cache_dir
    )

def cmd_init(args):
    """Initialize database"""
    api = get_api(args)
    
    print(f"Initializing database at {args.db_path}...")
    api.initialize_database()
    print("Database initialized successfully.")
    
    api.close()
    return 0

def cmd_index(args):
    """Index files or directories"""
    api = get_api(args)
    
    if not args.file_path and not args.dir_path:
        print("Error: Either --file-path or --dir-path must be specified")
        return 1
    
    # Make sure database is initialized
    api.initialize_database()
    
    if args.file_path:
        # Index a single file
        file_path = os.path.abspath(args.file_path)
        print(f"Indexing file: {file_path}")
        
        result = api.index_file(
            file_path=file_path,
            repo_name=args.repo_name,
            git_commit=args.git_commit,
            structure_file=args.structure_file
        )
        
        if result["success"]:
            print(f"✓ File indexed successfully")
            print(f"  - Chunks indexed: {result['chunks_indexed']}")
            print(f"  - Elements indexed: {result['elements_indexed']}")
            print(f"  - Duration: {format_duration(result['duration_seconds'])}")
        else:
            print(f"✗ Failed to index file: {result.get('error', 'Unknown error')}")
            return 1
    else:
        # Index a directory
        dir_path = os.path.abspath(args.dir_path)
        print(f"Indexing directory: {dir_path}")
        
        extensions = args.file_extensions.split(",") if args.file_extensions else None
        
        result = api.index_directory(
            dir_path=dir_path,
            repo_name=args.repo_name,
            file_extensions=extensions,
            git_commit=args.git_commit,
            recursive=not args.non_recursive
        )
        
        if result["success"]:
            print(f"✓ Directory indexed successfully")
            print(f"  - Files indexed: {result['files_indexed']}")
            print(f"  - Files failed: {result['files_failed']}")
            print(f"  - Total chunks: {result['total_chunks']}")
            print(f"  - Total elements: {result['total_elements']}")
            print(f"  - Duration: {format_duration(result['duration_seconds'])}")
            
            if result["files_failed"] > 0 and args.verbose:
                print("\nFailed files:")
                for failed in result["failed_files"]:
                    print(f"  - {failed['file_path']}: {failed['error']}")
        else:
            print(f"✗ Failed to index directory: {result.get('error', 'Unknown error')}")
            return 1
    
    api.close()
    return 0

def cmd_search(args):
    """Search code"""
    api = get_api(args)
    
    print(f"Searching for: {args.query}")
    print(f"Search type: {args.search_type}")
    
    filters = {}
    if args.repo_name:
        filters["repo_name"] = args.repo_name
        print(f"Repository filter: {args.repo_name}")
        
    if args.language:
        filters["language"] = args.language
        print(f"Language filter: {args.language}")
        
    if args.framework:
        filters["framework"] = args.framework
        print(f"Framework filter: {args.framework}")
        
    if args.element_type:
        filters["element_type"] = args.element_type
        print(f"Element type filter: {args.element_type}")
    
    start_time = time.time()
    results = api.search(
        query=args.query,
        top_k=args.top_k,
        repo_name=args.repo_name,
        language=args.language,
        framework=args.framework,
        element_type=args.element_type,
        search_type=args.search_type
    )
    duration = time.time() - start_time
    
    if not results:
        print("No results found.")
        return 0
    
    print(f"\nFound {len(results)} results ({format_duration(duration)}):\n")
    
    for i, result in enumerate(results):
        print(f"Result {i+1}:")
        print(f"  File: {result['file_path']}")
        print(f"  Lines: {result['start_line']+1}-{result['end_line']}")
        print(f"  Language: {result['language']}")
        if 'framework' in result and result['framework']:
            print(f"  Framework: {result['framework']}")
        if 'similarity_score' in result:
            print(f"  Similarity: {result['similarity_score']:.4f}")
        
        if 'semantic_elements' in result and result['semantic_elements']:
            elements = result['semantic_elements']
            print(f"  Context elements ({len(elements)}):")
            for elem in elements[:3]:  # Show up to 3 elements
                element_type = elem.get('element_type', 'Unknown')
                name = elem.get('name', 'Unnamed')
                start_line = elem.get('start_line', 0)
                end_line = elem.get('end_line', 0)
                print(f"    - {element_type}: {name} (Lines {start_line+1}-{end_line})")
            if len(elements) > 3:
                print(f"    - ... and {len(elements) - 3} more")
                
        if args.show_context:
            context_lines = min(args.context_lines, 10)  # Limit to avoid huge output
            content = result['content']
            if len(content.splitlines()) > context_lines:
                # Truncate to context_lines
                lines = content.splitlines()
                middle = len(lines) // 2
                start = max(0, middle - context_lines // 2)
                end = min(len(lines), start + context_lines)
                truncated = "\n".join(lines[start:end])
                print(f"\n  Content (truncated):\n```\n{truncated}\n...\n```")
            else:
                print(f"\n  Content:\n```\n{content}\n```")
        else:
            # Just show one line summary
            first_line = result['content'].splitlines()[0] if result['content'] else ""
            if len(first_line) > 60:
                first_line = first_line[:57] + "..."
            print(f"  Summary: {first_line}")
            
        print()
    
    api.close()
    return 0

def cmd_delete(args):
    """Delete repository or file"""
    api = get_api(args)
    
    if args.repo_name and args.file_path:
        # Delete specific file
        file_path = os.path.abspath(args.file_path)
        print(f"Deleting file: {file_path} from repo: {args.repo_name}")
        
        success = api.db.delete_file(args.repo_name, file_path)
        if success:
            print("✓ File deleted successfully")
        else:
            print("✗ Failed to delete file")
            return 1
    elif args.repo_name:
        # Delete entire repository
        print(f"Deleting entire repository: {args.repo_name}")
        
        if not args.force:
            confirm = input(f"Are you sure you want to delete all files in repository '{args.repo_name}'? (y/N): ")
            if confirm.lower() != 'y':
                print("Operation cancelled.")
                return 0
        
        success = api.delete_repository(args.repo_name)
        if success:
            print("✓ Repository deleted successfully")
        else:
            print("✗ Failed to delete repository")
            return 1
    else:
        print("Error: --repo-name is required")
        return 1
    
    api.close()
    return 0

def cmd_stats(args):
    """Show database statistics"""
    api = get_api(args)
    
    stats = api.get_stats()
    
    print("Database Statistics:")
    print(f"Total files: {stats['total_files']}")
    print(f"Total blocks: {stats['total_blocks']}")
    print(f"Total elements: {stats['total_elements']}")
    print(f"Total embeddings: {stats['total_embeddings']}")
    
    if stats['languages']:
        print("\nLanguage Distribution:")
        for lang, count in stats['languages'].items():
            print(f"  {lang}: {count}")
    
    if stats['frameworks']:
        print("\nFramework Distribution:")
        for fw, count in stats['frameworks'].items():
            print(f"  {fw}: {count}")
    
    if stats['repositories']:
        print("\nRepository Distribution:")
        for repo, count in stats['repositories'].items():
            print(f"  {repo}: {count}")
    
    api.close()
    return 0

def main():
    """Main CLI entrypoint"""
    parser = argparse.ArgumentParser(description="Code RAG Database CLI")
    parser.add_argument("--db-path", type=str, default="code_rag.db", help="Path to database file")
    parser.add_argument("--embedding-model", type=str, default="./model/bge-m3", help="Embedding model to use")
    parser.add_argument("--embedding-dim", type=int, default=1024, help="Embedding dimensions")
    parser.add_argument("--cache-dir", type=str, help="Cache directory for models")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # init command
    init_parser = subparsers.add_parser("init", help="Initialize database")
    
    # index command
    index_parser = subparsers.add_parser("index", help="Index files or directories")
    index_parser.add_argument("--file-path", type=str, help="Path to file to index")
    index_parser.add_argument("--dir-path", type=str, help="Path to directory to index")
    index_parser.add_argument("--repo-name", type=str, required=True, help="Repository name")
    index_parser.add_argument("--git-commit", type=str, help="Git commit hash")
    index_parser.add_argument("--structure-file", type=str, help="Path to pre-parsed structure file")
    index_parser.add_argument("--file-extensions", type=str, help="Comma-separated list of file extensions to index")
    index_parser.add_argument("--non-recursive", action="store_true", help="Do not recursively process directories")
    
    # search command
    search_parser = subparsers.add_parser("search", help="Search code")
    search_parser.add_argument("query", type=str, help="Search query")
    search_parser.add_argument("--repo-name", type=str, help="Repository filter")
    search_parser.add_argument("--language", type=str, help="Language filter")
    search_parser.add_argument("--framework", type=str, help="Framework filter")
    search_parser.add_argument("--element-type", type=str, help="Element type filter")
    search_parser.add_argument("--top-k", type=int, default=5, help="Number of results to return")
    search_parser.add_argument("--search-type", type=str, default="vector", 
                             choices=["vector", "keyword", "hybrid"], help="Search type")
    search_parser.add_argument("--show-context", action="store_true", help="Show code context in results")
    search_parser.add_argument("--context-lines", type=int, default=5, help="Number of context lines to show")
    
    # delete command
    delete_parser = subparsers.add_parser("delete", help="Delete repository or file")
    delete_parser.add_argument("--repo-name", type=str, help="Repository name")
    delete_parser.add_argument("--file-path", type=str, help="Path to file to delete")
    delete_parser.add_argument("--force", action="store_true", help="Do not ask for confirmation")
    
    # stats command
    stats_parser = subparsers.add_parser("stats", help="Show database statistics")
    
    args = parser.parse_args()
    
    if args.command == "init":
        return cmd_init(args)
    elif args.command == "index":
        return cmd_index(args)
    elif args.command == "search":
        return cmd_search(args)
    elif args.command == "delete":
        return cmd_delete(args)
    elif args.command == "stats":
        return cmd_stats(args)
    else:
        parser.print_help()
        return 1

if __name__ == "__main__":
    sys.exit(main()) 