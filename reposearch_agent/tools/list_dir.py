import os
import json
import fnmatch
from typing import Dict, Any, List, Optional, Set

from qwen_agent.tools.base import BaseTool, register_tool
from reposearch_agent.config import DEFAULT_REPO_DIR


@register_tool('list_dir')
class ListDirTool(BaseTool):
    description = 'List contents of a directory to explore the code repository structure.'
    parameters = [
        {
            'name': 'path',
            'type': 'string',
            'description': 'Relative path within the repository',
            'required': False,
        },
        {
            'name': 'recursive',
            'type': 'boolean',
            'description': 'Whether to recursively list subdirectories',
            'required': False,
        },
        {
            'name': 'max_entries',
            'type': 'integer',
            'description': 'Maximum number of entries to show',
            'required': False,
        },
        {
            'name': 'max_depth',
            'type': 'integer',
            'description': 'Maximum depth to traverse in recursive mode',
            'required': False,
        }
    ]
    
    def __init__(self, tool_cfg=None):
        """Initialize the directory listing tool"""
        self._gitignore_patterns = None
        self._repo_dir = None
    
    def _load_gitignore_patterns(self, repo_dir: str, current_path: str = "") -> Set[str]:
        """
        Load patterns from .gitignore file in current and parent directories
        
        Args:
            repo_dir: Base repository directory
            current_path: Current relative path within repo
            
        Returns:
            Set of gitignore patterns
        """
        patterns = set()
        
        # Path components from repo root to current dir
        path_components = current_path.split(os.sep) if current_path else []
        
        # Check all parent directories for .gitignore files
        for i in range(len(path_components) + 1):
            # Construct path to this level's potential .gitignore
            if i == 0:
                # Root level .gitignore
                rel_path = ""
            else:
                # Subdir .gitignore
                rel_path = os.path.join(*path_components[:i])
                
            gitignore_path = os.path.join(repo_dir, rel_path, '.gitignore')
            
            if os.path.exists(gitignore_path) and os.path.isfile(gitignore_path):
                try:
                    with open(gitignore_path, 'r') as f:
                        for line in f:
                            line = line.strip()
                            # Skip empty lines and comments
                            if line and not line.startswith('#'):
                                # Handle patterns with slashes properly
                                if line.endswith('/'):
                                    line = line[:-1]  # Remove trailing slash
                                patterns.add(line)
                except Exception:
                    pass  # Silently fail if we can't read the gitignore file
                
        return patterns
    
    def _should_exclude(self, entry_name: str, entry_path: str, repo_dir: str, rel_dir_path: str, gitignore_patterns: Set[str]) -> bool:
        """
        Check if an entry should be excluded based on filters
        
        Args:
            entry_name: Name of the file/directory
            entry_path: Full path to the entry
            repo_dir: Base repository directory
            rel_dir_path: Relative directory path from repo root
            gitignore_patterns: Set of gitignore patterns
            
        Returns:
            True if entry should be excluded, False otherwise
        """
        # Filter hidden files/directories (starting with .)
        if entry_name.startswith('.'):
            return True
            
        # Filter entries mentioned in gitignore
        if gitignore_patterns:
            # Get relative path from repo root
            if rel_dir_path:
                rel_path = os.path.join(rel_dir_path, entry_name)
            else:
                rel_path = entry_name
            
            for pattern in gitignore_patterns:
                # Handle directory-specific patterns
                if '/' in pattern:
                    if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(rel_path, f"{pattern}/*"):
                        return True
                # Handle wildcard patterns
                elif '*' in pattern:
                    if fnmatch.fnmatch(entry_name, pattern):
                        return True
                # Handle simple directory/file names
                elif entry_name == pattern or rel_path == pattern:
                    return True
                    
        return False
    
    def call(self, params: str, **kwargs) -> str:
        # Parse parameters
        try:
            params = json.loads(params)
            path = params.get('path', "")
            repo_dir = params.get('repo_dir', DEFAULT_REPO_DIR)
            recursive = params.get('recursive', True)  # Default to recursive listing
            max_entries = params.get('max_entries', 100)  # Default to 100 max entries
            max_depth = params.get('max_depth', 3)  # Default to depth 3
            
            # Load gitignore patterns
            self._repo_dir = repo_dir
            gitignore_patterns = self._load_gitignore_patterns(repo_dir, path)
            
            if recursive:
                # Call the recursive list implementation
                entries, total_count = self._list_contents_recursive(
                    path=path,
                    repo_dir=repo_dir,
                    max_entries=max_entries,
                    max_depth=max_depth,
                    gitignore_patterns=gitignore_patterns
                )
                
                # Check for errors or empty directories
                if not entries:
                    return f"No entries found in directory '{path}'"
                
                # Format hierarchically
                output = self._format_hierarchical_output(entries, total_count, max_entries)
                return output
            else:
                # Call the non-recursive list implementation
                results = self._list_contents(
                    path=path,
                    repo_dir=repo_dir,
                    gitignore_patterns=gitignore_patterns
                )
                
                # Check for errors or empty directories
                if not results:
                    return f"No entries found in directory '{path}'"
                    
                # Check for error
                if len(results) == 1 and "error" in results[0]:
                    return f"Error listing directory: {results[0]['error']}"
                
                # Count total entries and apply max_entries limit
                total_entries = len(results)
                displayed_entries = results[:max_entries]
                
                # Format like Linux ls command with additional information about remaining entries
                output = []
                output.append(f"Directory: {path or '/'}")
                
                for entry in displayed_entries:
                    name = entry["name"]
                    # Add trailing slash for directories
                    if entry.get("is_directory", False):
                        name = f"{name}/"
                    output.append(name)
                
                # Add information about remaining entries
                if total_entries > max_entries:
                    remaining = total_entries - max_entries
                    output.append(f"... ({remaining} more items)")
                    
                # Add summary line
                if total_entries > max_entries:
                    output.append(f"\nShowing {max_entries} of {total_entries} items (limited to {max_entries})")
                else:
                    output.append(f"\nTotal items: {total_entries}")
                
                # Join entries with newlines and return
                return "\n".join(output)
            
        except Exception as e:
            return f"Error listing directory: {str(e)}"
    
    def _list_contents(self, 
                     path: str = "",
                     repo_dir: Optional[str] = DEFAULT_REPO_DIR,
                     gitignore_patterns: Optional[Set[str]] = None) -> List[Dict[str, Any]]:
        """
        List contents of a directory
        
        Args:
            path: Relative path within the repository
            repo_dir: Base repository directory
            gitignore_patterns: Set of gitignore patterns
            
        Returns:
            List of directory entries with metadata
        """
        repo_dir = repo_dir or os.getcwd()
        target_path = os.path.join(repo_dir, path)
        
        # Make sure the path exists
        if not os.path.exists(target_path):
            return []
            
        # Make sure the path is a directory
        if not os.path.isdir(target_path):
            return []
            
        results = []
        
        try:
            # Get all entries in the directory
            entries = os.listdir(target_path)
            
            # Process each entry
            for entry in sorted(entries):
                entry_path = os.path.join(target_path, entry)
                
                # Apply filters
                if self._should_exclude(entry, entry_path, repo_dir, path, gitignore_patterns):
                    continue
                    
                is_dir = os.path.isdir(entry_path)
                
                # Get file size and type for files
                size = 0
                file_type = 'directory' if is_dir else 'unknown'
                
                if not is_dir:
                    try:
                        size = os.path.getsize(entry_path)
                        file_type = os.path.splitext(entry)[1].lstrip('.') or 'unknown'
                    except:
                        pass
                        
                # Create entry metadata
                entry_info = {
                    "name": entry,
                    "is_directory": is_dir,
                    "type": file_type,
                    "size": size
                }
                
                results.append(entry_info)
                
            return results
            
        except Exception as e:
            # Return error information
            return [{"error": str(e)}]
    
    def _list_contents_recursive(self, 
                               path: str = "",
                               repo_dir: Optional[str] = DEFAULT_REPO_DIR,
                               max_entries: int = 100,
                               max_depth: int = 3,
                               gitignore_patterns: Optional[Set[str]] = None) -> tuple[Dict[str, Any], int]:
        """
        Recursively list contents of a directory and its subdirectories
        
        Args:
            path: Relative path within the repository
            repo_dir: Base repository directory
            max_entries: Maximum number of entries to return
            max_depth: Maximum depth to traverse
            gitignore_patterns: Set of gitignore patterns
            
        Returns:
            Tuple of (hierarchical directory structure, total count of entries)
        """
        repo_dir = repo_dir or os.getcwd()
        target_path = os.path.join(repo_dir, path)
        
        # Make sure the path exists
        if not os.path.exists(target_path):
            return {}, 0
            
        # Make sure the path is a directory
        if not os.path.isdir(target_path):
            return {}, 0
        
        # Initialize result structure
        result = {
            "path": path or "/",
            "entries": [],
            "remaining": 0,
            "total_available": 0  # Track total available entries including those not shown
        }
        
        # Count for balancing entries across directories
        total_count = 0
        
        try:
            # Get all entries in the directory
            entries = sorted(os.listdir(target_path))
            
            # First pass to count and collect basic info
            dirs = []
            files = []
            
            for entry in entries:
                entry_path = os.path.join(target_path, entry)
                rel_path = os.path.join(path, entry) if path else entry
                
                # Apply filters
                if self._should_exclude(entry, entry_path, repo_dir, path, gitignore_patterns):
                    continue
                    
                is_dir = os.path.isdir(entry_path)
                
                if is_dir:
                    dirs.append((entry, rel_path, entry_path))
                else:
                    files.append({
                        "name": entry,
                        "is_directory": False,
                        "type": os.path.splitext(entry)[1].lstrip('.') or 'unknown',
                        "size": os.path.getsize(entry_path)
                    })
            
            # Count total available entries for statistics
            result["total_available"] = len(files) + len(dirs)
            
            # Add files first (up to a portion of max_entries)
            files_to_add = min(len(files), max_entries // 2)
            result["entries"].extend(files[:files_to_add])
            total_count += files_to_add
            
            # Track remaining files that won't be shown
            if len(files) > files_to_add:
                result["remaining"] += len(files) - files_to_add
            
            # Reserve remaining entries for directories
            remaining_entries = max_entries - files_to_add
            
            # If we have directories and are not at max depth, process them
            if dirs and max_depth > 0 and remaining_entries > 0:
                # Calculate entries per directory (at least 1)
                entries_per_dir = max(1, remaining_entries // len(dirs))
                
                # Process each directory
                for dir_name, dir_rel_path, dir_path in dirs:
                    # Base directory entry
                    dir_entry = {
                        "name": dir_name,
                        "is_directory": True,
                        "children": None,
                        "child_count": 0
                    }
                    
                    # Skip if we've reached max entries
                    if total_count >= max_entries:
                        result["remaining"] += 1
                        continue
                    
                    # Load gitignore patterns for this subdirectory (if any new ones)
                    subdir_gitignore_patterns = self._load_gitignore_patterns(repo_dir, dir_rel_path)
                    # Merge with parent patterns
                    if gitignore_patterns:
                        subdir_gitignore_patterns.update(gitignore_patterns)
                    
                    # Recursively list this directory
                    subdir_result, subdir_count = self._list_contents_recursive(
                        dir_rel_path, 
                        repo_dir, 
                        entries_per_dir, 
                        max_depth - 1,
                        subdir_gitignore_patterns
                    )
                    
                    if subdir_count > 0 or "total_available" in subdir_result:
                        dir_entry["children"] = subdir_result
                        dir_entry["child_count"] = subdir_count
                        # Add the total available count for statistics
                        if "total_available" in subdir_result:
                            dir_entry["total_available"] = subdir_result["total_available"]
                        result["entries"].append(dir_entry)
                        total_count += 1  # Count the directory itself
                        total_count += subdir_count  # Add children count
                    else:
                        # Even if empty, add directory
                        result["entries"].append(dir_entry)
                        total_count += 1
            
            # Add remaining directories as simple entries if we didn't process them recursively
            remaining_dirs = [d for d, _, _ in dirs if not any(e.get("name") == d and e.get("is_directory") for e in result["entries"])]
            for dir_name in remaining_dirs:
                if total_count < max_entries:
                    result["entries"].append({
                        "name": dir_name,
                        "is_directory": True
                    })
                    total_count += 1
                else:
                    result["remaining"] += 1
            
            return result, total_count
            
        except Exception as e:
            # Return error information
            return {"error": str(e)}, 0
    
    def _format_hierarchical_output(self, structure: Dict[str, Any], total_count: int, max_entries: int) -> str:
        """
        Format the hierarchical structure into a string representation
        
        Args:
            structure: The hierarchical directory structure
            total_count: Total count of entries
            max_entries: Maximum entries allowed
            
        Returns:
            Formatted string with hierarchical representation
        """
        output = []
        
        def _format_entry(entry, prefix="", is_last=False):
            # Choose the appropriate tree characters
            branch = "└── " if is_last else "├── "
            continuation = "    " if is_last else "│   "
            
            # Format name with trailing slash for directories
            name = entry["name"]
            if entry.get("is_directory", False):
                name = f"{name}/"
            
            # Add the entry
            output.append(f"{prefix}{branch}{name}")
            
            # Process children if any
            if entry.get("children") and entry.get("child_count", 0) > 0:
                children = entry["children"]["entries"]
                child_prefix = prefix + continuation
                
                for i, child in enumerate(children):
                    is_last_child = (i == len(children) - 1) and entry["children"].get("remaining", 0) == 0
                    _format_entry(child, child_prefix, is_last_child)
                
                # Show remaining count if applicable
                remaining = entry["children"].get("remaining", 0)
                if remaining > 0:
                    output.append(f"{child_prefix}└── ... ({remaining} more items)")
        
        # Add the root path
        output.append(f"Directory: {structure['path']}")
        
        # Process each entry
        entries = structure["entries"]
        for i, entry in enumerate(entries):
            is_last = (i == len(entries) - 1) and structure.get("remaining", 0) == 0
            _format_entry(entry, "", is_last)
        
        # Always show remaining count at root level if applicable
        remaining = structure.get("remaining", 0)
        if remaining > 0:
            output.append(f"... ({remaining} more items)")
        
        # Add summary
        if total_count > 0:
            # Always show count information, regardless of whether max_entries limit was reached
            displayed_count = min(total_count, max_entries)
            total_available = displayed_count + structure.get("remaining", 0)
            
            if total_available > displayed_count:
                output.append(f"\nShowing {displayed_count} of {total_available} items (limited to {max_entries})")
            else:
                output.append(f"\nTotal items: {total_count}")
        
        return "\n".join(output)


# Legacy function for backward compatibility
def list_dir(path: str = "", 
           repo_dir: Optional[str] = DEFAULT_REPO_DIR,
           recursive: bool = True,
           max_entries: int = 100,
           max_depth: int = 3) -> str:
    """
    List contents of a directory
    
    Args:
        path: Relative path within the repository
        repo_dir: Base repository directory
        recursive: Whether to recursively list subdirectories
        max_entries: Maximum number of entries to show
        max_depth: Maximum depth to traverse in recursive mode
        
    Returns:
        String with directory contents in a hierarchical format
    """
    tool = ListDirTool()
    params = {
        "path": path,
        "repo_dir": repo_dir,
        "recursive": recursive,
        "max_entries": max_entries,
        "max_depth": max_depth
    }
    return tool.call(json.dumps(params)) 