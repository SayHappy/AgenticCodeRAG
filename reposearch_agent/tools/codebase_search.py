import os
import sys
import json
from typing import Dict, Any, List, Optional

# Add parent directory to path to find the vec_db module
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from script.vec_db.api import CodeRAGAPI

# Import configuration
from reposearch_agent.config import (
    DB_PATH, 
    EMBEDDING_MODEL, 
    EMBEDDING_DIM, 
    CACHE_DIR,
    DEFAULT_TOP_K,
    DEFAULT_SEARCH_TYPE,
    DEFAULT_REPO_NAME
)

from qwen_agent.tools.base import BaseTool, register_tool


@register_tool('codebase_search')
class CodebaseSearchTool(BaseTool):
    description = 'Search for code snippets in the repository using semantic search.'
    parameters = [
        {
            'name': 'query',
            'type': 'string',
            'description': 'The search query to find relevant code',
            'required': True,
        }
    ]
    
    def __init__(self, tool_cfg=None):
        """Initialize the codebase search tool"""
        self.api = CodeRAGAPI(
            db_path=DB_PATH,
            embedding_model=EMBEDDING_MODEL,
            embedding_dim=EMBEDDING_DIM,
            cache_dir=CACHE_DIR
        )
    
    def call(self, params: str, **kwargs) -> str:
        # Parse parameters
        try:
            params = json.loads(params)
            query = params.get('query')
            repo_name = params.get('repo_name', DEFAULT_REPO_NAME)
            language = params.get('language')
            framework = params.get('framework')
            element_type = params.get('element_type')
            top_k = params.get('top_k', DEFAULT_TOP_K)
            search_type = params.get('search_type', DEFAULT_SEARCH_TYPE)
            
            # Call the search implementation
            results = self._search_code(
                query=query,
                repo_name=repo_name,
                language=language,
                framework=framework,
                element_type=element_type,
                top_k=top_k,
                search_type=search_type
            )
            
            # Format and return the results
            if not results:
                return json.dumps({"result": "No code found matching your query."})
                
            response = {
                "result": f"Found {len(results)} code snippets:",
                "snippets": results
            }
            
            return json.dumps(response, ensure_ascii=False)
            
        except Exception as e:
            return json.dumps({"error": f"Error in codebase search: {str(e)}"})
        finally:
            self.api.close()
    
    def _search_code(self, 
               query: str,
               repo_name: Optional[str] = DEFAULT_REPO_NAME,
               language: Optional[str] = None,
               framework: Optional[str] = None,
               element_type: Optional[str] = None,
               top_k: int = DEFAULT_TOP_K,
               search_type: str = DEFAULT_SEARCH_TYPE) -> List[Dict[str, Any]]:
        """
        Search for code in the repository
        
        Args:
            query: The search query
            repo_name: Optional repository filter
            language: Optional language filter (python, javascript, etc.)
            framework: Optional framework filter (react, django, etc.)
            element_type: Optional element type filter (function, class, etc.)
            top_k: Number of results to return
            search_type: Search type (vector, keyword, hybrid)
            
        Returns:
            List of search results with code snippets and metadata
        """
        results = self.api.search(
            query=query,
            top_k=top_k,
            repo_name=repo_name,
            language=language,
            framework=framework,
            element_type=element_type,
            search_type=search_type
        )
        
        # Format results for display in chat
        formatted_results = []
        for i, result in enumerate(results):
            formatted_result = {
                "file_path": result.get("file_path", ""),
                "language": result.get("language", "unknown"),
                "start_line": result.get("start_line", 0) + 1,  # Convert to 1-indexed for display
                "end_line": result.get("end_line", 0),
                "content": result.get("content", ""),
                "similarity_score": result.get("similarity_score", 0)
            }
            
            # Add framework if available
            if result.get("framework"):
                formatted_result["framework"] = result.get("framework")
                
            # Add semantic elements context if available
            if result.get("semantic_elements"):
                elements = []
                for elem in result.get("semantic_elements", [])[:3]:  # Show up to 3 elements
                    elements.append({
                        "type": elem.get("element_type", "Unknown"),
                        "name": elem.get("name", "Unnamed"),
                        "lines": f"{elem.get('start_line', 0)+1}-{elem.get('end_line', 0)}"
                    })
                formatted_result["context_elements"] = elements
                
            formatted_results.append(formatted_result)
            
        return formatted_results


# Legacy function for backward compatibility
def codebase_search(query: str,
                  repo_name: Optional[str] = DEFAULT_REPO_NAME,
                  language: Optional[str] = None,
                  framework: Optional[str] = None,
                  element_type: Optional[str] = None,
                  top_k: int = DEFAULT_TOP_K,
                  search_type: str = DEFAULT_SEARCH_TYPE) -> Dict[str, Any]:
    """
    Search for code in the repository
    
    Args:
        query: The search query
        repo_name: Optional repository filter
        language: Optional language filter (python, javascript, etc.)
        framework: Optional framework filter (react, django, etc.)
        element_type: Optional element type filter (function, class, etc.)
        top_k: Number of results to return (default: 5)
        search_type: Search type (vector, keyword, hybrid) (default: vector)
        
    Returns:
        Search results with code snippets and metadata
    """
    tool = CodebaseSearchTool()
    params = {
        "query": query,
        "repo_name": repo_name,
        "language": language,
        "framework": framework,
        "element_type": element_type,
        "top_k": top_k,
        "search_type": search_type
    }
    result = tool.call(json.dumps(params))
    return json.loads(result) 