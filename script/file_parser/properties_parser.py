#!/usr/bin/env python3
"""
Java Properties file parser implementation.
Supports .properties files.
"""
from pathlib import Path
from collections import namedtuple
from typing import List, Dict, Any
import re

from .base_parser import ElementDetector, LanguageParser, BaseExtendedTag, ParserRegistry
from .common_utils import console

# Limit for number of elements returned
MAX_ELEMENTS = 200

# Create a Properties-specific extended tag
PropertiesExtendedTag = namedtuple("PropertiesExtendedTag", BaseExtendedTag._fields)

class PropertiesElementDetector(ElementDetector):
    """Properties file specific element detector"""

    @property
    def element_types(self) -> List[str]:
        # Define element types (e.g., key, comment, unknown)
        return ["key", "comment", "unknown"]

    @property
    def type_display_config(self) -> Dict[str, Dict[str, str]]:
        # Configure display for properties types
        return {
            "key": {"title": "Properties", "color": "cyan"},
            "comment": {"title": "Comments", "color": "grey"},
            "unknown": {"title": "Other Lines", "color": "white"}
        }

    @property
    def display_order(self) -> List[str]:
        # Define display order
        return ["key", "comment", "unknown"]

    def detect_elements(self, file_path: str, verbose: bool = False) -> List[PropertiesExtendedTag]:
        """Detect elements (keys, comments) in the given properties file"""
        results = []
        rel_fname = Path(file_path).name
        try:
            lines = Path(file_path).read_text(encoding='utf-8', errors='replace').splitlines()
            
            for i, line in enumerate(lines):
                stripped_line = line.strip()
                line_num = i # 0-indexed
                type_info = "unknown"
                kind = "misc"
                element_name = stripped_line

                if not stripped_line:
                    continue # Skip empty lines

                # Check for comments
                if stripped_line.startswith('#') or stripped_line.startswith('!'):
                    type_info = "comment"
                    kind = "comment"
                    element_name = stripped_line
                else:
                    # Check for key-value pairs (allow for =, :, or whitespace separators)
                    # Handle potential continuation lines later if needed (more complex)
                    match = re.match(r'^\s*([^\s:=]+)\s*[:=\s]\s*(.*)', line)
                    if match:
                        key = match.group(1).strip()
                        value = match.group(2).strip()
                        type_info = "key"
                        kind = "def"
                        # Truncate long values for display
                        display_value = value[:50] + "..." if len(value) > 50 else value
                        element_name = f"{key} = {display_value}"
                    else:
                        # Treat lines without clear key-value structure as unknown
                        type_info = "unknown"
                        kind = "misc"
                        element_name = stripped_line[:80] # Limit length

                results.append(PropertiesExtendedTag(
                    rel_fname=rel_fname, fname=file_path,
                    line=line_num, end_line=line_num,
                    name=element_name, kind=kind, type_info=type_info
                ))

            # Sort results by starting line number (optional but good practice)
            results.sort(key=lambda x: x.line)

            # Store original count before truncation
            original_count = len(results)

            # Apply truncation
            if original_count > MAX_ELEMENTS:
                last_kept_element = results[MAX_ELEMENTS - 1]
                results = results[:MAX_ELEMENTS]
                results.append(PropertiesExtendedTag(
                    rel_fname=rel_fname, fname=file_path,
                    line=last_kept_element.end_line, end_line=last_kept_element.end_line,
                    name=f"[... Truncated - {MAX_ELEMENTS}/{original_count} elements shown ...]",
                    kind="misc", type_info="marker"
                ))
                
            return results # Return potentially truncated results
        except Exception as e:
            if verbose:
                console.print(f"[red]Properties file parsing error for {file_path}: {e}[/red]")
            # Add a placeholder if reading/processing fails
            results.append(PropertiesExtendedTag(
                 rel_fname=rel_fname, fname=file_path,
                 line=0, end_line=0, name="[Processing Error]", kind="err", type_info="unknown"
             ))
            return results

class PropertiesParser(LanguageParser):
    """Properties file language parser factory"""

    def create_element_detector(self) -> PropertiesElementDetector:
        """Create a Properties-specific element detector"""
        return PropertiesElementDetector()

    def get_file_extensions(self) -> List[str]:
        """Get the list of file extensions supported by this parser"""
        return [".properties"]

    def get_language_name(self) -> str:
        """Get the name of the language supported by this parser"""
        return "properties"

# Register the parser
ParserRegistry.register(PropertiesParser()) 