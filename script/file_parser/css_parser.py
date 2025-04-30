#!/usr/bin/env python3
"""
CSS language parser implementation.
Supports CSS files (.css).
"""
from pathlib import Path
from collections import namedtuple
from typing import List, Dict, Any
import re

from .base_parser import ElementDetector, LanguageParser, BaseExtendedTag, ParserRegistry
from .common_utils import console

# Create a CSS-specific extended tag
CssExtendedTag = namedtuple("CssExtendedTag", BaseExtendedTag._fields)

# Limit for number of elements returned
MAX_ELEMENTS = 200

class CssElementDetector(ElementDetector):
    """CSS-specific element detector"""

    @property
    def element_types(self) -> List[str]:
        # Define element types (e.g., selector, rule, comment, at-rule)
        return ["selector", "at-rule", "comment", "unknown"]

    @property
    def type_display_config(self) -> Dict[str, Dict[str, str]]:
        # Configure display for CSS types
        return {
            "selector": {"title": "Selectors", "color": "blue"},
            "at-rule": {"title": "At-Rules", "color": "magenta"},
            "comment": {"title": "Comments", "color": "grey"},
            "unknown": {"title": "Other Content", "color": "white"}
        }

    @property
    def display_order(self) -> List[str]:
        # Define display order
        return ["selector", "at-rule", "comment", "unknown"]

    def detect_elements(self, file_path: str, verbose: bool = False) -> List[CssExtendedTag]:
        """Detect CSS elements (selectors, rules, comments) in the given file"""
        results = []
        rel_fname = Path(file_path).name
        try:
            code = Path(file_path).read_text(encoding='utf-8', errors='replace')
            lines = code.splitlines()
            
            # Simple regex patterns
            # Note: These are basic and won't handle all complex CSS syntax perfectly
            comment_pattern = re.compile(r'/\\*.*?\\*/', re.DOTALL) # Multi-line comments
            selector_pattern = re.compile(r'([^{}/]+){[^{}]*?}', re.DOTALL) # Selectors and their blocks
            at_rule_pattern = re.compile(r'(@[a-zA-Z\\-]+)[^;{]*?(?:;|{[^{}]*?})', re.DOTALL) # Basic @-rules

            # Find comments first and store their ranges to ignore later
            comment_ranges = [(m.start(), m.end()) for m in comment_pattern.finditer(code)]

            def is_in_comment(index):
                for start, end in comment_ranges:
                    if start <= index < end:
                        return True
                return False
            
            # Find @-rules
            for match in at_rule_pattern.finditer(code):
                if not is_in_comment(match.start()):
                    start_line = code.count('\n', 0, match.start())
                    end_line = code.count('\n', 0, match.end())
                    rule_name = match.group(1)
                    results.append(CssExtendedTag(
                        rel_fname=rel_fname, fname=file_path,
                        line=start_line, end_line=end_line,
                        name=f"{rule_name} ...", kind="def", type_info="at-rule"
                    ))

            # Find selectors
            # Adjust finditer start position to avoid re-matching inside processed @-rules? (complex)
            for match in selector_pattern.finditer(code):
                if not is_in_comment(match.start()):
                    # Rough check if it's inside an already matched @-rule block (basic)
                    selector_part = match.group(1).strip()
                    if selector_part.startswith('@'): # Likely part of an @-rule, handled above
                        continue
                    
                    start_line = code.count('\n', 0, match.start())
                    end_line = code.count('\n', 0, match.end())
                    # Clean up selector name for display
                    selector_name = ' '.join(selector_part.split()) # Normalize whitespace
                    if len(selector_name) > 80:
                        selector_name = selector_name[:77] + "..."
                    
                    results.append(CssExtendedTag(
                        rel_fname=rel_fname, fname=file_path,
                        line=start_line, end_line=end_line,
                        name=f"{selector_name} {{...}}", kind="def", type_info="selector"
                    ))

            # Add comments separately (might overlap with lines of other rules)
            for match in comment_pattern.finditer(code):
                start_line = code.count('\n', 0, match.start())
                end_line = code.count('\n', 0, match.end())
                comment_text = match.group(0)[:80] # Truncate long comments
                if len(match.group(0)) > 80:
                    comment_text += "... */"
                results.append(CssExtendedTag(
                    rel_fname=rel_fname, fname=file_path,
                    line=start_line, end_line=end_line,
                    name=comment_text, kind="comment", type_info="comment"
                ))
            
            # Sort results by starting line number
            results.sort(key=lambda x: x.line)

            # Store original count before truncation
            original_count = len(results)

            # Apply truncation
            if original_count > MAX_ELEMENTS:
                last_kept_element = results[MAX_ELEMENTS - 1]
                results = results[:MAX_ELEMENTS]
                results.append(CssExtendedTag(
                    rel_fname=rel_fname, fname=file_path,
                    line=last_kept_element.end_line, end_line=last_kept_element.end_line,
                    # Corrected placeholder message without unnecessary escapes
                    name=f"[... Truncated - {MAX_ELEMENTS}/{original_count} elements shown ...]",
                    kind="misc", type_info="marker"
                ))

            return results
        except Exception as e:
            if verbose:
                console.print(f"[red]CSS parsing error for {file_path}: {e}[/red]")
            # Add a placeholder if reading/processing fails
            results.append(CssExtendedTag(
                rel_fname=rel_fname, fname=file_path,
                line=0, end_line=0, name="[Processing Error]", kind="err", type_info="unknown"
            ))
            return results

class CssParser(LanguageParser):
    """CSS language parser factory"""

    def create_element_detector(self) -> CssElementDetector:
        """Create a CSS-specific element detector"""
        return CssElementDetector()

    def get_file_extensions(self) -> List[str]:
        """Get the list of file extensions supported by this parser"""
        return [".css"]

    def get_language_name(self) -> str:
        """Get the name of the language supported by this parser"""
        return "css"

# Register the parser
ParserRegistry.register(CssParser()) 