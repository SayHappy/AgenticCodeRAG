import os
import json
from typing import Dict, Any, List, Optional

from qwen_agent.tools.base import BaseTool, register_tool
from reposearch_agent.config import DEFAULT_REPO_DIR


@register_tool('read_file')
class ReadFileTool(BaseTool):
    description = 'Read file contents with line limits to inspect specific code sections，Read as much as possible without considering cost.'
    parameters = [
        {
            'name': 'file_path',
            'type': 'string',
            'description': 'Relative path to the file',
            'required': True,
        },
        {
            'name': 'start_line',
            'type': 'integer',
            'description': 'Starting line number (1-indexed)',
            'required': False,
        },
        {
            'name': 'end_line',
            'type': 'integer',
            'description': 'Ending line number (1-indexed, inclusive)',
            'required': False,
        },
        {
            'name': 'max_lines',
            'type': 'integer',
            'description': 'Maximum number of lines to read',
            'required': False,
        }
    ]
    
    def __init__(self, tool_cfg=None):
        """Initialize the file reading tool"""
        pass
    
    def call(self, params: str, **kwargs) -> str:
        # Parse parameters
        try:
            params = json.loads(params)
            file_path = params.get('file_path')
            start_line = params.get('start_line', 1)
            end_line = params.get('end_line')
            max_lines = params.get('max_lines', 500)
            repo_dir = params.get('repo_dir', DEFAULT_REPO_DIR)
            
            # Call the read implementation
            result = self._read(
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                max_lines=max_lines,
                repo_dir=repo_dir
            )
            
            # Check for errors
            if not result.get("success", False):
                return json.dumps({"result": result.get("error", "Error reading file")})
                
            # Format the output for display
            response = {
                "result": f"File contents from line {result['start_line']} to {result['end_line']} (total lines: {result['total_lines']}):",
                "file_info": {
                    "file_path": result["file_path"],
                    "start_line": result["start_line"],
                    "end_line": result["end_line"],
                    "total_lines": result["total_lines"],
                    "truncated": result["truncated"]
                },
                "content": result["content"]
            }
            
            # Add truncation warnings
            if result.get("truncated", False):
                truncation_info = []
                if result.get("lines_before", 0) > 0:
                    truncation_info.append(f"{result['lines_before']} lines before")
                if result.get("lines_after", 0) > 0:
                    truncation_info.append(f"{result['lines_after']} lines after")
                    
                if truncation_info:
                    response["truncation_warning"] = f"File is truncated: {', '.join(truncation_info)}"
            
            return json.dumps(response, ensure_ascii=False)
            
        except Exception as e:
            return json.dumps({"error": f"Error reading file: {str(e)}"})
    
    def _read(self, 
            file_path: str,
            start_line: int = 1,
            end_line: Optional[int] = None,
            max_lines: int = 500,
            repo_dir: Optional[str] = DEFAULT_REPO_DIR) -> Dict[str, Any]:
        """
        Read file contents with line limits
        
        Args:
            file_path: Relative path to the file
            start_line: Starting line number (1-indexed)
            end_line: Ending line number (1-indexed, inclusive)
            max_lines: Maximum number of lines to read
            repo_dir: Base repository directory
            
        Returns:
            Dictionary with file contents and metadata
        """
        # Resolve the full path
        repo_dir = repo_dir or os.getcwd()
        full_path = os.path.join(repo_dir, file_path)
        
        # Make sure the path exists
        if not os.path.exists(full_path):
            return {
                "error": f"File not found: {file_path}",
                "success": False
            }
            
        # Make sure it's a file
        if not os.path.isfile(full_path):
            return {
                "error": f"Not a file: {file_path}",
                "success": False
            }
            
        try:
            # Read the file content
            with open(full_path, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                
            # Get the total number of lines
            total_lines = len(all_lines)
            
            # Validate start_line
            if start_line < 1:
                start_line = 1
                
            # Handle end_line
            if end_line is None:
                end_line = start_line + max_lines - 1
            
            # Make sure end_line doesn't exceed the file length
            end_line = min(end_line, total_lines)
            
            # Make sure we don't exceed max_lines
            if end_line - start_line + 1 > max_lines:
                end_line = start_line + max_lines - 1
                
            # Get the requested lines (0-indexed in the list)
            requested_lines = all_lines[start_line-1:end_line]
            
            # Prepare the result
            result = {
                "file_path": file_path,
                "start_line": start_line,
                "end_line": end_line,
                "total_lines": total_lines,
                "content": "".join(requested_lines),
                "success": True
            }
            
            # Add information about truncation
            if start_line > 1 or end_line < total_lines:
                result["truncated"] = True
                
                if start_line > 1:
                    result["lines_before"] = start_line - 1
                    
                if end_line < total_lines:
                    result["lines_after"] = total_lines - end_line
            else:
                result["truncated"] = False
                
            return result
            
        except Exception as e:
            return {
                "error": f"Error reading file: {str(e)}",
                "success": False
            }


# Legacy function for backward compatibility
def read_file(file_path: str,
            start_line: int = 1,
            end_line: Optional[int] = None,
            max_lines: int = 500,
            repo_dir: Optional[str] = DEFAULT_REPO_DIR) -> Dict[str, Any]:
    """
    Read file contents with line limits
    
    Args:
        file_path: Relative path to the file
        start_line: Starting line number (1-indexed)
        end_line: Ending line number (1-indexed, inclusive)
        max_lines: Maximum number of lines to read
        repo_dir: Base repository directory
        
    Returns:
        Dictionary with file contents and metadata
    """
    tool = ReadFileTool()
    params = {
        "file_path": file_path,
        "start_line": start_line,
        "end_line": end_line,
        "max_lines": max_lines,
        "repo_dir": repo_dir
    }
    result = tool.call(json.dumps(params))
    return json.loads(result) 