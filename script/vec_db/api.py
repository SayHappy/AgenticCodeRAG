import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple
import time
import traceback

# Add parent directory to path if running as script
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from script.vec_db.database import CodeRAGDatabase
from script.vec_db.embeddings import EmbeddingGenerator

class CodeRAGAPI:
    """High-level API for the Code RAG system"""
    
    def __init__(
        self,
        db_path: str = "code_rag.db",
        embedding_model: str = "bge-m3",
        embedding_dim: int = 1024,
        cache_dir: Optional[str] = None
    ):
        """
        Initialize the Code RAG API
        
        Args:
            db_path: Path to the SQLite database
            embedding_model: Model to use for embeddings
            embedding_dim: Dimension of embeddings
            cache_dir: Optional directory to cache model files
        """
        self.db_path = db_path
        self.db = CodeRAGDatabase(db_path, dim=embedding_dim)
        self.embedder = EmbeddingGenerator(model_name=embedding_model, cache_dir=cache_dir)
        
    def initialize_database(self):
        """Initialize the database schema"""
        self.db.initialize_database()
        # Check if schema needs updates for existing database
        return self.db.check_and_update_schema()
    
    def _get_chunker(self):
        """Import and return the code chunker"""
        try:
            from script.file_chunker.main import parse_file
            return parse_file
        except ImportError:
            try:
                # Try to import from a different location
                sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
                from script.file_chunker.main import parse_file
                return parse_file
            except ImportError:
                print("Error: File chunker module not found. Please make sure it's available.")
                raise
    
    def _get_file_language(self, file_path: str) -> str:
        """Get language from file extension"""
        try:
            from grep_ast import filename_to_lang
            lang = filename_to_lang(file_path)
            return lang or "unknown"
        except ImportError:
            # Fallback to simple extension mapping
            ext = os.path.splitext(file_path)[1].lower()
            lang_map = {
                '.py': 'python',
                '.js': 'javascript', 
                '.jsx': 'jsx',
                '.ts': 'typescript',
                '.tsx': 'tsx',
                '.java': 'java',
                '.go': 'go',
                '.html': 'html',
                '.css': 'css',
                '.cpp': 'cpp',
                '.c': 'c',
                '.rb': 'ruby'
            }
            return lang_map.get(ext, "unknown")
    
    def _detect_framework(self, code: str, file_path: str) -> Optional[str]:
        """Detect web framework used in code"""
        try:
            from script.vec_db.chunker import detect_framework
            return detect_framework(code, file_path)
        except ImportError:
            # Simple fallback detection
            framework_patterns = {
                'react': ['import React', 'React.Component', 'useState', 'useEffect'],
                'angular': ['@Component', '@NgModule', '@Injectable'],
                'vue': ['createApp', '<template>', 'defineComponent'],
                'spring': ['@SpringBootApplication', '@Controller', '@Service', '@Repository'],
                'django': ['from django'],
                'flask': ['Flask(__name__)', '@app.route']
            }
            
            for framework, patterns in framework_patterns.items():
                for pattern in patterns:
                    if pattern in code:
                        return framework
            return None
    
    def index_file(
        self,
        file_path: str,
        repo_name: str,
        git_commit: Optional[str] = None,
        structure_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Index a source code file
        
        Args:
            file_path: Path to the file to index
            repo_name: Repository identifier
            git_commit: Optional Git commit hash
            structure_file: Optional path to pre-parsed structure file
            
        Returns:
            Summary of indexing result
        """
        start_time = time.time()
        result = {
            "success": False,
            "file_path": file_path,
            "repo_name": repo_name,
            "chunks_indexed": 0,
            "elements_indexed": 0,
            "duration_seconds": 0
        }
        
        if not os.path.exists(file_path):
            result["error"] = f"File not found: {file_path}"
            return result
        
        # Read file content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
        except Exception as e:
            result["error"] = f"Error reading file: {str(e)}"
            return result
        
        # Parse file structure if provided
        external_structure = None
        if structure_file and os.path.exists(structure_file):
            try:
                with open(structure_file, 'r') as f:
                    external_structure = json.load(f)
            except Exception as e:
                result["error"] = f"Error loading structure file: {str(e)}"
                return result
        
        # Get language and detect framework
        language = self._get_file_language(file_path)
        framework = self._detect_framework(file_content, file_path)
        
        # Get parse_file function
        try:
            parse_file_fn = self._get_chunker()
        except Exception as e:
            result["error"] = f"Error loading chunker: {str(e)}"
            return result
        
        # Parse the file using parse_file
        try:
            parsed_result = parse_file_fn(file_path, verbose=False)
            chunk_infos = parsed_result["chunks"]
            summary = parsed_result["summary"]
            file_structure = parsed_result["structure"]
            formatted_structure = parsed_result.get("formatted_structure")
            metadata = parsed_result.get("metadata", {})
        except Exception as e:
            result["error"] = f"Error parsing file: {str(e)}\n{traceback.format_exc()}"
            return result
        
        # Get parser fragments from parse result
        parser_fragments = []
        
        # Try to extract parser_fragments from chunks
        for chunk in chunk_infos:
            if hasattr(chunk, 'parser_fragments') and chunk.parser_fragments:
                # Convert parser fragments to a serializable format if needed
                if hasattr(chunk, 'to_json'):
                    chunk_json = chunk.to_json()
                    if 'parser_fragments' in chunk_json:
                        parser_fragments.extend(chunk_json['parser_fragments'])
                else:
                    parser_fragments.extend(chunk.parser_fragments)
        
        # Use external structure if provided, otherwise use the parsed structure
        structure_to_store = external_structure if external_structure else formatted_structure
        
        # Create a simple structure object if not provided
        if not structure_to_store:
            structure_to_store = {
                "filename": os.path.basename(file_path),
                "filepath": file_path,
                "language": language,
                "total_lines": len(file_content.splitlines()),
                "total_chunks": len(chunk_infos)
            }
            
            # Add structure data if available
            if file_structure:
                structure_to_store["structure"] = file_structure
        
        # Calculate element count
        element_count = len(parser_fragments) if parser_fragments else 0
        
        # Store file in database
        try:
            file_id = self.db.store_file(
                repo_name=repo_name,
                file_path=file_path,
                content=file_content,
                language=language,
                framework=framework,
                structure_json=structure_to_store,
                element_count=element_count,
                git_commit=git_commit,
                summary_json=summary
            )
        except Exception as e:
            result["error"] = f"Error storing file: {str(e)}\n{traceback.format_exc()}"
            return result
        
        # Process and store chunks
        stored_chunks = 0
        for chunk in chunk_infos:
            try:
                # Get chunk attributes
                chunk_text = chunk.text if hasattr(chunk, 'text') else ""
                chunk_type = chunk.chunk_type if hasattr(chunk, 'chunk_type') else "code"
                start_line = chunk.span.start if hasattr(chunk, 'span') else 0
                end_line = chunk.span.end if hasattr(chunk, 'span') else 0
                
                # Skip empty chunks
                if not chunk_text.strip():
                    continue
                
                # Get metadata and special patterns
                chunk_metadata = {}
                special_patterns = {}
                
                if hasattr(chunk, 'metadata'):
                    chunk_metadata = chunk.metadata
                    # Extract special patterns if available
                    if 'special_matches' in chunk_metadata:
                        special_patterns = chunk_metadata.pop('special_matches')
                
                # Extract more values from metadata
                non_whitespace_len = chunk_metadata.get('non_whitespace_len', 0)
                quality_score = chunk_metadata.get('quality', 0.0)
                chunk_framework = chunk_metadata.get('framework', None)
                
                # Store code block
                block_id = self.db.store_code_block(
                    file_id=file_id,
                    chunk_type=chunk_type,
                    start_line=start_line,
                    end_line=end_line,
                    content=chunk_text,
                    non_whitespace_len=non_whitespace_len,
                    quality_score=quality_score,
                    framework=chunk_framework,
                    metadata=chunk_metadata,
                    special_patterns=special_patterns
                )
                
                # Store special patterns if available
                for pattern_type, matches in special_patterns.items():
                    self.db.store_special_pattern(
                        code_block_id=block_id,
                        pattern_type=pattern_type
                    )
                
                # Generate and store embedding
                embedding_metadata = {
                    'language': language,
                    'framework': chunk_framework or framework,
                    'chunk_type': chunk_type
                }
                
                embedding = self.embedder.generate_embedding(
                    code=chunk_text,
                    metadata=embedding_metadata
                )
                
                self.db.store_embedding(
                    code_block_id=block_id,
                    embedding_vector=embedding,
                    embedding_model=self.embedder.model_name
                )
                
                stored_chunks += 1
                
            except Exception as e:
                print(f"Error processing chunk: {str(e)}")
                # Continue with next chunk
        
        # Process and store semantic elements
        stored_elements = 0
        parent_elements = {}  # Track parent-child relationships
        
        # Store all elements first
        for fragment in parser_fragments:
            try:
                # Extract element properties
                if isinstance(fragment, dict):
                    # If fragment is already a dictionary
                    element_type = fragment.get('type_info', fragment.get('type', 'unknown'))
                    name = fragment.get('name', '')
                    start_line = fragment.get('line', 0)
                    end_line = fragment.get('end_line', start_line)
                    metadata = {k: v for k, v in fragment.items() 
                               if k not in ['type_info', 'type', 'name', 'line', 'end_line']}
                else:
                    # If fragment is an object
                    element_type = getattr(fragment, 'type_info', getattr(fragment, 'type', 'unknown'))
                    name = getattr(fragment, 'name', '')
                    start_line = getattr(fragment, 'line', 0)
                    end_line = getattr(fragment, 'end_line', start_line)
                    # Extract other attributes as metadata
                    metadata = {}
                    for attr in dir(fragment):
                        if not attr.startswith('_') and attr not in ['type_info', 'type', 'name', 'line', 'end_line']:
                            try:
                                value = getattr(fragment, attr)
                                if not callable(value):
                                    metadata[attr] = value
                            except:
                                pass
                
                element_id = self.db.store_semantic_element(
                    file_id=file_id,
                    element_type=element_type,
                    name=name,
                    start_line=start_line,
                    end_line=end_line,
                    metadata=metadata
                )
                
                # Store the mapping of name to ID for later parent assignment
                if name:
                    parent_elements[name] = element_id
                
                stored_elements += 1
                
            except Exception as e:
                print(f"Error storing semantic element: {str(e)}")
        
        # Update parent-child relationships
        for fragment in parser_fragments:
            try:
                # Extract name based on type
                if isinstance(fragment, dict):
                    name = fragment.get('name', '')
                else:
                    name = getattr(fragment, 'name', '')
                
                if not name:
                    continue
                
                # Skip if we don't have this element
                if name not in parent_elements:
                    continue
                
                element_id = parent_elements[name]
                
                # Check if this is a class method
                if name.count('.') > 0:
                    parent_name, method_name = name.rsplit('.', 1)
                    if parent_name in parent_elements:
                        # Update the parent reference
                        self.db.conn.execute(
                            "UPDATE semantic_elements SET parent_element_id = ? WHERE id = ?",
                            (parent_elements[parent_name], element_id)
                        )
            except Exception as e:
                print(f"Error updating semantic element: {str(e)}")
        
        # Update result
        result["success"] = True
        result["chunks_indexed"] = stored_chunks
        result["elements_indexed"] = stored_elements
        result["duration_seconds"] = time.time() - start_time
        
        return result
    
    def index_directory(
        self,
        dir_path: str,
        repo_name: str,
        file_extensions: Optional[List[str]] = None,
        git_commit: Optional[str] = None,
        recursive: bool = True
    ) -> Dict[str, Any]:
        """
        Index all supported files in a directory
        
        Args:
            dir_path: Path to the directory to index
            repo_name: Repository identifier
            file_extensions: List of file extensions to index (e.g. ['.py', '.java'])
            git_commit: Optional Git commit hash
            recursive: Whether to recursively process subdirectories
            
        Returns:
            Summary of indexing result
        """
        if not file_extensions:
            file_extensions = ['.py', '.java', '.js', '.jsx', '.ts', '.tsx', '.go', '.cpp', '.c']
            
        result = {
            "success": True,
            "dir_path": dir_path,
            "repo_name": repo_name,
            "files_indexed": 0,
            "files_failed": 0,
            "total_chunks": 0,
            "total_elements": 0,
            "duration_seconds": 0,
            "failed_files": []
        }
        
        start_time = time.time()
        
        if not os.path.exists(dir_path) or not os.path.isdir(dir_path):
            result["success"] = False
            result["error"] = f"Directory not found: {dir_path}"
            return result
        
        # Build list of files to process
        files_to_process = []
        
        if recursive:
            for root, _, files in os.walk(dir_path):
                for file in files:
                    if any(file.endswith(ext) for ext in file_extensions):
                        files_to_process.append(os.path.join(root, file))
        else:
            for file in os.listdir(dir_path):
                file_path = os.path.join(dir_path, file)
                if os.path.isfile(file_path) and any(file.endswith(ext) for ext in file_extensions):
                    files_to_process.append(file_path)
        
        # Process each file
        for file_path in files_to_process:
            try:
                # Get relative path for storage
                rel_path = os.path.relpath(file_path, dir_path)
                
                file_result = self.index_file(
                    file_path=file_path,
                    repo_name=repo_name,
                    git_commit=git_commit
                )
                
                if file_result["success"]:
                    result["files_indexed"] += 1
                    result["total_chunks"] += file_result["chunks_indexed"]
                    result["total_elements"] += file_result["elements_indexed"]
                else:
                    result["files_failed"] += 1
                    result["failed_files"].append({
                        "file_path": rel_path,
                        "error": file_result.get("error", "Unknown error")
                    })
            except Exception as e:
                result["files_failed"] += 1
                result["failed_files"].append({
                    "file_path": os.path.relpath(file_path, dir_path),
                    "error": str(e)
                })
        
        result["duration_seconds"] = time.time() - start_time
        
        return result
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        repo_name: Optional[str] = None,
        language: Optional[str] = None,
        framework: Optional[str] = None,
        element_type: Optional[str] = None,
        search_type: str = "vector",
        filter_empty: bool = True,
        min_quality: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Search for code based on query
        
        Args:
            query: Search query text
            top_k: Number of results to return
            repo_name: Optional repository filter
            language: Optional language filter
            framework: Optional framework filter
            element_type: Optional element type filter (function, class, etc.)
            search_type: "vector" (default), "keyword", or "hybrid"
            filter_empty: Whether to filter out empty results
            min_quality: Minimum quality score for results
            
        Returns:
            List of matching code blocks with metadata
        """
        filters = {}
        if repo_name:
            filters["repo_name"] = repo_name
        if language:
            filters["language"] = language
        if framework:
            filters["framework"] = framework
        if element_type:
            filters["element_type"] = element_type
        if min_quality > 0:
            filters["min_quality"] = min_quality
        
        results = []
        
        if search_type == "keyword":
            # Perform keyword search only
            results = self.db.keyword_search(query, top_k, filters)
        
        elif search_type == "hybrid":
            # Perform both searches and combine results
            keyword_results = self.db.keyword_search(query, top_k, filters)
            
            # Get vector embedding
            embedding = self.embedder.generate_embedding(query)
            vector_results = self.db.search_by_vector(embedding, top_k, filters)
            
            # Combine and deduplicate results
            seen_ids = set()
            hybrid_results = []
            
            # First add the keyword results
            for result in keyword_results:
                hybrid_results.append(result)
                seen_ids.add(result["code_block_id"])
            
            # Then add vector results not already included
            for result in vector_results:
                if result["code_block_id"] not in seen_ids:
                    hybrid_results.append(result)
                    seen_ids.add(result["code_block_id"])
                    
                    # Stop if we've reached top_k
                    if len(hybrid_results) >= top_k:
                        break
            
            results = hybrid_results[:top_k]
        
        else:  # Default to vector search
            # Generate embedding for query
            embedding = self.embedder.generate_embedding(query)
            results = self.db.search_by_vector(embedding, top_k, filters)
        
        # Filter out empty results if requested
        if filter_empty and results:
            results = [r for r in results if r.get('content', '').strip()]
        
        # Enhance results with file info
        for result in results:
            # Get file path information
            file_path = result.get('file_path', '')
            if file_path:
                result['filename'] = os.path.basename(file_path)
                result['relative_path'] = file_path
        
        return results
    
    def delete_repository(self, repo_name: str) -> bool:
        """Delete all files in a repository"""
        conn = self.db.connect()
        
        try:
            # Get all files for this repo
            file_paths = [
                row[0] for row in conn.execute(
                    "SELECT file_path FROM code_files WHERE repo_name = ?",
                    (repo_name,)
                ).fetchall()
            ]
            
            success = True
            for file_path in file_paths:
                result = self.db.delete_file(repo_name, file_path)
                if not result:
                    success = False
            
            return success
        except Exception as e:
            print(f"Error deleting repository: {str(e)}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the database"""
        return self.db.get_stats()
    
    def close(self):
        """Close database connection"""
        self.db.close() 