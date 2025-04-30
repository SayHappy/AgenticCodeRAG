#!/usr/bin/env python3
"""
YAML language parser implementation.
Supports YAML files (.yaml, .yml).
Requires PyYAML library.
"""
from pathlib import Path
from collections import namedtuple
from typing import List, Dict, Any, Tuple
import yaml # Import PyYAML

from .base_parser import ElementDetector, LanguageParser, BaseExtendedTag, ParserRegistry
from .common_utils import console

# Limit for number of elements returned
MAX_ELEMENTS = 200

# Create a YAML-specific extended tag
YamlExtendedTag = namedtuple("YamlExtendedTag", BaseExtendedTag._fields)

# Helper to get line numbers from PyYAML nodes
# Source: Adapted from suggestions in PyYAML issues/StackOverflow
def get_node_lines(node: yaml.Node) -> Tuple[int, int]:
    return node.start_mark.line, node.end_mark.line

class YamlElementDetector(ElementDetector):
    """YAML-specific element detector"""

    @property
    def element_types(self) -> List[str]:
        # Define element types for YAML (e.g., key, string, number, boolean, sequence, mapping)
        return ["key", "string", "number", "boolean", "sequence", "mapping", "anchor", "alias", "unknown"]

    @property
    def type_display_config(self) -> Dict[str, Dict[str, str]]:
        # Configure display for YAML element types
        return {
            "key": {"title": "Keys", "color": "cyan"},
            "string": {"title": "Strings", "color": "green"},
            "number": {"title": "Numbers", "color": "magenta"},
            "boolean": {"title": "Booleans", "color": "yellow"},
            "sequence": {"title": "Sequences (Lists)", "color": "blue"},
            "mapping": {"title": "Mappings (Dicts)", "color": "bright_blue"},
            "anchor": {"title": "Anchors", "color": "bright_yellow"},
            "alias": {"title": "Aliases", "color": "bright_cyan"},
            "unknown": {"title": "Other Content", "color": "white"}
        }

    @property
    def display_order(self) -> List[str]:
        # Define display order
        return ["key", "mapping", "sequence", "string", "number", "boolean", "anchor", "alias", "unknown"]

    def detect_elements(self, file_path: str, verbose: bool = False) -> List[YamlExtendedTag]:
        """Detect YAML elements (keys, structures) in the given file using PyYAML"""
        results = []
        try:
            code = Path(file_path).read_text(encoding='utf-8', errors='replace')
            rel_fname = Path(file_path).name

            # Use yaml.compose_all to get node structure with line numbers
            # Note: compose_all yields documents for multi-document files
            documents = list(yaml.compose_all(code))

            for doc_node in documents:
                if doc_node: # Check if the document node is not None
                    self._traverse_yaml_node(doc_node, file_path, rel_fname, results)

            # Sort results by starting line number (optional but good practice)
            results.sort(key=lambda x: x.line)
            
            # Store original count before truncation
            original_count = len(results)

            # Apply truncation
            if original_count > MAX_ELEMENTS:
                last_kept_element = results[MAX_ELEMENTS - 1]
                results = results[:MAX_ELEMENTS]
                results.append(YamlExtendedTag(
                    rel_fname=rel_fname, fname=file_path,
                    line=last_kept_element.end_line, end_line=last_kept_element.end_line,
                    name=f"[... Truncated - {MAX_ELEMENTS}/{original_count} elements shown ...]",
                    kind="misc", type_info="marker"
                ))
                
            return results # Return potentially truncated results
        except yaml.YAMLError as e:
            if verbose:
                console.print(f"[red]YAML parsing error in {file_path}: {e}[/red]")
            # Add placeholder for YAML errors
            line = e.problem_mark.line if hasattr(e, 'problem_mark') and e.problem_mark else 0
            results.append(YamlExtendedTag(
                rel_fname=Path(file_path).name, fname=file_path,
                line=line, end_line=line,
                name=f"[Parse Error: {e.problem}]", kind="err", type_info="unknown"
            ))
            return results
        except Exception as e:
            if verbose:
                console.print(f"[red]YAML element detection error for {file_path}: {e}[/red]")
            return []

    def _traverse_yaml_node(self, node: yaml.Node, file_path: str, rel_fname: str, results: List[YamlExtendedTag], current_path: str = "root"):
        """Recursive helper to traverse PyYAML nodes and create tags."""
        node_line, node_end_line = get_node_lines(node)
        display_name = ""
        kind = "literal"
        type_info = "unknown"

        if isinstance(node, yaml.ScalarNode):
            # Handle scalar values (strings, numbers, booleans)
            tag_uri = node.tag
            value = node.value
            if tag_uri == 'tag:yaml.org,2002:str':
                type_info = "string"
                display_name = repr(value[:50] + "..." if len(value) > 50 else value)
            elif tag_uri in ['tag:yaml.org,2002:int', 'tag:yaml.org,2002:float']:
                type_info = "number"
                display_name = str(value)
            elif tag_uri == 'tag:yaml.org,2002:bool':
                type_info = "boolean"
                display_name = str(value).lower()
            else:
                # Handle other scalar types if needed, e.g., null, timestamp
                display_name = f"{tag_uri} {value}"

            results.append(YamlExtendedTag(
                rel_fname=rel_fname, fname=file_path, line=node_line, end_line=node_end_line,
                name=display_name, kind=kind, type_info=type_info
            ))

        elif isinstance(node, yaml.MappingNode):
            # Handle mappings (dictionaries)
            type_info = "mapping"
            kind = "struct"
            display_name = f"{current_path} {{...}}"
            results.append(YamlExtendedTag(
                rel_fname=rel_fname, fname=file_path, line=node_line, end_line=node_end_line,
                name=display_name, kind=kind, type_info=type_info
            ))
            for key_node, value_node in node.value:
                key_line, key_end_line = get_node_lines(key_node)
                key_name = key_node.value # Assume keys are usually strings
                # Add the key itself
                results.append(YamlExtendedTag(
                     rel_fname=rel_fname, fname=file_path, line=key_line, end_line=key_end_line,
                     name=f'{key_name}:', kind="key", type_info="key"
                 ))
                # Traverse the value
                self._traverse_yaml_node(value_node, file_path, rel_fname, results, current_path=f"{current_path}.{key_name}")

        elif isinstance(node, yaml.SequenceNode):
            # Handle sequences (lists)
            type_info = "sequence"
            kind = "struct"
            display_name = f"{current_path} [...]"
            results.append(YamlExtendedTag(
                rel_fname=rel_fname, fname=file_path, line=node_line, end_line=node_end_line,
                name=display_name, kind=kind, type_info=type_info
            ))
            for index, item_node in enumerate(node.value):
                # Traverse the item
                self._traverse_yaml_node(item_node, file_path, rel_fname, results, current_path=f"{current_path}[{index}]")

        # Handle anchors and aliases if present
        if hasattr(node, 'anchor') and node.anchor:
             results.append(YamlExtendedTag(
                 rel_fname=rel_fname, fname=file_path, line=node_line, end_line=node_line, # Anchor definition line
                 name=f'&{node.anchor}', kind="anchor", type_info="anchor"
             ))
        # Note: Aliases (*anchor) are represented by AliasToken during scanning/parsing,
        # but compose resolves them. Accessing the AliasNode directly might require a different approach (e.g., custom constructor or loader)
        # We might not easily detect the exact line of the alias '*' itself here.

class YamlParser(LanguageParser):
    """YAML language parser factory"""

    def create_element_detector(self) -> YamlElementDetector:
        """Create a YAML-specific element detector"""
        return YamlElementDetector()

    def get_file_extensions(self) -> List[str]:
        """Get the list of file extensions supported by this parser"""
        return [".yaml", ".yml"]

    def get_language_name(self) -> str:
        """Get the name of the language supported by this parser"""
        return "yaml"

# Register the parser
# Make sure PyYAML is installed (`pip install PyYAML`)
try:
    import yaml
    ParserRegistry.register(YamlParser())
except ImportError:
    console.print("[yellow]PyYAML not found. YAML parser disabled. Install with: pip install PyYAML[/yellow]") 