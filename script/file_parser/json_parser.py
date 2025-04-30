#!/usr/bin/env python3
"""
JSON language parser implementation.
Supports JSON files (.json).
"""
import json
from pathlib import Path
from collections import namedtuple
from typing import List, Dict, Any, Tuple

from .base_parser import ElementDetector, LanguageParser, BaseExtendedTag, ParserRegistry
from .common_utils import console

# Limit for number of elements returned
MAX_ELEMENTS = 200

# Create a JSON-specific extended tag
JsonExtendedTag = namedtuple("JsonExtendedTag", BaseExtendedTag._fields)

class JsonElementDetector(ElementDetector):
    """JSON-specific element detector"""

    @property
    def element_types(self) -> List[str]:
        # Define element types for JSON (e.g., key, string, number, boolean, array, object)
        return ["key", "string", "number", "boolean", "array", "object", "unknown"]

    @property
    def type_display_config(self) -> Dict[str, Dict[str, str]]:
        # Configure display for JSON element types
        return {
            "key": {"title": "Keys", "color": "cyan"},
            "string": {"title": "Strings", "color": "green"},
            "number": {"title": "Numbers", "color": "magenta"},
            "boolean": {"title": "Booleans", "color": "yellow"},
            "array": {"title": "Arrays", "color": "blue"},
            "object": {"title": "Objects", "color": "bright_blue"},
            "unknown": {"title": "Other Content", "color": "white"}
        }

    @property
    def display_order(self) -> List[str]:
        # Define display order
        return ["key", "object", "array", "string", "number", "boolean", "unknown"]

    def detect_elements(self, file_path: str, verbose: bool = False) -> List[JsonExtendedTag]:
        """Detect JSON elements (keys, structures) in the given file"""
        results = []
        try:
            code = Path(file_path).read_text(encoding='utf-8', errors='replace')
            # Attempt to parse JSON first to check validity
            try:
                json_data = json.loads(code)
            except json.JSONDecodeError as e:
                if verbose:
                    console.print(f"[red]JSON parsing error in {file_path}: {e}[/red]")
                # Add a placeholder for parse errors
                results.append(JsonExtendedTag(
                    rel_fname=Path(file_path).name, fname=file_path,
                    line=e.lineno - 1, end_line=e.lineno - 1, # Use error line info
                    name=f"[Parse Error: {e.msg}]", kind="err", type_info="unknown"
                ))
                return results

            lines = code.splitlines()
            rel_fname = Path(file_path).name

            # Use a recursive function to traverse the JSON structure and find line numbers
            self._find_json_elements(json_data, lines, file_path, rel_fname, results)

            # Sort results by starting line number (optional but good practice)
            results.sort(key=lambda x: x.line)

            # Store original count before truncation
            original_count = len(results)
            
            # Apply truncation
            if original_count > MAX_ELEMENTS:
                last_kept_element = results[MAX_ELEMENTS - 1]
                results = results[:MAX_ELEMENTS]
                results.append(JsonExtendedTag(
                    rel_fname=rel_fname, fname=file_path,
                    line=last_kept_element.end_line, end_line=last_kept_element.end_line,
                    name=f"[... Truncated - {MAX_ELEMENTS}/{original_count} elements shown ...]",
                    kind="misc", type_info="marker"
                ))
                
            return results # Return potentially truncated results
        except Exception as e:
            if verbose:
                console.print(f"[red]JSON element detection error for {file_path}: {e}[/red]")
            return []

    def _find_json_elements(self, data: Any, lines: List[str], file_path: str, rel_fname: str, results: List[JsonExtendedTag], current_path: str = "root"):
        """Recursive helper to find elements and approximate their lines."""
        if isinstance(data, dict):
            # Find line number for the opening brace '{'
            start_line, end_line = self._find_structure_lines(data, lines)
            results.append(JsonExtendedTag(
                rel_fname=rel_fname, fname=file_path, line=start_line, end_line=end_line,
                name=f"{current_path} {{...}}", kind="struct", type_info="object"
            ))
            for key, value in data.items():
                key_line = self._find_key_line(key, lines, start_line, end_line)
                results.append(JsonExtendedTag(
                    rel_fname=rel_fname, fname=file_path, line=key_line, end_line=key_line,
                    name=f'"{key}" :', kind="key", type_info="key"
                ))
                self._find_json_elements(value, lines, file_path, rel_fname, results, current_path=f"{current_path}.{key}")
        elif isinstance(data, list):
            start_line, end_line = self._find_structure_lines(data, lines)
            results.append(JsonExtendedTag(
                rel_fname=rel_fname, fname=file_path, line=start_line, end_line=end_line,
                name=f"{current_path} [...]", kind="struct", type_info="array"
            ))
            for index, item in enumerate(data):
                 self._find_json_elements(item, lines, file_path, rel_fname, results, current_path=f"{current_path}[{index}]")
        else:
             # For primitive types, find the line where they appear
             value_line = self._find_value_line(data, lines)
             type_info = "unknown"
             kind = "literal"
             if isinstance(data, str):
                 type_info = "string"
             elif isinstance(data, (int, float)):
                 type_info = "number"
             elif isinstance(data, bool):
                 type_info = "boolean"

             # Truncate long strings for display name
             display_value = str(data)
             if len(display_value) > 50:
                 display_value = display_value[:47] + "..."

             results.append(JsonExtendedTag(
                 rel_fname=rel_fname, fname=file_path, line=value_line, end_line=value_line,
                 name=repr(display_value), kind=kind, type_info=type_info
             ))

    def _find_key_line(self, key: str, lines: List[str], start_hint: int = 0, end_hint: int = -1) -> int:
        """Approximate line number for a JSON key."""
        search_key = json.dumps(key) # Get the representation with quotes
        if end_hint == -1:
            end_hint = len(lines)
        try:
            for i in range(start_hint, end_hint):
                if search_key + ":" in lines[i]: # Look for "key":
                    return i
        except IndexError:
             pass # Should not happen if hints are correct
        return start_hint # Fallback

    def _find_value_line(self, value: Any, lines: List[str], start_hint: int = 0) -> int:
        """Approximate line number for a JSON primitive value."""
        search_value = json.dumps(value)
        try:
            for i in range(start_hint, len(lines)):
                 # Simple check, might match comments or substrings incorrectly
                 if search_value in lines[i]:
                     # Try to avoid matching inside keys like "true_key": false
                     if not (lines[i].strip().startswith("\"") and ":" in lines[i]):
                        return i
        except IndexError:
            pass
        return start_hint # Fallback

    def _find_structure_lines(self, structure: Any, lines: List[str]) -> Tuple[int, int]:
         """Approximate start and end lines for JSON objects/arrays (very basic)."""
         # This is highly approximate and doesn't handle nesting well
         # It relies on finding the first { or [ and the corresponding last } or ]
         # A proper parser would be needed for accuracy
         start_char = '{' if isinstance(structure, dict) else '['
         end_char = '}' if isinstance(structure, dict) else ']'
         start_line = 0
         end_line = len(lines) - 1
         level = 0
         found_start = False

         try:
             for i, line in enumerate(lines):
                 stripped_line = line.strip()
                 if not found_start:
                     if stripped_line.startswith(start_char) or stripped_line.endswith(start_char):
                          start_line = i
                          found_start = True
                 if found_start:
                     level += line.count(start_char)
                     level -= line.count(end_char)
                     if level <= 0 and end_char in line: # Very rough check for the end
                         end_line = i
                         break # Assume first closing match is the end for this simple check
         except IndexError:
            pass

         return start_line, max(start_line, end_line) # Ensure end_line is not before start_line

class JsonParser(LanguageParser):
    """JSON language parser factory"""

    def create_element_detector(self) -> JsonElementDetector:
        """Create a JSON-specific element detector"""
        return JsonElementDetector()

    def get_file_extensions(self) -> List[str]:
        """Get the list of file extensions supported by this parser"""
        return [".json", ".jsonl", ".geojson"]

    def get_language_name(self) -> str:
        """Get the name of the language supported by this parser"""
        return "json"

# Register the parser
ParserRegistry.register(JsonParser()) 