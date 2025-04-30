#!/usr/bin/env python3
"""
Common utilities for language parsing shared across all language implementations.
"""
import sys
import warnings
from pathlib import Path
from typing import List, Optional

# Import pygments for fallback reference finding
from pygments.lexers import guess_lexer_for_filename
from pygments.token import Token

# 抑制 FutureWarning
warnings.simplefilter("ignore", category=FutureWarning)

# 导入 grep-ast 相关模块
from grep_ast import filename_to_lang
try:
    from grep_ast.tsl import USING_TSL_PACK, get_language, get_parser
except ImportError:
    print("Error: Could not import from grep_ast.tsl. Is grep_ast correctly installed?", file=sys.stderr)
    sys.exit(1)

# Import rich for console output
from rich.console import Console
from rich.tree import Tree
from rich.markup import escape

# Create console object for output
console = Console()

# Determine the project base directory
def get_project_root() -> Path:
    """Get the project root directory"""
    # When using single files, the file is two levels down from the root
    # Adjust this if the file structure changes
    return Path(__file__).parent.parent

# Helper function to find the SCM query file for a language
def get_scm_fname(lang: str) -> Optional[Path]:
    """Load the tags queries for a given language, checking project structure first.
    
    Args:
        lang: The language identifier as used by grep-ast
        
    Returns:
        Path to the SCM query file or None if not found
    """
    project_root = get_project_root()
    queries_dir = project_root / "queries"
    
    # Path within the project's queries directory
    project_pack_path = queries_dir / "tree-sitter-language-pack" / f"{lang}-tags.scm"
    if project_pack_path.is_file():
        return project_pack_path

    project_langs_path = queries_dir / "tree-sitter-languages" / f"{lang}-tags.scm"
    if project_langs_path.is_file():
        return project_langs_path
    
    # Return None if not found in project structure
    return None

def get_tags_raw(fname: str, rel_fname: str, verbose: bool = False) -> List:
    """Extract tags (definitions and references) from a single file using grep_ast.
    
    This is the common raw tag extraction utility shared by all language parsers.
    
    Args:
        fname: Path to the file to analyze
        rel_fname: Relative path of the file (for tag construction)
        verbose: Whether to print verbose information
        
    Returns:
        List of Tag objects representing the parsed elements
    """
    from .base_parser import Tag, TagWithEndLine
    
    lang = filename_to_lang(fname)
    if not lang:
        if verbose:
            console.print(f"[yellow]无法确定语言: {fname}[/yellow]")
        return []
    try:
        language = get_language(lang)
        parser = get_parser(lang)
    except Exception as err:
        console.print(f"[yellow]跳过文件 {fname}: 加载解析器失败: {err}[/yellow]")
        return []

    query_scm_path = get_scm_fname(lang)
    if not query_scm_path or not query_scm_path.exists():
        if verbose:
            console.print(f"[yellow]未找到 {lang} 的查询文件 (.scm) in project structure[/yellow]")
        console.print(f"[yellow]警告: 无法进行基于 SCM 的详细分析，因为缺少 {lang} 的查询文件。[/yellow]")
        return [] # Return empty list if no SCM file found

    try:
        query_scm = query_scm_path.read_text(encoding='utf-8')
    except Exception as e:
        console.print(f"[red]读取查询文件失败 {query_scm_path}: {e}[/red]")
        return []

    try:
        # Use standard Path object read_text
        code = Path(fname).read_text(encoding='utf-8', errors='replace')
    except Exception as e:
        console.print(f"[yellow]读取文件 {fname} 失败: {e}[/yellow]")
        return []

    if not code:
        return []

    tree = None # Initialize tree
    raw_captures = [] # Initialize raw_captures
    try:
        tree = parser.parse(bytes(code, "utf-8"))
        query = language.query(query_scm)
        # Use captures_by_tags for potentially better structure if needed later
        raw_captures = query.captures(tree.root_node)

    except Exception as e:
        console.print(f"[red]解析或查询文件 {fname} 时出错: {e}[/red]")
        return []

    results = []
    saw = set() # Track if we saw definitions or references via tree-sitter

    # Align capture handling with RepoMap
    all_nodes = []
    if USING_TSL_PACK and isinstance(raw_captures, dict):
         for tag_name, nodes in raw_captures.items():
            all_nodes += [(node, tag_name) for node in nodes]
    elif isinstance(raw_captures, list):
         all_nodes = list(raw_captures)
    elif verbose:
        console.print(f"[yellow]未知的 captures 格式: {type(raw_captures)} for {fname}[/yellow]")

    for node, tag_name in all_nodes:
        kind = None
        if tag_name.startswith("name.definition."):
            kind = "def"
        elif tag_name.startswith("name.reference."):
            kind = "ref"
        else:
            # Skip other capture types (like 'body' ranges etc.)
            continue

        saw.add(kind) # Track that we found this kind via tree-sitter

        try:
            text = node.text.decode('utf-8', errors='replace')
            start_line = node.start_point[0] # 0-indexed line
            end_line = node.end_point[0]  # Add end line (0-indexed)

            # Create basic tag instance
            tag_instance = Tag(
                rel_fname=rel_fname,
                fname=fname,
                name=text,
                kind=kind,
                line=start_line,
            )
            # Add additional properties to the tag for start/end line
            tag_instance = tag_instance._replace(line=start_line)
            # Attach end_line as an attribute since it's not in the Tag namedtuple
            tag_instance = TagWithEndLine(*tag_instance, end_line)
            
            results.append(tag_instance)

        except Exception as e:
            if verbose:
                console.print(f"[red]处理节点时出错 for {tag_name} in {fname}: {e}[/red]")

    # --- Pygments Fallback ---
    # If we saw definitions but no references via tree-sitter, try pygments.
    if "ref" in saw:
        # If tree-sitter found refs, we assume it's comprehensive enough
        return results
    if "def" not in saw:
        # If tree-sitter found neither defs nor refs, nothing more to do
        return results

    # We saw defs, without any refs from tree-sitter. Use pygments.
    if verbose:
        console.print(f"[cyan]Info: Using Pygments to find references in {fname} as SCM provided only definitions.[/cyan]")

    try:
        # Use guess_lexer_for_filename which needs the code content
        lexer = guess_lexer_for_filename(fname, code)
        pygments_tokens = list(lexer.get_tokens(code))
        # Filter for Name tokens
        name_tokens = [token[1] for token in pygments_tokens if token[0] in Token.Name]

        for token_text in name_tokens:
            # Add as 'ref' kind, line number is unknown (-1)
            tag_instance = Tag(
                rel_fname=rel_fname,
                fname=fname,
                name=token_text,
                kind="ref",
                line=-1, # Line number unavailable from this method
            )
            results.append(tag_instance)

    except Exception as e:
        # Pygments can sometimes fail
        if verbose:
             console.print(f"[yellow]Pygments fallback failed for {fname}: {e}[/yellow]")

    return results

def display_file_structure(file_path: str, elements: List, detector, verbose: bool = False):
    """Display the file structure as a rich tree.
    
    Args:
        file_path: Path to the file
        elements: List of ExtendedTag objects 
        detector: The ElementDetector instance used to get display configuration
        verbose: Whether to print verbose information
    """
    # 创建结果树
    result_tree = Tree(f"[bold blue]{escape(file_path)}[/bold blue]")

    # Group elements by type
    elements_by_type = {elem_type: [] for elem_type in detector.element_types}
    
    for elem in elements:
        # Convert 0-indexed to 1-indexed for display
        start_line = elem.line + 1
        end_line = elem.end_line + 1
        line_range = f"(Lines: {start_line}-{end_line})" if start_line != end_line else f"(Line: {start_line})"
        
        type_info = elem.type_info
        if type_info in elements_by_type:
            elements_by_type[type_info].append((elem.name, line_range))
    
    # Add elements to the tree
    has_elements = False
    
    # Get display configuration from detector
    type_display = detector.type_display_config
    
    # Add each type to the tree in the specified order
    for elem_type in detector.display_order:
        if elem_type in elements_by_type and elements_by_type[elem_type]:
            has_elements = True
            display_info = type_display[elem_type]
            type_node = result_tree.add(f"[bold {display_info['color']}]{display_info['title']}[/bold {display_info['color']}]")
            
            # Sort elements by name within each category
            for name, line_range in sorted(elements_by_type[elem_type]):
                type_node.add(f"[{display_info['color']}]{name}[/{display_info['color']}] {line_range}")
    
    if not has_elements:
        # If no elements were found
        result_tree.add("[italic]未找到定义[/italic]")

    # 输出结果
    console.print(result_tree) 