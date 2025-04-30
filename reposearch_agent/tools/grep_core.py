#!/usr/bin/env python3
import os
import re
import sys
import fnmatch
from typing import Dict, Any, List, Optional, Set

# Import TreeContext for AST-based code searching
from grep_ast import TreeContext

# Set a reasonable recursion limit
sys.setrecursionlimit(3000)  # Default is usually 1000


def escape_regex(pattern: str) -> str:
    """
    Escape special regex characters in a string to make it safe for use in a regex pattern.
    """
    special_chars = r'[](){}*+?|^$.\\'
    return ''.join('\\' + c if c in special_chars else c for c in pattern)


class GrepCore:
    def __init__(self):
        """Initialize the grep search tool"""
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
    
    def _should_exclude(self, file_path: str, repo_dir: str, gitignore_patterns: Set[str]) -> bool:
        """
        Check if a file should be excluded based on filters
        
        Args:
            file_path: Path to the file
            repo_dir: Base repository directory
            gitignore_patterns: Set of gitignore patterns
            
        Returns:
            True if file should be excluded, False otherwise
        """
        # Get the relative path and file name
        rel_path = os.path.relpath(file_path, repo_dir)
        file_name = os.path.basename(file_path)
        parent_dir = os.path.dirname(rel_path)
        
        # Filter hidden files/directories (starting with .)
        if file_name.startswith('.'):
            return True
            
        # Check if any parent directory is hidden
        path_parts = rel_path.split(os.sep)
        for part in path_parts:
            if part.startswith('.'):
                return True
                
        # Filter entries mentioned in gitignore
        if gitignore_patterns:
            for pattern in gitignore_patterns:
                # Handle directory-specific patterns
                if '/' in pattern:
                    if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(rel_path, f"{pattern}/*"):
                        return True
                # Handle wildcard patterns
                elif '*' in pattern:
                    if fnmatch.fnmatch(file_name, pattern):
                        return True
                # Handle simple directory/file names
                elif file_name == pattern or rel_path == pattern or (parent_dir and parent_dir == pattern):
                    return True
                    
        return False
    
    def _file_matches_extensions(self, file_name: str, extensions: List[str]) -> bool:
        """
        Check if a file matches any of the provided extensions
        
        Args:
            file_name: Name of the file
            extensions: List of file extensions to match (without dot)
            
        Returns:
            True if file matches any extension, False otherwise
        """
        if not extensions:
            return True  # No filter applied
            
        # Get file extension (without the dot)
        _, ext = os.path.splitext(file_name)
        ext = ext[1:] if ext else ""
        
        # Check if the file extension matches any in the list
        return ext.lower() in [e.lower() for e in extensions]
            
    def process_grep_search(self, params: Dict[str, Any]) -> str:
        """
        Process grep search parameters and return formatted results
        
        Args:
            params: Dictionary of search parameters
            
        Returns:
            Formatted search results
        """
        query = params.get('query')
        repo_dir = params.get('repo_dir', os.getcwd())
        
        # Handle both legacy 'file_pattern' and new 'file_extension'
        file_pattern = params.get('file_pattern')
        file_extension = params.get('file_extension', file_pattern)
        
        # Process extensions (convert to list if comma-separated)
        extensions = []
        if file_extension:
            # Handle comma-separated list of extensions
            if ',' in file_extension:
                extensions = [ext.strip() for ext in file_extension.split(',')]
            else:
                extensions = [file_extension.strip()]
        
        case_sensitive = params.get('case_sensitive', True)
        max_results = params.get('max_results', 20)  # 默认20个文件
        
        # 检查是否使用简单搜索模式
        simple_mode = params.get('simple_mode', False)
        
        # Set up for gitignore filtering
        self._repo_dir = repo_dir
        gitignore_patterns = self._load_gitignore_patterns(repo_dir)
        
        # Call the search implementation
        results = self._search(
            query=query,
            repo_dir=repo_dir,
            extensions=extensions,
            case_sensitive=case_sensitive,
            max_results=max_results,
            gitignore_patterns=gitignore_patterns,
            simple_mode=simple_mode
        )
        
        # Debug info
        match_count = sum(1 for r in results if r.get("match", False) and not r.get("is_file_marker", False))
        file_count = sum(1 for r in results if r.get("is_file_marker", False))
        print(f"Found {match_count} matches in {file_count} files")
        
        # Format and return the results in Linux grep style
        if not results:
            return "No matches found for your query."
        
        # 简化输出处理流程
        formatted_results = []
        current_file = None
        
        for result in results:
            file_path = result.get("file_path")
            
            # 处理新文件
            if current_file != file_path:
                current_file = file_path
                formatted_results.append(f"\n{file_path}:")
            
            # 如果是分隔符，直接添加
            if result.get("is_separator", False):
                formatted_results.append(result.get("content", ""))
                continue
            
            # 如果是带格式的行，直接添加内容
            if result.get("formatted", False):
                content = result.get("content", "")
                formatted_results.append(content)
        
        return "\n".join(formatted_results)
    
    def _search(self, 
               query: str,
               repo_dir: Optional[str] = None,
               extensions: Optional[List[str]] = None,
               case_sensitive: bool = True,
               max_results: int = 20,
               gitignore_patterns: Optional[Set[str]] = None,
               simple_mode: bool = False) -> List[Dict[str, Any]]:
        """
        Search for patterns in files
        
        Args:
            query: The string to search for (can be comma-separated)
            repo_dir: Directory to search in
            extensions: List of file extensions to search in (without dot)
            case_sensitive: Whether the search should be case sensitive
            max_results: Maximum number of files to return (default: 20)
            gitignore_patterns: Set of gitignore patterns to exclude
            simple_mode: Whether to use simple search (line matching only) instead of AST parsing
            
        Returns:
            List of search results with matched lines and context
        """
        # 用于收集每个文件的匹配信息
        file_matches = {}  # 格式: {file_path: [matches]}
        repo_dir = repo_dir or os.getcwd()
        
        # 调试信息
        print(f"Starting search for '{query}' in {repo_dir}")
        if simple_mode:
            print("Using simple search mode (faster, line matching only)")
            # 在简单模式下可以处理更多结果
            if max_results < 50:
                max_results = 50
            print(f"Max results: {max_results}")
        else:
            print("Using complex search mode (slower, with context and AST parsing)")
            print(f"Max files: {max_results}")
        
        # 如果在简单模式下，保存已找到的匹配数
        total_matches_found = 0
        
        # Split query into multiple patterns if comma-separated
        queries = [q.strip() for q in query.split(',') if q.strip()]
        if not queries:
            queries = [query]  # Fallback if no valid queries after splitting
        
        # Process each query pattern
        for current_query in queries:
            print(f"Processing query: '{current_query}'")
            files_processed = 0
            matches_found = 0
            
            for root, dirs, files in os.walk(repo_dir):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                # Load additional gitignore patterns for this directory
                rel_dir_path = os.path.relpath(root, repo_dir)
                if rel_dir_path == '.':
                    rel_dir_path = ""
                    
                dir_patterns = gitignore_patterns
                if rel_dir_path:
                    # Check for additional gitignore files in this directory
                    local_patterns = self._load_gitignore_patterns(repo_dir, rel_dir_path)
                    if local_patterns:
                        if dir_patterns:
                            dir_patterns = dir_patterns.union(local_patterns)
                        else:
                            dir_patterns = local_patterns
                
                for file in files:
                    # Skip files not matching extensions
                    if not self._file_matches_extensions(file, extensions):
                        continue
                    
                    file_path = os.path.join(root, file)
                    
                    # Skip files excluded by gitignore or hidden files
                    if self._should_exclude(file_path, repo_dir, dir_patterns):
                        continue
                    
                    files_processed += 1
                    # 每处理100个文件显示一次进度
                    if files_processed % 100 == 0:
                        print(f"Processed {files_processed} files, found {matches_found} matches in {len(file_matches)} files so far...")
                    
                    try:
                        # Try to open as text file
                        with open(file_path, 'r', encoding='utf-8') as f:
                            code = f.read()
                        
                        # 收集当前文件的匹配结果
                        file_results = []
                        rel_path = os.path.relpath(file_path, repo_dir)
                        
                        # Use a simple fallback for large files to prevent recursion issues
                        if len(code.splitlines()) > 2000 or simple_mode:
                            # For large files, use a simpler approach without TreeContext
                            matching_lines = self._simple_grep(code, current_query, case_sensitive)
                            if matching_lines:
                                matches_found += len(matching_lines)
                                lines = code.splitlines()
                                
                                # 添加文件标记
                                file_results.append({
                                    "file_path": rel_path,
                                    "match": True,
                                    "is_file_marker": True
                                })
                                
                                for line_num in matching_lines:
                                    # Ensure the match flag is set to True for simple grep matches
                                    result_item = {
                                        "file_path": rel_path,
                                        "line_number": line_num + 1,  # Convert to 1-indexed
                                        "content": f"  █ {line_num + 1}: {lines[line_num]}",
                                        "raw_content": lines[line_num],
                                        "match": True,
                                        "formatted": True
                                    }
                                    file_results.append(result_item)
                                    
                                    # 在简单模式下，只添加匹配行，不添加上下文
                                    if not simple_mode:
                                        # 添加上下文行
                                        context_range = 1  # Lines before and after
                                        for ctx_idx in range(max(0, line_num - context_range), min(len(lines), line_num + context_range + 1)):
                                            if ctx_idx == line_num:  # 跳过匹配行本身
                                                continue
                                                
                                            ctx_result = {
                                                "file_path": rel_path,
                                                "line_number": ctx_idx + 1,
                                                "content": f"  │ {ctx_idx + 1}: {lines[ctx_idx]}",
                                                "raw_content": lines[ctx_idx],
                                                "match": False,
                                                "formatted": True
                                            }
                                            file_results.append(ctx_result)
                                
                            # 如果有匹配结果，添加到文件匹配集合中
                            if file_results:
                                file_matches[rel_path] = file_results
                                
                                # 在简单模式下，如果达到了指定的匹配结果数，就停止搜索
                                if simple_mode:
                                    total_matches_found += len(matching_lines)
                                    if total_matches_found >= max_results:
                                        print(f"Simple mode: reached maximum number of matches ({max_results})")
                                        break
                            continue
                        
                        # Use TreeContext for AST-aware code searching
                        try:
                            tree_context = TreeContext(
                                filename=file_path,
                                code=code,
                                color=False,
                                verbose=False,
                                line_number=True,
                            )
                            
                            # Find matching lines
                            matching_lines = tree_context.grep(current_query, not case_sensitive)
                            
                            if matching_lines:
                                matches_found += len(matching_lines)
                                print(f"Found {len(matching_lines)} matches in {rel_path}")
                                
                                # Add lines of interest to get proper context
                                tree_context.add_lines_of_interest(matching_lines)
                                tree_context.add_context()
                                
                                # Add file marker
                                file_results.append({
                                    "file_path": rel_path,
                                    "match": True,
                                    "is_file_marker": True,
                                    "match_count": len(matching_lines)  # 记录匹配次数
                                })
                                
                                # 直接使用 tree_context 的格式化输出
                                formatted_output = tree_context.format()
                                output_lines = formatted_output.strip().splitlines()
                                
                                print(f"Processed {len(output_lines)} formatted lines")
                                
                                # 添加格式化后的每一行到结果
                                for line in output_lines:
                                    # Skip empty lines or separator-only lines
                                    if not line.strip():
                                        continue
                                    
                                    # 处理省略号行
                                    if line.strip() == '⋮':
                                        file_results.append({
                                            "file_path": rel_path,
                                            "content": line,
                                            "is_separator": True,
                                            "formatted": True
                                        })
                                        continue
                                    
                                    # 检查是否包含行号
                                    parts = line.split(' ', 1)
                                    try:
                                        # 提取行号
                                        line_num = int(parts[0].strip())
                                        # 获取行内容（保留原始格式）
                                        content = parts[1] if len(parts) > 1 else ""
                                        # 检查是否是匹配行
                                        is_match = '█' in line
                                        
                                        # 直接使用完整行，包括标记
                                        file_results.append({
                                            "file_path": rel_path,
                                            "line_number": line_num,
                                            "content": line,
                                            "raw_content": content,
                                            "match": is_match,
                                            "formatted": True
                                        })
                                    except (ValueError, IndexError):
                                        # 非行号开头的行，但不是省略号，直接添加
                                        if not line.strip() == '⋮':
                                            file_results.append({
                                                "file_path": rel_path,
                                                "content": line,
                                                "is_separator": True,
                                                "formatted": True
                                            })
                                
                                # 如果有匹配结果，添加到文件匹配集合中
                                if file_results:
                                    file_matches[rel_path] = file_results
                                    
                                    # 在简单模式下，如果达到了指定的匹配文件数，就停止搜索
                                    if simple_mode:
                                        total_matches_found += len(matching_lines)
                                        if total_matches_found >= max_results:
                                            print(f"Simple mode: reached maximum number of matches ({max_results})")
                                            break
                                
                        except Exception as e:
                            print(f"Error in file {file_path}: {str(e)}")
                            # Fallback to simple grep if TreeContext fails
                            matching_lines = self._simple_grep(code, current_query, case_sensitive)
                            if matching_lines:
                                matches_found += len(matching_lines)
                                
                                # 添加文件标记
                                file_results.append({
                                    "file_path": rel_path,
                                    "match": True,
                                    "is_file_marker": True,
                                    "match_count": len(matching_lines)  # 记录匹配次数
                                })
                                
                                lines = code.splitlines()
                                for line_num in matching_lines:
                                    result_item = {
                                        "file_path": rel_path,
                                        "line_number": line_num + 1,  # Convert to 1-indexed
                                        "content": f"  █ {line_num + 1}: {lines[line_num]}",
                                        "raw_content": lines[line_num],
                                        "match": True,
                                        "formatted": True
                                    }
                                    file_results.append(result_item)
                                    
                                    # 添加上下文行
                                    context_range = 1  # Lines before and after
                                    for ctx_idx in range(max(0, line_num - context_range), min(len(lines), line_num + context_range + 1)):
                                        if ctx_idx == line_num:  # 跳过匹配行本身
                                            continue
                                            
                                        ctx_result = {
                                            "file_path": rel_path,
                                            "line_number": ctx_idx + 1,
                                            "content": f"  │ {ctx_idx + 1}: {lines[ctx_idx]}",
                                            "raw_content": lines[ctx_idx],
                                            "match": False,
                                            "formatted": True
                                        }
                                        file_results.append(ctx_result)
                                
                                # 如果有匹配结果，添加到文件匹配集合中
                                if file_results:
                                    file_matches[rel_path] = file_results
                                    
                                    # 在简单模式下，如果达到了指定的匹配文件数，就停止搜索
                                    if simple_mode:
                                        total_matches_found += len(matching_lines)
                                        if total_matches_found >= max_results:
                                            print(f"Simple mode: reached maximum number of matches ({max_results})")
                                            break
                    except (UnicodeDecodeError, IOError) as e:
                        # Skip binary files or files that can't be read
                        print(f"Cannot read file {file_path}: {str(e)}")
                        continue
            
            print(f"Processed a total of {files_processed} files, found {matches_found} matches in {len(file_matches)} files")
            
            # 如果在简单模式下，不需要排序，直接返回
            if simple_mode:
                if max_results > 0 and total_matches_found > max_results:
                    print(f"Limiting output to {max_results} matches")
                
                # 合并所有结果
                results = []
                for file_results in file_matches.values():
                    results.extend(file_results)
                
                return results
        
        # 按照匹配次数对文件排序，选择匹配次数最多的 max_results 个文件
        sorted_files = []
        
        # 计算每个文件的匹配行数
        file_match_counts = {}
        for file_path, results in file_matches.items():
            match_count = sum(1 for r in results if r.get("match", False) and not r.get("is_file_marker", False))
            file_match_counts[file_path] = match_count
        
        # 按匹配次数降序排序
        sorted_files = sorted(file_matches.keys(), key=lambda x: file_match_counts[x], reverse=True)
        
        # 限制文件数量
        if max_results > 0 and len(sorted_files) > max_results:
            sorted_files = sorted_files[:max_results]
            print(f"Limiting output to top {max_results} files with most matches")
        
        # 将所有选中文件的结果合并到最终结果
        results = []
        for file_path in sorted_files:
            results.extend(file_matches[file_path])
        
        return results

    def _simple_grep(self, code: str, query: str, case_sensitive: bool) -> List[int]:
        """Simple line-by-line grep implementation as fallback for large files or recursion issues"""
        matching_lines = []
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            pattern = re.compile(query, flags=flags)
            lines = code.splitlines()
            for i, line in enumerate(lines):
                if pattern.search(line):
                    matching_lines.append(i)
        except re.error:
            # If regex fails, try literal string search
            lines = code.splitlines()
            for i, line in enumerate(lines):
                if (query in line) if case_sensitive else (query.lower() in line.lower()):
                    matching_lines.append(i)
        
        return matching_lines


def grep_search(query: str,
              repo_dir: Optional[str] = None,
              file_pattern: Optional[str] = None,
              case_sensitive: bool = True,
              max_results: int = 20,
              simple_mode: bool = False) -> str:  # 默认20个文件
    """
    Search for pattern matches in files
    
    Args:
        query: The string to search for (can be comma-separated)
        repo_dir: Directory to search in
        file_pattern: Optional file extension or comma-separated list of extensions
        case_sensitive: Whether the search should be case sensitive
        max_results: Maximum number of files to return (default: 20)
        simple_mode: Whether to use simple search (line matching only)
        
    Returns:
        Search results formatted in Linux grep style
    """
    core = GrepCore()
    params = {
        "query": query,
        "repo_dir": repo_dir or os.getcwd(),
        "file_extension": file_pattern,  # Map to new parameter name
        "case_sensitive": case_sensitive,
        "max_results": max_results,
        "simple_mode": simple_mode
    }
    return core.process_grep_search(params)


# Command-line interface for when this file is run directly
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Search for patterns in files using regex')
    parser.add_argument('query', help='The regex pattern to search for')
    parser.add_argument('-d', '--directory', default=os.getcwd(), 
                        help='Directory to search in (default: current directory)')
    parser.add_argument('-e', '--extension', help='File extension(s) to search (comma-separated)')
    parser.add_argument('-i', '--ignore-case', action='store_true', 
                        help='Ignore case distinctions in pattern')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug output')
    parser.add_argument('-n', '--max-results', type=int, default=20,
                        help='Maximum number of files to return, sorted by match count (default: 20)')
    parser.add_argument('-s', '--simple', action='store_true',
                        help='Use simple search mode (faster, line matching only)')
    
    args = parser.parse_args()
    
    # Enable debug mode
    debug_mode = args.debug
    
    print(f"Searching for '{args.query}' in {args.directory}...")
    
    result = grep_search(
        query=args.query,
        repo_dir=args.directory,
        file_pattern=args.extension,
        case_sensitive=not args.ignore_case,
        max_results=args.max_results,
        simple_mode=args.simple
    )
    
    # Print results
    if result:
        print("\n" + result)
    else:
        print("No results found.") 