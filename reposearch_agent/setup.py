"""Setup script for the reposearch agent"""

import os
import sys
import argparse
import subprocess
from pathlib import Path

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def setup_database(args):
    """Initialize and index the database"""
    
    # Get the path to the CLI script
    cli_path = Path(__file__).parent.parent / "script" / "vec_db" / "cli.py"
    
    print(f"Setting up the database at {args.db_path}...")
    
    # Initialize the database
    cmd = [
        sys.executable, 
        str(cli_path), 
        "--db-path", args.db_path,
        "--embedding-model", args.embedding_model,
        "--embedding-dim", str(args.embedding_dim),
        "init"
    ]
    
    print("Initializing the database...")
    result = subprocess.run(cmd, check=True)
    
    if result.returncode != 0:
        print("Error initializing the database.")
        return False
    
    # Index the repository
    if args.repo_path:
        print(f"Indexing repository {args.repo_name} at {args.repo_path}...")
        cmd = [
            sys.executable, 
            str(cli_path), 
            "--db-path", args.db_path,
            "--embedding-model", args.embedding_model,
            "--embedding-dim", str(args.embedding_dim),
            "index",
            "--dir-path", args.repo_path,
            "--repo-name", args.repo_name
        ]
        
        if args.file_extensions:
            cmd.extend(["--file-extensions", args.file_extensions])
        
        result = subprocess.run(cmd, check=True)
        
        if result.returncode != 0:
            print("Error indexing the repository.")
            return False
    
    # Show stats
    print("Database setup completed. Showing statistics...")
    cmd = [
        sys.executable, 
        str(cli_path), 
        "--db-path", args.db_path,
        "stats"
    ]
    
    subprocess.run(cmd, check=True)
    
    # Update configuration
    update_config(args)
    
    return True


def update_config(args):
    """Update the config.py file with the provided settings"""
    config_path = Path(__file__).parent / "config.py"
    
    # Read the current config
    with open(config_path, 'r') as f:
        config_content = f.read()
    
    # Update values
    config_updates = {
        "DB_PATH": f'os.environ.get("CODEBASE_DB_PATH", "{args.db_path}")',
        "EMBEDDING_MODEL": f'os.environ.get("EMBEDDING_MODEL", "{args.embedding_model}")',
        "EMBEDDING_DIM": f'int(os.environ.get("EMBEDDING_DIM", "{args.embedding_dim}"))',
        "DEFAULT_REPO_NAME": f'os.environ.get("DEFAULT_REPO_NAME", "{args.repo_name}")'
    }
    
    for key, value in config_updates.items():
        # Simple search and replace for the specific variable
        line_prefix = f"{key} = "
        lines = config_content.split('\n')
        for i, line in enumerate(lines):
            if line.startswith(line_prefix):
                lines[i] = f"{line_prefix}{value}"
        
        config_content = '\n'.join(lines)
    
    # Write updated config
    with open(config_path, 'w') as f:
        f.write(config_content)
    
    print(f"Updated configuration in {config_path}")


def main():
    """Main entry point for the setup script"""
    parser = argparse.ArgumentParser(description="Setup script for the reposearch agent")
    
    parser.add_argument("--db-path", type=str, default="code_rag.db", 
                      help="Path to the database file")
    parser.add_argument("--embedding-model", type=str, default="./model/bge-m3", 
                      help="Path to the embedding model")
    parser.add_argument("--embedding-dim", type=int, default=1024, 
                      help="Dimension of the embeddings")
    parser.add_argument("--repo-path", type=str, 
                      help="Path to the repository to index")
    parser.add_argument("--repo-name", type=str, default="default-repo", 
                      help="Name of the repository to index")
    parser.add_argument("--file-extensions", type=str, 
                      help="Comma-separated list of file extensions to index (e.g., .py,.js,.jsx)")
    
    args = parser.parse_args()
    
    if setup_database(args):
        print("\nSetup completed! You can now run the agent:")
        print("  python start.py")


if __name__ == "__main__":
    main() 