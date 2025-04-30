import sqlite3
import sqlite_vec
import os
import struct
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union

class CodeRAGDatabase:
    """Database handler for code RAG using SQLite and SQLite-Vec"""
    
    def __init__(self, db_path: str, dim: int = 1024, distance_function: str = "cosine"):
        """
        Initialize the database connection and setup
        
        Args:
            db_path: Path to the SQLite database file
            dim: Embedding dimension (default 384 for bge-m3)
            distance_function: Vector distance function (cosine, l2, dot)
        """
        self.db_path = db_path
        self.dim = dim
        self.distance_function = distance_function
        self.conn = None
        
    def serialize_vector(self, vector: List[float]) -> bytes:
        """Serialize a vector into bytes for storage"""
        return struct.pack(f"{len(vector)}f", *vector)
    
    def connect(self) -> sqlite3.Connection:
        """Establish database connection with vector extensions"""
        if self.conn is None:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
            
            # Connect to database
            self.conn = sqlite3.connect(self.db_path)
            self.conn.enable_load_extension(True)
            sqlite_vec.load(self.conn)
            self.conn.enable_load_extension(False)
            
            # Enable foreign keys
            self.conn.execute("PRAGMA foreign_keys = ON")
        
        return self.conn
    
    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def initialize_database(self):
        """Create database schema with tables and indexes"""
        conn = self.connect()
        
        # Create tables using transactions
        with conn:
            # Core file table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS code_files (
                id INTEGER PRIMARY KEY,
                repo_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                language TEXT NOT NULL,
                framework TEXT,
                structure_json JSON,
                element_count INTEGER,
                latest_commit TEXT,
                summary_json JSON,
                indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(repo_name, file_path, content_hash)
            )
            """)
            
            # Code blocks table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS code_blocks (
                id INTEGER PRIMARY KEY,
                file_id INTEGER NOT NULL,
                chunk_type TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                content TEXT NOT NULL,
                non_whitespace_len INTEGER,
                quality_score FLOAT,
                framework TEXT,
                special_patterns_json JSON,
                metadata_json JSON,
                FOREIGN KEY (file_id) REFERENCES code_files(id) ON DELETE CASCADE
            )
            """)
            
            # Semantic elements from parser_fragments
            conn.execute("""
            CREATE TABLE IF NOT EXISTS semantic_elements (
                id INTEGER PRIMARY KEY,
                file_id INTEGER NOT NULL,
                element_type TEXT NOT NULL,
                name TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                parent_element_id INTEGER,
                associated_block_ids TEXT,
                metadata_json JSON,
                FOREIGN KEY (file_id) REFERENCES code_files(id) ON DELETE CASCADE,
                FOREIGN KEY (parent_element_id) REFERENCES semantic_elements(id) ON DELETE CASCADE
            )
            """)
            
            # Special patterns detected in chunks
            conn.execute("""
            CREATE TABLE IF NOT EXISTS special_patterns (
                id INTEGER PRIMARY KEY,
                code_block_id INTEGER NOT NULL,
                pattern_type TEXT NOT NULL,
                pattern_line INTEGER,
                FOREIGN KEY (code_block_id) REFERENCES code_blocks(id) ON DELETE CASCADE
            )
            """)
            
            # File versions for tracking
            conn.execute("""
            CREATE TABLE IF NOT EXISTS file_versions (
                id INTEGER PRIMARY KEY,
                file_id INTEGER NOT NULL,
                git_commit TEXT NOT NULL,
                commit_timestamp TIMESTAMP,
                is_deleted BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (file_id) REFERENCES code_files(id) ON DELETE CASCADE
            )
            """)
            
            # Vector table using sqlite_vec
            conn.execute(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS embeddings 
            USING vec0(
                code_block_id INTEGER,
                embedding float[{self.dim}],
                embedding_model TEXT
            )
            """)
            
            # Create necessary indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_code_files_repo_path ON code_files(repo_name, file_path)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_code_files_language ON code_files(language)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_code_files_framework ON code_files(framework)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_code_blocks_file_id ON code_blocks(file_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_code_blocks_lines ON code_blocks(start_line, end_line)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_semantic_elements_file ON semantic_elements(file_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_semantic_elements_type ON semantic_elements(element_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_semantic_elements_parent ON semantic_elements(parent_element_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_special_patterns_block ON special_patterns(code_block_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_file_versions_commit ON file_versions(git_commit)")
    
    def calculate_file_hash(self, content: str) -> str:
        """Calculate SHA256 hash of file content"""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
    
    def store_file(self, repo_name: str, file_path: str, content: str, 
                  language: str, framework: Optional[str], structure_json: Dict, 
                  element_count: int, git_commit: Optional[str] = None,
                  summary_json: Optional[Dict] = None) -> int:
        """
        Store file metadata in the database
        
        Returns: file_id
        """
        conn = self.connect()
        content_hash = self.calculate_file_hash(content)
        
        with conn:
            # Check if file already exists with same hash
            existing = conn.execute(
                "SELECT id FROM code_files WHERE repo_name = ? AND file_path = ? AND content_hash = ?",
                (repo_name, file_path, content_hash)
            ).fetchone()
            
            if existing:
                return existing[0]
            
            # Insert new file
            cursor = conn.execute(
                """
                INSERT INTO code_files 
                (repo_name, file_path, content_hash, language, framework, structure_json, element_count, latest_commit, summary_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    repo_name, 
                    file_path, 
                    content_hash, 
                    language, 
                    framework, 
                    json.dumps(structure_json) if structure_json else None,
                    element_count,
                    git_commit,
                    json.dumps(summary_json) if summary_json else None
                )
            )
            
            file_id = cursor.lastrowid
            
            # If git commit is provided, add file version
            if git_commit:
                conn.execute(
                    """
                    INSERT INTO file_versions (file_id, git_commit)
                    VALUES (?, ?)
                    """,
                    (file_id, git_commit)
                )
                
            return file_id
    
    def store_code_block(self, file_id: int, chunk_type: str, start_line: int, end_line: int,
                       content: str, non_whitespace_len: int, quality_score: float,
                       framework: Optional[str], metadata: Optional[Dict] = None,
                       special_patterns: Optional[Dict] = None) -> int:
        """
        Store a code block in the database
        
        Returns: code_block_id
        """
        conn = self.connect()
        
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO code_blocks
                (file_id, chunk_type, start_line, end_line, content, non_whitespace_len, quality_score, framework, metadata_json, special_patterns_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    file_id,
                    chunk_type,
                    start_line,
                    end_line,
                    content,
                    non_whitespace_len,
                    quality_score,
                    framework,
                    json.dumps(metadata) if metadata else None,
                    json.dumps(special_patterns) if special_patterns else None
                )
            )
            
            return cursor.lastrowid
    
    def store_semantic_element(self, file_id: int, element_type: str, name: str,
                             start_line: int, end_line: int, 
                             parent_element_id: Optional[int] = None,
                             associated_block_ids: Optional[List[int]] = None,
                             metadata: Optional[Dict] = None) -> int:
        """
        Store a semantic element in the database
        
        Returns: element_id
        """
        conn = self.connect()
        
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO semantic_elements
                (file_id, element_type, name, start_line, end_line, parent_element_id, associated_block_ids, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    file_id,
                    element_type,
                    name,
                    start_line,
                    end_line,
                    parent_element_id,
                    json.dumps(associated_block_ids) if associated_block_ids else None,
                    json.dumps(metadata) if metadata else None
                )
            )
            
            return cursor.lastrowid
    
    def store_special_pattern(self, code_block_id: int, pattern_type: str, pattern_line: Optional[int] = None) -> int:
        """
        Store a special pattern in the database
        
        Returns: pattern_id
        """
        conn = self.connect()
        
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO special_patterns
                (code_block_id, pattern_type, pattern_line)
                VALUES (?, ?, ?)
                """,
                (
                    code_block_id,
                    pattern_type,
                    pattern_line
                )
            )
            
            return cursor.lastrowid
    
    def store_embedding(self, code_block_id: int, embedding_vector: List[float], 
                      embedding_model: str) -> bool:
        """
        Store a vector embedding for a code block
        
        Returns: success (boolean)
        """
        conn = self.connect()
        
        # Ensure vector has correct dimensions
        if len(embedding_vector) != self.dim:
            raise ValueError(f"Embedding dimension mismatch: expected {self.dim}, got {len(embedding_vector)}")
        
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO embeddings
                    (code_block_id, embedding, embedding_model)
                    VALUES (?, ?, ?)
                    """,
                    (
                        code_block_id,
                        self.serialize_vector(embedding_vector),
                        embedding_model
                    )
                )
            return True
        except Exception as e:
            print(f"Error storing embedding: {e}")
            return False
    
    def search_by_vector(self, query_embedding: List[float], top_k: int = 5, 
                       filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Search for similar code blocks based on embedding similarity
        
        Args:
            query_embedding: Vector embedding of the query
            top_k: Number of results to return
            filters: Optional filters to apply (repo_name, language, etc.)
        
        Returns:
            List of matching code blocks with metadata
        """
        conn = self.connect()
        
        # Convert filters into SQL conditions
        filter_conditions = []
        filter_params = []
        
        if filters:
            if "repo_name" in filters:
                filter_conditions.append("f.repo_name = ?")
                filter_params.append(filters["repo_name"])
                
            if "language" in filters:
                filter_conditions.append("f.language = ?")
                filter_params.append(filters["language"])
                
            if "framework" in filters:
                filter_conditions.append("(f.framework = ? OR b.framework = ?)")
                filter_params.extend([filters["framework"], filters["framework"]])
                
            if "element_type" in filters:
                filter_conditions.append("EXISTS (SELECT 1 FROM semantic_elements se WHERE se.file_id = f.id AND se.element_type = ? AND (b.start_line <= se.end_line AND b.end_line >= se.start_line))")
                filter_params.append(filters["element_type"])
        
        # Build the WHERE clause for filters
        where_clause = " AND ".join(filter_conditions)
        if where_clause:
            where_clause = "WHERE " + where_clause
            
        # Prepare the query vector
        if len(query_embedding) != self.dim:
            raise ValueError(f"Query embedding dimension mismatch: expected {self.dim}, got {len(query_embedding)}")
        
        # Build the full query
        query_sql = f"""
        SELECT 
            b.id, b.content, b.start_line, b.end_line, b.chunk_type, b.quality_score,
            f.repo_name, f.file_path, f.language, b.framework, 
            vec_distance_cosine(e.embedding, ?) as distance
        FROM embeddings e
        JOIN code_blocks b ON e.code_block_id = b.id
        JOIN code_files f ON b.file_id = f.id
        {where_clause}
        ORDER BY distance
        LIMIT ?
        """
        
        # Prepare query parameters
        params = [self.serialize_vector(query_embedding)] + filter_params + [top_k]
        
        results = []
        for row in conn.execute(query_sql, params).fetchall():
            result = {
                'code_block_id': row[0],
                'content': row[1],
                'start_line': row[2],
                'end_line': row[3],
                'chunk_type': row[4],
                'quality_score': row[5],
                'repo_name': row[6],
                'file_path': row[7],
                'language': row[8],
                'framework': row[9],
                'distance': row[10]
            }
            
            # Extract metadata if available
            block_metadata = conn.execute(
                "SELECT metadata_json, special_patterns_json FROM code_blocks WHERE id = ?", 
                (row[0],)
            ).fetchone()
            
            if block_metadata:
                if block_metadata[0]:
                    try:
                        result['metadata'] = json.loads(block_metadata[0])
                    except:
                        pass
                    
                if block_metadata[1]:
                    try:
                        result['special_patterns'] = json.loads(block_metadata[1])
                    except:
                        pass
            
            # Add semantic elements related to this code block
            related_elements = self.get_semantic_elements_for_block(row[0])
            if related_elements:
                result['semantic_elements'] = related_elements
                
            results.append(result)
        
        return results
    
    def get_semantic_elements_for_block(self, code_block_id: int) -> List[Dict[str, Any]]:
        """Get semantic elements that overlap with a code block"""
        conn = self.connect()
        
        # First get the block's file_id and line range
        block_info = conn.execute(
            "SELECT file_id, start_line, end_line FROM code_blocks WHERE id = ?",
            (code_block_id,)
        ).fetchone()
        
        if not block_info:
            return []
            
        file_id, start_line, end_line = block_info
        
        # Get elements that overlap with the block
        rows = conn.execute(
            """
            SELECT id, element_type, name, start_line, end_line, parent_element_id, metadata_json
            FROM semantic_elements
            WHERE file_id = ? AND (
                (start_line >= ? AND start_line <= ?) OR
                (end_line >= ? AND end_line <= ?) OR
                (start_line <= ? AND end_line >= ?)
            )
            """,
            (file_id, start_line, end_line, start_line, end_line, start_line, end_line)
        ).fetchall()
        
        results = []
        for row in rows:
            element = {
                'id': row[0],
                'element_type': row[1],
                'name': row[2],
                'start_line': row[3],
                'end_line': row[4],
                'parent_id': row[5],
            }
            
            # Add metadata if available
            if row[6]:
                try:
                    element['metadata'] = json.loads(row[6])
                except:
                    pass
                
            results.append(element)
            
        return results
    
    def keyword_search(self, query: str, top_k: int = 5, 
                     filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Search for code blocks based on keyword search
        
        Args:
            query: Search query text
            top_k: Number of results to return
            filters: Optional filters to apply (repo_name, language, etc.)
        
        Returns:
            List of matching code blocks with metadata
        """
        conn = self.connect()
        
        # Convert filters into SQL conditions
        filter_conditions = []
        filter_params = []
        
        if filters:
            if "repo_name" in filters:
                filter_conditions.append("f.repo_name = ?")
                filter_params.append(filters["repo_name"])
                
            if "language" in filters:
                filter_conditions.append("f.language = ?")
                filter_params.append(filters["language"])
                
            if "framework" in filters:
                filter_conditions.append("(f.framework = ? OR b.framework = ?)")
                filter_params.extend([filters["framework"], filters["framework"]])
                
            if "element_type" in filters:
                filter_conditions.append("EXISTS (SELECT 1 FROM semantic_elements se WHERE se.file_id = f.id AND se.element_type = ? AND (b.start_line <= se.end_line AND b.end_line >= se.start_line))")
                filter_params.append(filters["element_type"])
        
        # Build the WHERE clause for filters and keyword search
        search_condition = "b.content LIKE ?"
        search_param = f"%{query}%"
        
        # Combine filter and search conditions
        where_conditions = [search_condition] + filter_conditions
        where_clause = " AND ".join(where_conditions)
        
        # Build the full query
        query_sql = f"""
        SELECT 
            b.id, b.content, b.start_line, b.end_line, b.chunk_type, b.quality_score,
            f.repo_name, f.file_path, f.language, b.framework
        FROM code_blocks b
        JOIN code_files f ON b.file_id = f.id
        WHERE {where_clause}
        ORDER BY b.quality_score DESC
        LIMIT ?
        """
        
        # Prepare query parameters
        params = [search_param] + filter_params + [top_k]
        
        results = []
        for row in conn.execute(query_sql, params).fetchall():
            result = {
                'code_block_id': row[0],
                'content': row[1],
                'start_line': row[2],
                'end_line': row[3],
                'chunk_type': row[4],
                'quality_score': row[5],
                'repo_name': row[6],
                'file_path': row[7],
                'language': row[8],
                'framework': row[9]
            }
            
            # Extract metadata if available
            block_metadata = conn.execute(
                "SELECT metadata_json, special_patterns_json FROM code_blocks WHERE id = ?", 
                (row[0],)
            ).fetchone()
            
            if block_metadata:
                if block_metadata[0]:
                    try:
                        result['metadata'] = json.loads(block_metadata[0])
                    except:
                        pass
                    
                if block_metadata[1]:
                    try:
                        result['special_patterns'] = json.loads(block_metadata[1])
                    except:
                        pass
            
            # Add semantic elements related to this code block
            related_elements = self.get_semantic_elements_for_block(row[0])
            if related_elements:
                result['semantic_elements'] = related_elements
                
            results.append(result)
        
        return results
    
    def get_file_info(self, file_id: int) -> Dict[str, Any]:
        """Get complete file information including structure"""
        conn = self.connect()
        
        file_info = conn.execute(
            """
            SELECT 
                id, repo_name, file_path, language, framework, 
                structure_json, element_count, latest_commit, indexed_at, summary_json
            FROM code_files
            WHERE id = ?
            """,
            (file_id,)
        ).fetchone()
        
        if not file_info:
            return {}
        
        result = {
            'id': file_info[0],
            'repo_name': file_info[1],
            'file_path': file_info[2],
            'language': file_info[3],
            'framework': file_info[4],
            'element_count': file_info[6],
            'latest_commit': file_info[7],
            'indexed_at': file_info[8]
        }
        
        # Parse JSON fields
        if file_info[5]:  # structure_json
            try:
                result['structure'] = json.loads(file_info[5])
            except:
                result['structure'] = None
                
        if file_info[9]:  # summary_json
            try:
                result['summary'] = json.loads(file_info[9])
            except:
                result['summary'] = None
                
        return result
    
    def delete_file(self, repo_name: str, file_path: str) -> bool:
        """Delete a file and all associated data"""
        conn = self.connect()
        
        try:
            with conn:
                # Find file ID
                file_id_row = conn.execute(
                    "SELECT id FROM code_files WHERE repo_name = ? AND file_path = ?",
                    (repo_name, file_path)
                ).fetchone()
                
                if not file_id_row:
                    return True  # File not found, consider it deleted
                
                file_id = file_id_row[0]
                
                # Get all code block IDs to clean up embeddings
                block_ids = [
                    row[0] for row in conn.execute(
                        "SELECT id FROM code_blocks WHERE file_id = ?",
                        (file_id,)
                    ).fetchall()
                ]
                
                # Delete embeddings first (SQLite-Vec doesn't cascade)
                for block_id in block_ids:
                    conn.execute(
                        "DELETE FROM embeddings WHERE code_block_id = ?",
                        (block_id,)
                    )
                
                # Delete file (cascades to code_blocks, semantic_elements, and file_versions)
                conn.execute(
                    "DELETE FROM code_files WHERE id = ?",
                    (file_id,)
                )
                
            return True
        except Exception as e:
            print(f"Error deleting file: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        conn = self.connect()
        
        stats = {
            'total_files': 0,
            'total_blocks': 0,
            'total_elements': 0,
            'total_embeddings': 0,
            'languages': {},
            'frameworks': {},
            'repositories': {}
        }
        
        # Get counts
        stats['total_files'] = conn.execute("SELECT COUNT(*) FROM code_files").fetchone()[0]
        stats['total_blocks'] = conn.execute("SELECT COUNT(*) FROM code_blocks").fetchone()[0]
        stats['total_elements'] = conn.execute("SELECT COUNT(*) FROM semantic_elements").fetchone()[0]
        stats['total_embeddings'] = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
        
        # Get language distribution
        for row in conn.execute("SELECT language, COUNT(*) FROM code_files GROUP BY language"):
            stats['languages'][row[0]] = row[1]
        
        # Get framework distribution
        for row in conn.execute("SELECT framework, COUNT(*) FROM code_files WHERE framework IS NOT NULL GROUP BY framework"):
            stats['frameworks'][row[0]] = row[1]
        
        # Get repo distribution
        for row in conn.execute("SELECT repo_name, COUNT(*) FROM code_files GROUP BY repo_name"):
            stats['repositories'][row[0]] = row[1]
            
        return stats
    
    def check_and_update_schema(self):
        """Check if existing tables match the expected schema and add missing columns if needed"""
        conn = self.connect()
        
        try:
            # First initialize the database to ensure tables exist
            self.initialize_database()
            
            # Check code_files table for missing columns
            existing_cols = [row[1] for row in conn.execute("PRAGMA table_info(code_files)").fetchall()]
            if "summary_json" not in existing_cols:
                print("Adding missing column 'summary_json' to code_files table")
                conn.execute("ALTER TABLE code_files ADD COLUMN summary_json JSON")
            
            # Check code_blocks table for missing columns
            existing_cols = [row[1] for row in conn.execute("PRAGMA table_info(code_blocks)").fetchall()]
            if "special_patterns_json" not in existing_cols:
                print("Adding missing column 'special_patterns_json' to code_blocks table")
                conn.execute("ALTER TABLE code_blocks ADD COLUMN special_patterns_json JSON")
            if "metadata_json" not in existing_cols:
                print("Adding missing column 'metadata_json' to code_blocks table")
                conn.execute("ALTER TABLE code_blocks ADD COLUMN metadata_json JSON")
            
            # Check semantic_elements table for missing columns
            existing_cols = [row[1] for row in conn.execute("PRAGMA table_info(semantic_elements)").fetchall()]
            if "metadata_json" not in existing_cols:
                print("Adding missing column 'metadata_json' to semantic_elements table")
                conn.execute("ALTER TABLE semantic_elements ADD COLUMN metadata_json JSON")
            
            return True
        except Exception as e:
            print(f"Error updating schema: {e}")
            return False 