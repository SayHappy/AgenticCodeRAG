#!/usr/bin/env python3
"""
Java language parser implementation using the Abstract Factory pattern.
"""
from pathlib import Path
from collections import namedtuple
from typing import List, Dict, Any
import re

from .base_parser import ElementDetector, LanguageParser, BaseExtendedTag
from .common_utils import get_tags_raw, console

# Create a Java-specific extended tag
JavaExtendedTag = namedtuple("JavaExtendedTag", BaseExtendedTag._fields)

class JavaElementDetector(ElementDetector):
    """Java-specific element detector"""
    
    @property
    def element_types(self) -> List[str]:
        return [
            "package",
            "import",
            "class",
            "interface",
            "method",
            "field",
            "unknown"
        ]
    
    @property
    def type_display_config(self) -> Dict[str, Dict[str, str]]:
        return {
            "package": {"title": "Package", "color": "bright_green"},
            "import": {"title": "Imports", "color": "magenta"},
            "class": {"title": "Classes", "color": "yellow"},
            "interface": {"title": "Interfaces", "color": "bright_cyan"},
            "method": {"title": "Methods", "color": "bright_yellow"},
            "field": {"title": "Fields", "color": "bright_blue"},
            "unknown": {"title": "Other Elements", "color": "white"}
        }
    
    @property
    def display_order(self) -> List[str]:
        return [
            "package",
            "import",
            "class",
            "interface",
            "method",
            "field",
            "unknown"
        ]
    
    def detect_elements(self, file_path: str, verbose: bool = False) -> List[JavaExtendedTag]:
        """Detect Java-specific elements in the given file"""
        try:
            # Get the raw code content
            code = Path(file_path).read_text(encoding='utf-8', errors='replace')
            lines = code.splitlines()
            
            # Initialize results
            results = []
            
            # Track package declaration
            package_declaration = None
            
            # Track imports, classes, interfaces, methods, and fields
            imports = []
            classes = []
            interfaces = []
            
            # First pass: identify package and imports
            for i, line in enumerate(lines):
                stripped = line.strip()
                
                # Skip empty lines and comments
                if not stripped or stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
                    continue
                    
                # Check for package declaration
                if stripped.startswith("package "):
                    package_name = stripped[8:].strip().rstrip(';')
                    package_declaration = {"name": package_name, "start": i, "end": i}
                    
                # Check for imports
                if stripped.startswith("import "):
                    import_name = stripped[7:].strip().rstrip(';')
                    imports.append({"name": import_name, "start": i, "end": i})
            
            # Extract package prefix if package was found
            package_prefix = None
            if package_declaration:
                package_name = package_declaration["name"]
                package_parts = package_name.split('.')
                # Use first two parts for com/org, first part otherwise
                if len(package_parts) >= 2 and package_parts[0] in ['com', 'org']:
                    package_prefix = f"{package_parts[0]}.{package_parts[1]}."
                elif len(package_parts) >= 1:
                    package_prefix = f"{package_parts[0]}."

            # Extract simple names from relevant imports for usage tracking
            import_simple_names = set()
            for imp in imports:
                full_name = imp['name']
                # Filter based on package prefix
                should_track = False
                if package_prefix:
                    if full_name.startswith(package_prefix):
                        should_track = True
                else:
                    # If no package prefix could be determined, track all imports for now
                    should_track = True

                if should_track:
                    # Handle static imports differently if needed, currently just taking the last part
                    parts = full_name.split('.')
                    if len(parts) > 0 and parts[-1] != '*':
                        import_simple_names.add(parts[-1])

            # Create a regex pattern to find any of the tracked import names as whole words
            import_pattern = None
            if import_simple_names:
                escaped_names = [re.escape(name) for name in import_simple_names]
                import_pattern = re.compile(r'\b(' + '|'.join(escaped_names) + r')\b')

            # Second pass: identify class structure and annotations
            i = 0
            current_annotations = []
            while i < len(lines):
                line = lines[i]
                stripped = line.strip()
                
                # Skip empty lines
                if not stripped:
                    i += 1
                    continue
                    
                # Collect annotations
                if stripped.startswith("@"):
                    current_annotations.append({"text": stripped, "line": i})
                    i += 1
                    continue
                
                # Identify classes
                if any(keyword in stripped for keyword in ["class ", "class\t"]) and "=" not in stripped:
                    # Extract class name
                    class_name = None
                    for part in stripped.split():
                        if part == "class":
                            next_index = stripped.split().index(part) + 1
                            if next_index < len(stripped.split()):
                                class_name = stripped.split()[next_index].split("{")[0].split("extends")[0].split("implements")[0].strip()
                    
                    if class_name:
                        start_line = i
                        # Find the class end by finding matching braces
                        brace_count = 0
                        found_opening = False
                        j = i
                        
                        while j < len(lines):
                            for char in lines[j]:
                                if char == '{':
                                    found_opening = True
                                    brace_count += 1
                                elif char == '}':
                                    brace_count -= 1
                                    if brace_count == 0 and found_opening:
                                        end_line = j
                                        break
                            if brace_count == 0 and found_opening:
                                break
                            j += 1
                        
                        # If we couldn't find the end, estimate it
                        if brace_count != 0:
                            end_line = len(lines) - 1
                        
                        # Create the class object with annotations
                        class_obj = {
                            "name": class_name,
                            "start": start_line,
                            "end": end_line,
                            "annotations": current_annotations,
                            "methods": [],
                            "fields": []
                        }
                        
                        # Reset annotations after use
                        current_annotations = []
                        
                        # Analyze class content for methods and fields
                        inside_method = False
                        method_brace_count = 0
                        method_start = -1
                        method_name = None
                        current_method_references = set() # Track references within the current method being parsed
                        
                        for k in range(start_line + 1, end_line):
                            class_line = lines[k].strip()
                            
                            # Find import usages on this line regardless of context (method/field) for now
                            line_references = set()
                            if import_pattern:
                                line_references.update(import_pattern.findall(class_line))

                            # Skip empty lines and comments
                            if not class_line or class_line.startswith("//") or class_line.startswith("/*") or class_line.startswith("*"):
                                continue
                                
                            # Collect method annotations
                            if class_line.startswith("@"):
                                if not inside_method:
                                    current_annotations.append({"text": class_line, "line": k})
                                continue
                            
                            # Check for method declarations
                            if (("public " in class_line or "private " in class_line or "protected " in class_line or "void " in class_line or 
                                 class_name in class_line or "static " in class_line or "final " in class_line) and "(" in class_line and ")" in class_line and ";" not in class_line):
                                
                                # This is a method declaration
                                method_name = None
                                for part in class_line.split("(")[0].split():
                                    if "(" in part:
                                        method_name = part.split("(")[0]
                                        break
                                    if part not in ["public", "private", "protected", "static", "final", "void", "int", "String", "boolean", "double", "float", "long", "char", "byte", "short"]:
                                        method_name = part
                                
                                if not method_name and "(" in class_line:
                                    method_name = class_line.split("(")[0].strip().split()[-1]
                                
                                # Handle constructor
                                if method_name == class_name:
                                    method_name = f"{class_name}(constructor)"
                                    
                                if method_name:
                                    method_start = k
                                    inside_method = True
                                    method_brace_count = 0
                                    
                                    # Count opening braces on this line
                                    for char in class_line:
                                        if char == '{':
                                            method_brace_count += 1
                                        elif char == '}':
                                            method_brace_count -= 1
                                    
                                    # If the method ends on the same line
                                    if "{" in class_line and "}" in class_line and method_brace_count == 0:
                                        # Add references found on the declaration line itself
                                        current_method_references.update(line_references)
                                        class_obj["methods"].append({
                                            "name": method_name,
                                            "start": k,
                                            "end": k,
                                            "annotations": current_annotations,
                                            "references": sorted(list(current_method_references)) # Store references
                                        })
                                        current_annotations = []
                                        inside_method = False
                                        method_start = -1
                                        current_method_references = set() # Reset for next method
                                    else:
                                        # Add references found on the declaration line for multi-line method
                                        current_method_references.update(line_references)
                                
                            # Inside a method, track braces and references
                            elif inside_method:
                                current_method_references.update(line_references) # Add references found on this line
                                for char in class_line:
                                    if char == '{':
                                        method_brace_count += 1
                                    elif char == '}':
                                        method_brace_count -= 1
                                        
                                # Method end
                                if method_brace_count <= 0 and "}" in class_line:
                                    class_obj["methods"].append({
                                        "name": method_name,
                                        "start": method_start,
                                        "end": k,
                                        "annotations": current_annotations,
                                        "references": sorted(list(current_method_references)) # Store references
                                    })
                                    current_annotations = []
                                    inside_method = False
                                    method_start = -1
                                    current_method_references = set() # Reset for next method
                                    
                            # Check for field declarations (if not in a method and has a semicolon)
                            elif not inside_method and "=" in class_line and ";" in class_line:
                                field_name = class_line.split("=")[0].strip().split()[-1]
                                class_obj["fields"].append({
                                    "name": field_name,
                                    "start": k,
                                    "end": k,
                                    "annotations": current_annotations,
                                    "references": sorted(list(line_references)) # Store references found on this line
                                })
                                current_annotations = []
                            
                            # Check for simple field declarations without initialization
                            elif not inside_method and ";" in class_line and not ("(" in class_line and ")" in class_line):
                                parts = class_line.rstrip(";").strip().split()
                                if len(parts) >= 2 and parts[0] not in ["return", "break", "continue", "throw"]:
                                    field_name = parts[-1]
                                    if field_name.isidentifier():
                                        class_obj["fields"].append({
                                            "name": field_name,
                                            "start": k,
                                            "end": k,
                                            "annotations": current_annotations,
                                            "references": sorted(list(line_references)) # Store references found on this line
                                        })
                                        current_annotations = []
                        
                        classes.append(class_obj)
                        i = end_line + 1
                        continue
                
                # Identify interfaces
                if any(keyword in stripped for keyword in ["interface ", "interface\t"]) and "=" not in stripped:
                    # Extract interface name
                    interface_name = None
                    for part in stripped.split():
                        if part == "interface":
                            next_index = stripped.split().index(part) + 1
                            if next_index < len(stripped.split()):
                                interface_name = stripped.split()[next_index].split("{")[0].split("extends")[0].strip()
                    
                    if interface_name:
                        start_line = i
                        # Find the interface end by finding matching braces
                        brace_count = 0
                        found_opening = False
                        j = i
                        
                        while j < len(lines):
                            for char in lines[j]:
                                if char == '{':
                                    found_opening = True
                                    brace_count += 1
                                elif char == '}':
                                    brace_count -= 1
                                    if brace_count == 0 and found_opening:
                                        end_line = j
                                        break
                            if brace_count == 0 and found_opening:
                                break
                            j += 1
                        
                        # If we couldn't find the end, estimate it
                        if brace_count != 0:
                            end_line = len(lines) - 1
                        
                        # Create the interface object with annotations
                        interface_obj = {
                            "name": interface_name,
                            "start": start_line,
                            "end": end_line,
                            "annotations": current_annotations,
                            "methods": []
                        }
                        
                        # Reset annotations after use
                        current_annotations = []
                        
                        # Add to interfaces list
                        interfaces.append(interface_obj)
                        i = end_line + 1
                        continue
                
                # If none of the above, move to next line
                i += 1
            
            # Create result elements for each component
            
            # Package declaration
            if package_declaration:
                results.append(JavaExtendedTag(
                    rel_fname=Path(file_path).name,
                    fname=file_path,
                    line=package_declaration["start"],
                    end_line=package_declaration["end"],
                    name=package_declaration["name"],
                    kind="def",
                    type_info="package"
                ))
            
            # Imports
            for imp in imports:
                # Filter displayed imports based on package prefix
                should_display = False
                if package_prefix:
                    if imp['name'].startswith(package_prefix):
                        should_display = True
                else:
                    # If no package prefix, display all imports
                    should_display = True
                
                if should_display:
                    results.append(JavaExtendedTag(
                        rel_fname=Path(file_path).name,
                        fname=file_path,
                        line=imp["start"],
                        end_line=imp["end"],
                        name=imp["name"],
                        kind="def",
                        type_info="import"
                    ))
            
            # Classes
            for cls in classes:
                results.append(JavaExtendedTag(
                    rel_fname=Path(file_path).name,
                    fname=file_path,
                    line=cls["start"],
                    end_line=cls["end"],
                    name=cls["name"],
                    kind="def",
                    type_info="class"
                ))
                
                # Methods within classes
                for method in cls["methods"]:
                    method_name_display = f"{cls['name']}.{method['name']}"
                    if method.get("references"):
                        method_name_display += f" (uses: {', '.join(method['references'])})"
                        
                    results.append(JavaExtendedTag(
                        rel_fname=Path(file_path).name,
                        fname=file_path,
                        line=method["start"],
                        end_line=method["end"],
                        name=method_name_display, # Updated name
                        kind="def",
                        type_info="method"
                    ))
                
                # Fields within classes
                for field in cls["fields"]:
                    field_name_display = f"{cls['name']}.{field['name']}"
                    if field.get("references"):
                        field_name_display += f" (uses: {', '.join(field['references'])})"
                        
                    results.append(JavaExtendedTag(
                        rel_fname=Path(file_path).name,
                        fname=file_path,
                        line=field["start"],
                        end_line=field["end"],
                        name=field_name_display, # Updated name
                        kind="def",
                        type_info="field"
                    ))
            
            # Interfaces
            for iface in interfaces:
                results.append(JavaExtendedTag(
                    rel_fname=Path(file_path).name,
                    fname=file_path,
                    line=iface["start"],
                    end_line=iface["end"],
                    name=iface["name"],
                    kind="def",
                    type_info="interface"
                ))
            
            return results
            
        except Exception as e:
            if verbose:
                console.print(f"[red]Java element detection error for {file_path}: {e}[/red]")
            return []

class JavaParser(LanguageParser):
    """Java language parser factory"""
    
    def create_element_detector(self) -> JavaElementDetector:
        """Create a Java-specific element detector"""
        return JavaElementDetector()
    
    def get_file_extensions(self) -> List[str]:
        """Get the list of file extensions supported by this parser"""
        return [".java"]
    
    def get_language_name(self) -> str:
        """Get the name of the language supported by this parser"""
        return "java"

# Register the parser
from .base_parser import ParserRegistry
ParserRegistry.register(JavaParser()) 