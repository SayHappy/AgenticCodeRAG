#!/usr/bin/env python3
"""
XML language parser implementation.
Supports XML files (.xml).
"""
from pathlib import Path
from collections import namedtuple
from typing import List, Dict, Any
import xml.etree.ElementTree as ET # Import ElementTree

from .base_parser import ElementDetector, LanguageParser, BaseExtendedTag, ParserRegistry
from .common_utils import console

# Limit for number of elements returned
MAX_ELEMENTS = 200

# Create an XML-specific extended tag
XmlExtendedTag = namedtuple("XmlExtendedTag", BaseExtendedTag._fields)

class XmlElementDetector(ElementDetector):
    """XML-specific element detector"""

    @property
    def element_types(self) -> List[str]:
        # Define element types relevant for XML (e.g., 'element')
        return ["element", "unknown"]

    @property
    def type_display_config(self) -> Dict[str, Dict[str, str]]:
        # Configure display for XML element types
        return {
            "element": {"title": "XML Elements", "color": "blue"},
            "unknown": {"title": "Other Content", "color": "white"}
        }

    @property
    def display_order(self) -> List[str]:
        # Define display order
        return ["element", "unknown"]

    def detect_elements(self, file_path: str, verbose: bool = False) -> List[XmlExtendedTag]:
        """Detect XML elements in the given file"""
        results = []
        try:
            # ElementTree doesn't easily give line numbers without custom parsing.
            # For simplicity, we'll parse the structure but might not get exact start/end lines easily.
            # A more complex SAX parser or regex might be needed for precise line numbers.
            tree = ET.parse(file_path)
            root = tree.getroot()
            rel_fname = Path(file_path).name

            # We can iterate through elements, but line numbers are tricky.
            # Let's approximate by reading lines and finding tag occurrences.
            # This is a simplified approach.
            lines = Path(file_path).read_text(encoding='utf-8', errors='replace').splitlines()
            line_map = {} # Store line numbers for tags

            for i, line in enumerate(lines):
                try:
                    # Attempt to find tags on each line (simple approach)
                    # This won't perfectly capture multi-line tags or complex structures
                    tree_line = ET.fromstring(line.strip())
                    if tree_line.tag not in line_map:
                         line_map[tree_line.tag] = i # Store first occurrence line
                except ET.ParseError:
                    # Ignore lines that aren't valid XML fragments alone
                    pass

            # Iterate through the parsed tree and use the line map
            for elem in root.iter():
                tag_name = elem.tag
                # Try to get line number, default to 0 if not found in our simple map
                line_num = line_map.get(tag_name, 0)
                # ElementTree doesn't provide end lines directly
                end_line_num = line_num # Approximation

                # Create a name representation, possibly including attributes
                attrs = " ".join([f'{k}="{v}"' for k, v in elem.attrib.items()])
                element_name = f"<{tag_name}" + (f" {attrs}" if attrs else "") + ">"

                results.append(XmlExtendedTag(
                    rel_fname=rel_fname, fname=file_path,
                    line=line_num, end_line=end_line_num, # Using approximations
                    name=element_name, kind="def", type_info="element"
                ))

            # Sort results by starting line number (optional but good practice)
            results.sort(key=lambda x: x.line)
            
            # Store original count before truncation
            original_count = len(results)
            
            # Apply truncation
            if original_count > MAX_ELEMENTS:
                last_kept_element = results[MAX_ELEMENTS - 1]
                results = results[:MAX_ELEMENTS]
                results.append(XmlExtendedTag(
                    rel_fname=rel_fname, fname=file_path,
                    line=last_kept_element.end_line, end_line=last_kept_element.end_line,
                    name=f"[... Truncated - {MAX_ELEMENTS}/{original_count} elements shown ...]",
                    kind="misc", type_info="marker"
                ))
                
            return results # Return potentially truncated results
        except ET.ParseError as e:
            if verbose:
                console.print(f"[red]XML parsing error in {file_path}: {e}[/red]")
            # Add a placeholder for the file if parsing fails entirely
            results.append(XmlExtendedTag(
                rel_fname=Path(file_path).name, fname=file_path,
                line=0, end_line=0, name="[Parse Error]", kind="err", type_info="unknown"
            ))
            return results
        except Exception as e:
            if verbose:
                console.print(f"[red]XML element detection error for {file_path}: {e}[/red]")
            return []


class XmlParser(LanguageParser):
    """XML language parser factory"""

    def create_element_detector(self) -> XmlElementDetector:
        """Create an XML-specific element detector"""
        return XmlElementDetector()

    def get_file_extensions(self) -> List[str]:
        """Get the list of file extensions supported by this parser"""
        # Add common XML related extensions
        return [".xml", ".xsd", ".xsl", ".xslt", ".wsdl", ".rss", ".atom", ".plist"]

    def get_language_name(self) -> str:
        """Get the name of the language supported by this parser"""
        return "xml"

# Register the parser
ParserRegistry.register(XmlParser()) 