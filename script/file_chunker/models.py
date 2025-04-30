#!/usr/bin/env python3
"""
Data models for the file chunker package.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Union, List

@dataclass
class Span:
    """Represents a slice of text using start and end points (byte or line)."""
    start: int
    end: int

    def extract(self, s: Union[str, bytes]) -> Union[str, bytes]:
        """Extracts the substring/subbytes corresponding to the span."""
        return s[self.start:self.end]

    def extract_lines(self, s: str) -> str:
        """Extracts lines from a string based on 0-indexed line numbers."""
        lines = s.splitlines()
        # Ensure start and end are within bounds
        start_line = max(0, self.start)
        end_line = min(len(lines), self.end)
        return "\n".join(lines[start_line:end_line])

    def __add__(self, other: Union['Span', int]) -> 'Span':
        """
        Adds two spans or shifts a span by an integer.
        Span(a, b) + Span(c, d) = Span(a, d) (Concatenation, assumes b approx c)
        Span(a, b) + int = Span(a + int, b + int) (Shift)
        """
        if isinstance(other, int):
            return Span(self.start + other, self.end + other)
        elif isinstance(other, Span):
            # Concatenate: assumes spans are contiguous or overlapping for simplification
            # Takes the start of the first and end of the second.
            return Span(self.start, other.end)
        else:
            raise NotImplementedError(f"Cannot add Span and {type(other)}")

    def __len__(self) -> int:
        """Returns the length of the span (end - start)."""
        return self.end - self.start


@dataclass
class ChunkInfo:
    """Enhanced information about a code chunk."""
    span: Span
    text: str
    chunk_type: str = "code"  # code, imports, mixed, etc.
    metadata: Dict[str, Any] = field(default_factory=dict)
    parser_fragments: List[Any] = field(default_factory=list)  # Stores parsed elements in this chunk
    
    @property
    def start_line(self) -> int:
        return self.span.start
    
    @property
    def end_line(self) -> int:
        return self.span.end
        
    def format_parser_fragments(self) -> str:
        """Format the parser fragments in a readable tree structure, grouped by type."""
        if not self.parser_fragments:
            return ""
            
        # Group fragments by type
        grouped_fragments = {}
        for fragment in self.parser_fragments:
            fragment_type = getattr(fragment, 'type_info', 'unknown')
            fragment_kind = getattr(fragment, 'kind', '')
            
            # Use kind as the group key if available, otherwise use type_info
            group_key = fragment_kind.capitalize() if fragment_kind else fragment_type.capitalize()
            
            if group_key not in grouped_fragments:
                grouped_fragments[group_key] = []
            
            grouped_fragments[group_key].append(fragment)
        
        # Sort groups
        sorted_groups = sorted(grouped_fragments.keys())
        
        result = []
        for group in sorted_groups:
            # Add group header
            result.append(f"{group}s")
            
            # Sort fragments within group by line number
            fragments = sorted(grouped_fragments[group], key=lambda x: getattr(x, 'line', 0))
            
            for fragment in fragments:
                fragment_name = getattr(fragment, 'name', 'unnamed')
                fragment_line = getattr(fragment, 'line', 0)
                fragment_end_line = getattr(fragment, 'end_line', fragment_line)
                
                # Add fragment info
                result.append(f"  └── {fragment_name} (Lines: {fragment_line}-{fragment_end_line})")
            
        return "\n".join(result)

    def to_json(self) -> Dict[str, Any]:
        """Convert the ChunkInfo object to a JSON-serializable dictionary."""
        return {
            "span": {
                "start": self.span.start,
                "end": self.span.end
            },
            "text": self.text,
            "chunk_type": self.chunk_type,
            "metadata": self.metadata,
            "parser_fragments": [
                {
                    "type_info": getattr(fragment, 'type_info', 'unknown'),
                    "kind": getattr(fragment, 'kind', ''),
                    "name": getattr(fragment, 'name', 'unnamed'),
                    "line": getattr(fragment, 'line', 0),
                    "end_line": getattr(fragment, 'end_line', getattr(fragment, 'line', 0))
                }
                for fragment in self.parser_fragments
            ]
        } 