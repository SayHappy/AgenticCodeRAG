#!/usr/bin/env python3
"""
Markdown language parser implementation.
Supports Markdown files (.md).
"""
from pathlib import Path
from collections import namedtuple
from typing import List, Dict
import re
from markitdown import MarkItDown

from .base_parser import ElementDetector, LanguageParser, BaseExtendedTag, ParserRegistry
from .common_utils import console

# Limit for number of elements returned
MAX_ELEMENTS = 200

# Create a Markdown-specific extended tag
MarkdownExtendedTag = namedtuple("MarkdownExtendedTag", BaseExtendedTag._fields + ("prefix_summary",))

class MarkdownElementDetector(ElementDetector):
    """Markdown-specific element detector"""

    @property
    def element_types(self) -> List[str]:
        # Define types like heading, code_block, paragraph, etc.
        return [
            "heading1",
            "heading2",
            "heading3",
            "code_block",
            "unknown"
        ]

    @property
    def type_display_config(self) -> Dict[str, Dict[str, str]]:
        # Define display styles for elements
        return {
            "heading1": {"title": "Primary Headings", "color": "bold blue"},
            "heading2": {"title": "Secondary Headings", "color": "blue"},
            "heading3": {"title": "Tertiary Headings", "color": "cyan"},
            "code_block": {"title": "Code Blocks", "color": "cyan"},
            "unknown": {"title": "Other", "color": "dim"}
        }

    @property
    def display_order(self) -> List[str]:
        # Define the order in which elements are displayed
        return [
            "heading1",
            "heading2",
            "heading3",
            "code_block",
            "unknown"
        ]

    def detect_elements(self, file_path: str, verbose: bool = False) -> List[MarkdownExtendedTag]:
        """Detect Markdown elements in the given file"""
        try:
            md = MarkItDown(enable_plugins=False)
            code = md.convert(file_path).text_content
            lines = code.splitlines()
            # Extract prefix summary (first 300 characters)
            prefix_summary = code[:400] + "..." if len(code) > 400 else code
            prefix_summary = prefix_summary.replace('\n', ' ')      
            results = []
            
            # Add prefix summary as a special element at the beginning
            results.append(MarkdownExtendedTag(
                rel_fname=Path(file_path).name, fname=file_path,
                line=0, end_line=0,
                name=f"Prefix: {prefix_summary}",
                kind="def", type_info="heading1", 
                prefix_summary=prefix_summary
            ))
            
            self._process_markdown_file(file_path, lines, results, prefix_summary, verbose)
            
            # Sort results by starting line number, but keep prefix_summary at the top
            first_element = results[0]  # Save the prefix_summary element
            results = results[1:]  # Remove it from the list
            results.sort(key=lambda x: x.line)  # Sort the rest
            results.insert(0, first_element)  # Put prefix_summary back at the top

            # Apply truncation if needed (similar to HtmlParser)
            original_count = len(results)
            if original_count > MAX_ELEMENTS:
                last_kept_element = results[MAX_ELEMENTS - 1]
                results = results[:MAX_ELEMENTS]
                results.append(MarkdownExtendedTag(
                    rel_fname=Path(file_path).name, fname=file_path,
                    line=last_kept_element.end_line, end_line=last_kept_element.end_line,
                    name=f"[... Truncated - {MAX_ELEMENTS}/{original_count} elements shown ...]",
                    kind="misc", type_info="marker", prefix_summary=prefix_summary
                ))
            return results
        except Exception as e:
            if verbose:
                console.print(f"[red]Markdown element detection error for {file_path}: {e}[/red]")
            return []

    def _process_markdown_file(self, file_path: str, lines: List[str], results: List[MarkdownExtendedTag], prefix_summary: str, verbose: bool = False):
        """Process the Markdown file lines to find headings and code blocks."""
        rel_fname = Path(file_path).name
        i = 0
        in_code_block = False
        code_block_start = -1
        code_block_lang = ""
        current_code_block_content = []
        heading1_level = None
        heading2_level = None # Will be set relative to heading1_level
        heading3_level = None # Will be set relative to heading2_level

        while i < len(lines):
            line = lines[i]
            stripped_line = line.strip()

            # Detect code block start/end
            if stripped_line.startswith("```"):
                if not in_code_block:
                    in_code_block = True
                    code_block_start = i
                    code_block_lang = stripped_line[3:].strip()
                    current_code_block_content = []
                    i += 1
                    continue
                else:
                    # End of code block
                    in_code_block = False
                    element_base_name = f"Code Block ({code_block_lang})" if code_block_lang else "Code Block"
                    full_content = "\\n".join(current_code_block_content).strip()
                    summary = full_content[:150]
                    if len(full_content) > 150:
                        summary += "..."
                    element_name = f"{element_base_name}: {summary}" if summary else element_base_name

                    results.append(MarkdownExtendedTag(
                        rel_fname=rel_fname, fname=file_path,
                        line=code_block_start, end_line=i,
                        name=element_name, kind="def", type_info="code_block", 
                        prefix_summary=prefix_summary
                    ))
                    i += 1
                    continue

            # Store content if inside code block
            if in_code_block:
                current_code_block_content.append(line)
                i += 1
                continue

            # Detect Headings dynamically
            heading_match = re.match(r"^\s*(#+)\s+(.+)", line)

            if heading_match:
                level = len(heading_match.group(1))
                heading_text = heading_match.group(2).strip()
                tag_name = f"H{level}: {heading_text}"
                tag_type = "unknown" # Default

                if heading1_level is None:
                    heading1_level = level
                    heading2_level = level + 1 # Define H2 relative to the first H1
                    heading3_level = level + 2 # Define H3 relative to the first H1
                    tag_type = "heading1"
                elif level == heading1_level:
                    tag_type = "heading1"
                elif level == heading2_level:
                    tag_type = "heading2"
                elif level == heading3_level:
                    tag_type = "heading3"

                if tag_type != "unknown": # Only add if it matches H1, H2, or H3 levels
                    results.append(MarkdownExtendedTag(
                        rel_fname=rel_fname, fname=file_path,
                        line=i, end_line=i,
                        name=tag_name, kind="def", type_info=tag_type,
                        prefix_summary=prefix_summary
                    ))
            
            # Skip paragraph detection - we're not including paragraphs anymore
            
            i += 1

        # Handle unterminated code block at EOF
        if in_code_block:
             element_base_name = f"Code Block ({code_block_lang})" if code_block_lang else "Code Block"
             # Generate summary for unterminated block
             full_content = "\\n".join(current_code_block_content).strip()
             summary = full_content[:100]
             if len(full_content) > 100:
                 summary += "..."
             
             element_name = f"{element_base_name} (unterminated): {summary}" if summary else f"{element_base_name} (unterminated)"

             results.append(MarkdownExtendedTag(
                 rel_fname=rel_fname, fname=file_path,
                 line=code_block_start, end_line=len(lines) - 1,
                 name=element_name, kind="def", type_info="code_block",
                 prefix_summary=prefix_summary
             ))

class MarkdownParser(LanguageParser):
    """Markdown language parser factory"""

    def create_element_detector(self) -> MarkdownElementDetector:
        """Create a Markdown-specific element detector"""
        return MarkdownElementDetector()

    def get_file_extensions(self) -> List[str]:
        """Get the list of file extensions supported by this parser"""
        return [".md", ".markdown", ".mdown", ".mkd", ".mkdn", ".mdwn", ".mdtxt", ".mdtext", ".text", ".txt", ".pdf", ".docx", ".pptx", ".xlsx", ".xls", ".msg", ".eml"]

    def get_language_name(self) -> str:
        """Get the name of the language supported by this parser"""
        return "markdown"

# Register the parser
ParserRegistry.register(MarkdownParser()) 
