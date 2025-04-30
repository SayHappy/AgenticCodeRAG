import os
import re
import sys
import json
import fnmatch
from typing import Dict, Any, List, Optional, Set

from grep_ast import TreeContext
from qwen_agent.tools.base import BaseTool, register_tool
from reposearch_agent.config import DEFAULT_REPO_DIR

# 导入核心功能
from reposearch_agent.tools.grep_core import GrepCore, grep_search as core_grep_search

def escape_regex(pattern: str) -> str:
    """
    Escape special regex characters in a string to make it safe for use in a regex pattern.
    """
    special_chars = r'[](){}*+?|^$.\\'
    return ''.join('\\' + c if c in special_chars else c for c in pattern)


@register_tool('grep_search')
class GrepSearchTool(BaseTool):
    description = 'Search for pattern matches within files or directories using regex patterns.'
    parameters = [
        {
            'name': 'query',
            'type': 'string',
            'description': 'The query to search for. Use commas to separate multiple search keywords (e.g., "keyword1,keyword2").',
            'required': True,
        },
        {
            'name': 'file_extension',
            'type': 'string',
            'description': 'File extension to search (e.g., "py", "js", "ts"). Can be a comma-separated list like "py,js,ts".',
            'required': False,
        },
        {
            'name': 'max_results',
            'type': 'integer',
            'description': 'Maximum number of files to return when using complex_mode, or maximum results when using simple mode. Recommended values: 10-30 for complex mode, 50-100 for simple mode.',
            'required': False,
        },
        {
            'name': 'complex_mode',
            'type': 'boolean',
            'description': 'Whether to use complex search mode with context and AST parsing (slower but more detailed) or simple search mode (faster, basic line matching).',
            'required': False,
        }
    ]
    
    def __init__(self, tool_cfg=None):
        """Initialize the grep search tool"""
        self._grep_core = GrepCore()
    
    def call(self, params: str, **kwargs) -> str:
        # Parse parameters
        try:
            params_dict = json.loads(params)
            return self.process_grep_search(params_dict)
        except Exception as e:
            return f"Error in grep search: {str(e)}"
            
    def process_grep_search(self, params: Dict[str, Any]) -> str:
        """
        Process grep search parameters and return formatted results
        
        Args:
            params: Dictionary of search parameters
            
        Returns:
            Formatted search results
        """
        # 设置默认存储库目录
        if 'repo_dir' not in params:
            params['repo_dir'] = DEFAULT_REPO_DIR
        
        # 设置默认值
        if 'complex_mode' not in params:
            params['complex_mode'] = True
        
        # 根据模式设置默认的最大结果数
        if 'max_results' not in params:
            if params.get('complex_mode', True):
                params['max_results'] = 20  # 复杂模式默认搜索20个文件
            else:
                params['max_results'] = 100  # 简单模式默认搜索100个结果
        
        # 添加简单模式标志
        if not params.get('complex_mode', True):
            params['simple_mode'] = True
            
        # 调用核心功能处理
        return self._grep_core.process_grep_search(params)


# Legacy function for backward compatibility
def grep_search(query: str,
              repo_dir: Optional[str] = DEFAULT_REPO_DIR,
              file_pattern: Optional[str] = None,
              case_sensitive: bool = True,
              max_results: int = 20,
              complex_mode: bool = True) -> str:
    """
    Search for pattern matches in files
    
    Args:
        query: The string to search for (can be comma-separated)
        repo_dir: Directory to search in
        file_pattern: Optional file extension or comma-separated list of extensions
        case_sensitive: Whether the search should be case sensitive
        max_results: Maximum number of files (complex mode) or results (simple mode) to return
        complex_mode: Whether to use complex search with context and AST parsing
        
    Returns:
        Search results formatted in Linux grep style
    """
    # 调用核心功能
    return core_grep_search(
        query=query,
        repo_dir=repo_dir,
        file_pattern=file_pattern,
        case_sensitive=case_sensitive,
        max_results=max_results
    )