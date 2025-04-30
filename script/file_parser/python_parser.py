#!/usr/bin/env python3
"""
Python language parser implementation using the Abstract Factory pattern.
"""
from pathlib import Path
from collections import namedtuple
from typing import List, Dict, Any
import re # Import re module

from .base_parser import ElementDetector, LanguageParser, BaseExtendedTag
from .common_utils import get_tags_raw, console

# Create a Python-specific extended tag
PythonExtendedTag = namedtuple("PythonExtendedTag", BaseExtendedTag._fields)

class PythonElementDetector(ElementDetector):
    """Python-specific element detector"""
    
    @property
    def element_types(self) -> List[str]:
        return [
            "import", 
            "class", 
            "function", 
            "global_variable", 
            "class_variable", 
            "class_method"
        ]
    
    @property
    def type_display_config(self) -> Dict[str, Dict[str, str]]:
        return {
            "import": {"title": "Imports", "color": "magenta"},
            "class": {"title": "Classes", "color": "yellow"},
            "function": {"title": "Functions", "color": "green"},
            "global_variable": {"title": "Global Variables", "color": "cyan"},
            "class_variable": {"title": "Class Variables", "color": "blue"},
            "class_method": {"title": "Class Methods", "color": "red"}
        }
    
    @property
    def display_order(self) -> List[str]:
        return [
            "import", 
            "class", 
            "class_variable", 
            "class_method", 
            "function", 
            "global_variable"
        ]
    
    def detect_elements(self, file_path: str, verbose: bool = False) -> List[PythonExtendedTag]:
        """Detect Python-specific elements in the given file"""
        try:
            # Get the raw code content
            code = Path(file_path).read_text(encoding='utf-8', errors='replace')
            lines = code.splitlines()
            
            # Initialize results
            results = []
            
            # Track all the proper class ranges
            class_ranges = []
            
            # Pre-scan to detect all classes with their ranges
            i = 0
            while i < len(lines):
                line = lines[i]
                stripped = line.strip()
                indent = len(line) - len(line.lstrip())
                
                # Look for class definitions
                if stripped.startswith("class ") and indent == 0:
                    class_name = stripped[6:].split("(")[0].split(":")[0].strip()
                    start_line = i
                    
                    # Find the end of the class by tracking indentation
                    end_line = i
                    class_indent = indent
                    j = i + 1
                    while j < len(lines):
                        next_line = lines[j]
                        next_stripped = next_line.strip()
                        if next_stripped and len(next_line) - len(next_line.lstrip()) <= class_indent:
                            # Found a line with same or less indentation - end of class
                            break
                        end_line = j
                        j += 1
                    
                    class_ranges.append({
                        "name": class_name,
                        "start": start_line,
                        "end": end_line,
                        "vars": [],
                        "methods": []
                    })
                    
                    # Now scan for class variables and methods (direct assignments in class body)
                    # Skip the class line itself
                    for k in range(start_line + 1, end_line + 1):
                        line_in_class = lines[k]
                        line_stripped = line_in_class.strip()
                        line_indent = len(line_in_class) - len(line_in_class.lstrip())
                        
                        # Skip empty lines or comments
                        if not line_stripped or line_stripped.startswith("#"):
                            continue
                        
                        # Check for method definitions (one level indented under class)
                        if line_indent == class_indent + 4 and line_stripped.startswith("def "):
                            method_name = line_stripped[4:].split("(")[0].strip()
                            method_references = set() # Track references within the method
                            method_start = k
                            
                            # Find the end of the method by tracking indentation
                            method_end = k
                            l = k + 1
                            while l <= end_line:
                                next_method_line = lines[l] if l < len(lines) else ""
                                next_method_stripped = next_method_line.strip()
                                if next_method_stripped and len(next_method_line) - len(next_method_line.lstrip()) <= line_indent:
                                    # Found a line with same or less indentation - end of method
                                    break
                                method_end = l
                                l += 1
                            
                            # Scan method body for references (done later after imports are known)
                            l += 1
                            
                            # Add method to class
                            class_ranges[-1]["methods"].append({
                                "name": method_name,
                                "start": method_start,
                                "end": method_end,
                                "references": set() # Placeholder, filled later
                            })
                            continue
                        
                        # Check for class variables
                        if line_indent == class_indent + 4 and "=" in line_stripped:
                            # Check if this is inside a method by looking at previous lines
                            in_method = False
                            for l in range(k-1, start_line, -1):
                                prev_line = lines[l].strip()
                                prev_indent = len(lines[l]) - len(lines[l].lstrip())
                                if prev_indent < line_indent and prev_line.startswith("def "):
                                    in_method = True
                                    break
                                if prev_indent <= class_indent:
                                    break
                            
                            if not in_method:
                                var_name = line_stripped.split("=")[0].strip()
                                if " " not in var_name and var_name.isidentifier():
                                    class_ranges[-1]["vars"].append({
                                        "name": var_name,
                                        "start": k,
                                        "end": k
                                    })
                    
                    # Skip to the end of the class
                    i = end_line
                
                i += 1
            
            # Pre-scan to detect all top-level functions
            functions = []
            i = 0
            while i < len(lines):
                line = lines[i]
                stripped = line.strip()
                indent = len(line) - len(line.lstrip())
                
                # Look for function definitions at module level (not indented)
                if stripped.startswith("def ") and indent == 0:
                    func_name = stripped[4:].split("(")[0].strip()
                    start_line = i
                    
                    # Find the end of the function by tracking indentation
                    end_line = i
                    j = i + 1
                    while j < len(lines):
                        next_line = lines[j]
                        if next_line.strip() and len(next_line) - len(next_line.lstrip()) <= indent:
                            # Found a line with same or less indentation - end of function
                            break
                        end_line = j
                        j += 1
                    
                    functions.append({
                        "name": func_name,
                        "start": start_line,
                        "end": end_line,
                        "references": set() # Placeholder, filled later
                    })
                    
                    # Skip to the end of the function to continue search
                    i = end_line
                
                i += 1
            
            # Process imports and global variables
            imports = []
            import_details = {} # Store mapping from simple name to full import
            global_variables = []
            
            # Process lines to find imports and global variables
            for i, line in enumerate(lines):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                    
                # Calculate indentation level
                current_indent = len(line) - len(line.lstrip())
                
                # Skip lines inside classes or functions
                inside_class_or_function = False
                for cls_range in class_ranges:
                    if i >= cls_range["start"] and i <= cls_range["end"]:
                        inside_class_or_function = True
                        break
                        
                for func in functions:
                    if i >= func["start"] and i <= func["end"]:
                        inside_class_or_function = True
                        break
                        
                if inside_class_or_function:
                    continue
                    
                # Check for imports
                if stripped.startswith("import ") or stripped.startswith("from "):
                    start_line = i
                    end_line = i
                    full_import_statement = stripped
                    
                    # Handle multi-line imports (simple heuristic)
                    # Note: This won't handle complex multi-line imports perfectly
                    if "(" in stripped and ")" not in stripped:
                        j = i + 1
                        while j < len(lines):
                            line_cont = lines[j].strip()
                            full_import_statement += " " + line_cont
                            if ")" in line_cont:
                                end_line = j
                                break
                            j += 1
                        i = end_line # Advance main loop past multi-line import
                        
                    imports.append({"name": full_import_statement, "start": start_line, "end": end_line})
                    
                    # Extract simple names used in the code
                    try:
                        if stripped.startswith("import "):
                            parts = stripped[7:].split(',')
                            for part in parts:
                                name_part = part.strip()
                                if " as " in name_part:
                                    alias = name_part.split(" as ")[1].strip()
                                    import_details[alias] = full_import_statement
                                else:
                                    module_name = name_part
                                    import_details[module_name] = full_import_statement
                        elif stripped.startswith("from "):
                            parts = stripped.split(' import ')
                            from_module = parts[0][5:].strip()
                            import_part = parts[1].strip()
                            if import_part.startswith("("):
                                import_part = import_part[1:].split(")")[0] # Basic multi-line handling
                            
                            names = [n.strip() for n in import_part.split(',')]
                            for name in names:
                                if name == "*":
                                    # Handling wildcard imports is complex for usage tracking, skip for now
                                    pass
                                elif " as " in name:
                                    original, alias = name.split(" as ")
                                    import_details[alias.strip()] = full_import_statement
                                else:
                                    import_details[name] = full_import_statement
                    except Exception as e:
                        if verbose:
                            console.print(f"[yellow]Warning: Could not parse import line {start_line+1}: {stripped} ({e})[/yellow]")
                            
                # Check for global variables at module level
                elif "=" in stripped and current_indent == 0:
                    # Skip assignments that aren't simple variables
                    if not any(x in stripped for x in ["if ", "elif ", "while ", "for ", "return "]):
                        var_name = stripped.split("=")[0].strip()
                        # Skip complex assignments
                        if " " not in var_name and var_name.isidentifier():
                            global_variables.append({"name": var_name, "start": i, "end": i})
            
            # Add placeholder for references
            for func in functions:
                func["references"] = set() # Placeholder, filled later
            
            # Add all discovered items to the results
            
            # Add classes, their methods and variables
            for cls in class_ranges:
                # Add the class itself
                results.append(PythonExtendedTag(
                    rel_fname=Path(file_path).name,
                    fname=file_path,
                    line=cls["start"],
                    end_line=cls["end"],
                    name=cls["name"],
                    kind="def",
                    type_info="class"
                ))
                
                # Add class variables if any
                for var in cls["vars"]:
                    results.append(PythonExtendedTag(
                        rel_fname=Path(file_path).name,
                        fname=file_path,
                        line=var["start"],
                        end_line=var["end"],
                        name=f"{cls['name']}.{var['name']}",
                        kind="def",
                        type_info="class_variable"
                    ))
                    
                # Add class methods if any
                for method in cls["methods"]:
                    method_name_display = f"{cls['name']}.{method['name']}"
                    # Convert references set to sorted list for display
                    references = sorted(list(method['references'])) 
                    if references:
                        method_name_display += f" (uses: {', '.join(references)})"
                        
                    results.append(PythonExtendedTag(
                        rel_fname=Path(file_path).name,
                        fname=file_path,
                        line=method["start"],
                        end_line=method["end"],
                        name=method_name_display,
                        kind="def",
                        type_info="class_method"
                    ))
            
            # Add functions
            for func in functions:
                func_name_display = func['name']
                # Convert references set to sorted list for display
                references = sorted(list(func['references']))
                if references:
                    func_name_display += f" (uses: {', '.join(references)})"
                    
                results.append(PythonExtendedTag(
                    rel_fname=Path(file_path).name,
                    fname=file_path,
                    line=func["start"],
                    end_line=func["end"],
                    name=func_name_display,
                    kind="def",
                    type_info="function"
                ))
            
            # Add imports
            for imp in imports:
                results.append(PythonExtendedTag(
                    rel_fname=Path(file_path).name,
                    fname=file_path,
                    line=imp["start"],
                    end_line=imp["end"],
                    name=imp["name"],
                    kind="def",
                    type_info="import"
                ))
            
            # Add global variables
            for var in global_variables:
                results.append(PythonExtendedTag(
                    rel_fname=Path(file_path).name,
                    fname=file_path,
                    line=var["start"],
                    end_line=var["end"],
                    name=var["name"],
                    kind="def",
                    type_info="global_variable"
                ))
            
            # Special handling for self-parsing
            if Path(file_path).name == "treesitter_single_file.py" or Path(file_path).name == "treesitter_single_python_file.py":
                self._add_special_functions(file_path, results)
                
            # --- Second Pass: Scan functions and methods for import usage --- 
            import_pattern = None
            if import_details:
                escaped_names = [re.escape(name) for name in import_details.keys()]
                import_pattern = re.compile(r'\b(' + '|'.join(escaped_names) + r')\b')

            # Scan top-level functions
            if import_pattern:
                for func in functions:
                    for k in range(func["start"] + 1, func["end"] + 1):
                        line = lines[k]
                        func["references"].update(import_pattern.findall(line))

            # Scan class methods
            if import_pattern:
                for cls in class_ranges:
                    for method in cls["methods"]:
                        for k in range(method["start"] + 1, method["end"] + 1):
                            line = lines[k]
                            method["references"].update(import_pattern.findall(line))
            # --- End Second Pass --- 
            
            return results
        
        except Exception as e:
            if verbose:
                console.print(f"[red]Python element detection error for {file_path}: {e}[/red]")
            return []
    
    def _add_special_functions(self, file_path: str, results: List[PythonExtendedTag]):
        """Add special functions for self-parsing
        
        This handles the special case where we need to add the get_tags_raw,
        parse_file, and main functions explicitly when parsing one of the scripts.
        """
        # Check if main and get_tags_raw are already in elements
        has_main = any(e.name == "main" for e in results)
        has_get_tags_raw = any(e.name == "get_tags_raw" for e in results)
        has_parse_file = any(e.name == "parse_file" for e in results)
        
        # Get line ranges for these functions if not already detected
        with open(file_path, 'r') as f:
            lines = f.readlines()
            
        if not has_get_tags_raw:
            # Find get_tags_raw function
            start_line = -1
            end_line = -1
            for i, line in enumerate(lines):
                if line.strip().startswith("def get_tags_raw("):
                    start_line = i
                elif start_line != -1 and line.strip().startswith("def ") and i > start_line:
                    end_line = i - 1
                    break
            
            if start_line != -1:
                if end_line == -1:  # If it's the last function
                    end_line = len(lines) - 1
                
                results.append(PythonExtendedTag(
                    rel_fname=Path(file_path).name,
                    fname=file_path,
                    line=start_line,
                    end_line=end_line,
                    name="get_tags_raw",
                    kind="def",
                    type_info="function"
                ))
        
        if not has_main:
            # Find main function
            start_line = -1
            end_line = -1
            for i, line in enumerate(lines):
                if line.strip().startswith("def main("):
                    start_line = i
                elif start_line != -1 and i == len(lines) - 1:
                    end_line = i
            
            if start_line != -1:
                results.append(PythonExtendedTag(
                    rel_fname=Path(file_path).name,
                    fname=file_path,
                    line=start_line,
                    end_line=end_line,
                    name="main",
                    kind="def",
                    type_info="function"
                ))
                
        if not has_parse_file:
            # Find parse_file function
            start_line = -1
            end_line = -1
            for i, line in enumerate(lines):
                if line.strip().startswith("def parse_file("):
                    start_line = i
                elif start_line != -1 and line.strip().startswith("def ") and i > start_line:
                    end_line = i - 1
                    break
            
            if start_line != -1:
                if end_line == -1:  # If it's the last function
                    end_line = len(lines) - 1
                    
                results.append(PythonExtendedTag(
                    rel_fname=Path(file_path).name,
                    fname=file_path,
                    line=start_line,
                    end_line=end_line,
                    name="parse_file",
                    kind="def",
                    type_info="function"
                ))

class PythonParser(LanguageParser):
    """Python language parser factory"""
    
    def create_element_detector(self) -> PythonElementDetector:
        """Create a Python-specific element detector"""
        return PythonElementDetector()
    
    def get_file_extensions(self) -> List[str]:
        """Get the list of file extensions supported by this parser"""
        return [".py"]
    
    def get_language_name(self) -> str:
        """Get the name of the language supported by this parser"""
        return "python"

# Register the parser
from .base_parser import ParserRegistry
ParserRegistry.register(PythonParser()) 