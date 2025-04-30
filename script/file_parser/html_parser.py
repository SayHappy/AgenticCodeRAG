#!/usr/bin/env python3
"""
HTML language parser implementation.
Supports HTML files (.html, .htm).
"""
from pathlib import Path
from collections import namedtuple
from typing import List, Dict, Any
import re # Import re

from .base_parser import ElementDetector, LanguageParser, BaseExtendedTag, ParserRegistry
from .common_utils import console

# Limit for number of elements returned
MAX_ELEMENTS = 200

# Create an HTML-specific extended tag
HtmlExtendedTag = namedtuple("HtmlExtendedTag", BaseExtendedTag._fields)

class HtmlElementDetector(ElementDetector):
    """HTML-specific element detector"""

    @property
    def element_types(self) -> List[str]:
        return [
            "element",
            "script",
            "style",
            "unknown"
        ]

    @property
    def type_display_config(self) -> Dict[str, Dict[str, str]]:
        return {
            "element": {"title": "HTML Elements", "color": "green"},
            "script": {"title": "Scripts", "color": "cyan"},
            "style": {"title": "Styles", "color": "bright_magenta"},
            "unknown": {"title": "Other Elements", "color": "white"}
        }

    @property
    def display_order(self) -> List[str]:
        return [
            "element",
            "script",
            "style",
            "unknown"
        ]

    def detect_elements(self, file_path: str, verbose: bool = False) -> List[HtmlExtendedTag]:
        """Detect HTML-specific elements in the given file"""
        try:
            code = Path(file_path).read_text(encoding='utf-8', errors='replace')
            lines = code.splitlines()
            results = []
            self._process_html_file(file_path, lines, results, verbose)
            return results
        except Exception as e:
            if verbose:
                console.print(f"[red]HTML element detection error for {file_path}: {e}[/red]")
            return []

    def _process_html_file(self, file_path: str, lines: List[str], results: List[HtmlExtendedTag], verbose: bool = False):
        """Process HTML files (Adapted from FrontendElementDetector)"""
        # Track elements, scripts, and styles
        elements = []
        scripts = []
        styles = []

        i = 0
        tag_stack = [] # Stack to keep track of (tag_name, start_line)

        while i < len(lines):
            line = lines[i].strip()
            line_lower = line.lower() # For case-insensitive matching

            # Skip empty lines and comments
            # Basic comment handling, might not catch multi-line comments perfectly if not started/ended on same line
            if not line or line.startswith("<!--"):
                # Handle multi-line comments roughly
                if line.startswith("<!--") and "-->" not in line:
                    while i < len(lines) and "-->" not in lines[i]:
                        i += 1
                i += 1
                continue

            # Simple regex to find opening tags (more robust than simple < check)
            # Handles <tag>, <tag attr="val">, ignores </tag>
            # NOTE: This simplified regex just finds the tag name start, 
            # allowing multi-line tags but attribute capture relies on later logic.
            opening_tags = re.findall(r'<([a-zA-Z0-9\-]+)', line) # Find <tagname start
            for tag_name in opening_tags:
                 tag_lower = tag_name.lower()
                 # Track all tags as potential elements - don't limit to specific structural tags
                 tag_stack.append((tag_lower, i))

            # Simple regex to find closing tags
            closing_tags = re.findall(r'</([a-zA-Z0-9\-]+)>', line)
            for close_tag in closing_tags:
                close_tag_lower = close_tag.lower()
                # Find matching opening tag in the stack
                matching_tag_index = -1
                for idx, (tag, _) in enumerate(reversed(tag_stack)):
                    if tag == close_tag_lower:
                        matching_tag_index = len(tag_stack) - 1 - idx
                        break
                
                if matching_tag_index >= 0:
                    tag_type, start_line = tag_stack.pop(matching_tag_index)
                    end_line = i

                    # Extract content from the starting line for better naming
                    start_line_content = lines[start_line].strip()
                    element_name = f"<{tag_type}>"

                    # Process based on tag type
                    if tag_type == "script":
                        # Try to find src attribute
                        src_match = re.search(r'src\s*=\s*["\']?([^"\' >]+)["\']?', start_line_content, re.IGNORECASE)
                        if src_match:
                            element_name = f'<script src="{src_match.group(1)}">'
                        else:
                            element_name = f"<script> (inline)"
                        scripts.append({"name": element_name, "start": start_line, "end": end_line})
                    elif tag_type == "style":
                        element_name = f"<style>"
                        styles.append({"name": element_name, "start": start_line, "end": end_line})
                    else:
                        # Check for id or class in the opening tag line
                        id_match = re.search(r'id\s*=\s*["\']?([^"\' >]+)["\']?', start_line_content, re.IGNORECASE)
                        class_match = re.search(r'class\s*=\s*["\']?([^"\' >]+)["\']?', start_line_content, re.IGNORECASE)

                        attrs = []
                        if id_match:
                            attrs.append(f'id="{id_match.group(1)}"')
                        if class_match:
                            # Limit displayed classes if too many
                            class_list = class_match.group(1).split()
                            display_classes = " ".join(class_list[:3])
                            if len(class_list) > 3:
                                display_classes += "..."
                            attrs.append(f'class="{display_classes}"')

                        if attrs:
                            element_name = f"<{tag_type} {' '.join(attrs)}>"
                        else:
                             element_name = f"<{tag_type}>"

                        # For buttons, try to add text content if available and short
                        if tag_type == "button" and end_line >= start_line:
                            # Extract text content, cleaning whitespace and handling multi-line
                            content_lines = lines[start_line+1:end_line] # Get lines between tags
                            # Get content from start/end lines if tag isn't alone
                            start_tag_end = start_line_content.find('>') + 1
                            end_tag_start = lines[end_line].strip().find('</')
                            
                            full_content = ""
                            if end_line == start_line: # Tag on single line <button>text</button>
                               if end_tag_start > start_tag_end:
                                   full_content = start_line_content[start_tag_end:end_tag_start].strip()
                            else:
                                first_line_content = start_line_content[start_tag_end:].strip()
                                last_line_content = lines[end_line].strip()[:end_tag_start].strip()
                                middle_content = " ".join(l.strip() for l in content_lines)
                                full_content = f"{first_line_content} {middle_content} {last_line_content}".strip()
                                full_content = re.sub(r'\s+', ' ', full_content) # Consolidate whitespace

                            # Limit length and avoid overly complex template strings
                            if 0 < len(full_content) <= 50 and '{{' not in full_content and '{%' not in full_content:
                                element_name += f' "{full_content}"'
                            elif 0 < len(full_content):
                                 element_name += f' "{full_content[:47]}..."'

                        elements.append({"name": element_name, "start": start_line, "end": end_line})

            i += 1

        # Add self-closing tags that weren't caught by the closing tag logic
        self_closing_tags = []
        for i, line in enumerate(lines):
            # Find self-closing tags like <tag /> or <tag/>
            self_closing_matches = re.findall(r'<([a-zA-Z0-9\-]+)[^>]*?/>', line)
            for tag_name in self_closing_matches:
                tag_lower = tag_name.lower()
                element_name = f"<{tag_lower}/>"
                
                # Check for id or class in the tag
                id_match = re.search(f'<{tag_name}[^>]*?id\s*=\s*["\']?([^"\' >]+)["\']?', line, re.IGNORECASE)
                class_match = re.search(f'<{tag_name}[^>]*?class\s*=\s*["\']?([^"\' >]+)["\']?', line, re.IGNORECASE)
                
                attrs = []
                if id_match:
                    attrs.append(f'id="{id_match.group(1)}"')
                if class_match:
                    class_list = class_match.group(1).split()
                    display_classes = " ".join(class_list[:3])
                    if len(class_list) > 3:
                        display_classes += "..."
                    attrs.append(f'class="{display_classes}"')
                
                if attrs:
                    element_name = f"<{tag_lower} {' '.join(attrs)}/>"
                
                self_closing_tags.append({"name": element_name, "start": i, "end": i})

        # Define tags to exclude from the main element list
        excluded_tags = {"p", "span"}

        # Create result elements
        rel_fname = Path(file_path).name
        for elem in elements:
            # Extract base tag name for filtering
            tag_match = re.match(r'<([a-zA-Z0-9\-]+)', elem["name"])
            if tag_match and tag_match.group(1).lower() in excluded_tags:
                continue # Skip excluded tags

            results.append(HtmlExtendedTag(
                rel_fname=rel_fname, fname=file_path,
                line=elem["start"], end_line=elem["end"],
                name=elem["name"], kind="def", type_info="element"
            ))
        for script in scripts:
            results.append(HtmlExtendedTag(
                rel_fname=rel_fname, fname=file_path,
                line=script["start"], end_line=script["end"],
                name=script["name"], kind="def", type_info="script"
            ))
        for style in styles:
            results.append(HtmlExtendedTag(
                rel_fname=rel_fname, fname=file_path,
                line=style["start"], end_line=style["end"],
                name=style["name"], kind="def", type_info="style"
            ))
        for tag in self_closing_tags:
            results.append(HtmlExtendedTag(
                rel_fname=rel_fname, fname=file_path,
                line=tag["start"], end_line=tag["end"],
                name=tag["name"], kind="def", type_info="element"
            ))

        # Sort results by starting line number (optional but good practice)
        results.sort(key=lambda x: x.line)

        # Store original count before truncation
        original_count = len(results)

        # Apply truncation
        if original_count > MAX_ELEMENTS:
            last_kept_element = results[MAX_ELEMENTS - 1]
            results = results[:MAX_ELEMENTS]
            results.append(HtmlExtendedTag(
                rel_fname=rel_fname, fname=file_path,
                line=last_kept_element.end_line, end_line=last_kept_element.end_line,
                name=f"[... Truncated - {MAX_ELEMENTS}/{original_count} elements shown ...]",
                kind="misc", type_info="marker"
            ))
            
        return results # Return potentially truncated results

class HtmlParser(LanguageParser):
    """HTML language parser factory"""

    def create_element_detector(self) -> HtmlElementDetector:
        """Create an HTML-specific element detector"""
        return HtmlElementDetector()

    def get_file_extensions(self) -> List[str]:
        """Get the list of file extensions supported by this parser"""
        return [".html", ".htm", ".xhsml", ".xhtm", ".xhtml"]

    def get_language_name(self) -> str:
        """Get the name of the language supported by this parser"""
        return "html"

# Register the parser
ParserRegistry.register(HtmlParser()) 