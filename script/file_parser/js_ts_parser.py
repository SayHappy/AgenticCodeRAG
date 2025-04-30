#!/usr/bin/env python3
"""
JavaScript/TypeScript language parser implementation.
Supports JS, TS, JSX, and TSX files.
"""
import re
from pathlib import Path
from collections import namedtuple
from typing import List, Dict, Any

from .base_parser import ElementDetector, LanguageParser, BaseExtendedTag, ParserRegistry
from .common_utils import console

# Create a JS/TS-specific extended tag
JsTsExtendedTag = namedtuple("JsTsExtendedTag", BaseExtendedTag._fields)

class JsTsElementDetector(ElementDetector):
    """JavaScript/TypeScript-specific element detector"""

    @property
    def element_types(self) -> List[str]:
        return [
            "import",
            "component",
            "hook",
            "function",
            "method",  # Add method type to support object methods
            "variable",
            "export",
            "unknown" # Keep unknown for elements not specifically categorized
        ]

    @property
    def type_display_config(self) -> Dict[str, Dict[str, str]]:
        return {
            "import": {"title": "Imports", "color": "bright_green"},
            "component": {"title": "Components", "color": "yellow"},
            "hook": {"title": "Hooks", "color": "bright_magenta"},
            "function": {"title": "Functions", "color": "bright_yellow"},
            "method": {"title": "Methods", "color": "cyan"},  # Add display config for methods
            "variable": {"title": "Variables", "color": "bright_blue"},
            "export": {"title": "Exports", "color": "magenta"},
            "unknown": {"title": "Other Elements", "color": "white"}
        }

    @property
    def display_order(self) -> List[str]:
        return [
            "import",
            "component",
            "hook",
            "function",
            "method",  # Add methods to display order
            "variable",
            "export",
            "unknown"
        ]

    # --- Helper functions moved from FrontendElementDetector ---
    def _is_pascal_case(self, name):
        """Helper function to identify React component names (PascalCase)"""
        if not name or not name[0].isalpha():
            return False
        return name[0].isupper() and not name.isupper()

    def _contains_jsx(self, code_segment):
        """Helper to check if a code segment contains JSX"""
        return any(jsx_hint in code_segment.lower()
                   for jsx_hint in ["<div", "<>", "</", "fragment", "jsx", "tsx", "<span", "<p", "<h", "<button", "<input"])

    def _find_element_end(self, lines: List[str], start_idx: int, open_char='{', close_char='}'):
        """Find element end by tracking braces"""
        brace_count = 0
        found_opening = False

        # Process current line first
        current_line = lines[start_idx]
        for char in current_line:
            if char == open_char:
                found_opening = True
                brace_count += 1
            elif char == close_char:
                brace_count -= 1

        # If we already have balanced braces, return the same line
        if brace_count == 0 and found_opening:
            return start_idx

        # Continue to next lines if needed
        if brace_count > 0:
            j = start_idx + 1
            while j < len(lines):
                for char in lines[j]:
                    if char == open_char:
                        brace_count += 1
                    elif char == close_char:
                        brace_count -= 1
                        # If braces are balanced, we've found the end
                        if brace_count == 0 and found_opening:
                            return j
                j += 1

        # Default to current line if we couldn't find the end
        return start_idx

    def _has_jsx_in_next_lines(self, lines: List[str], start_idx: int, n=15):
        """Check if there's JSX content in the next N lines"""
        end_idx = min(start_idx + n, len(lines))
        code_segment = "\n".join(lines[start_idx:end_idx])
        return self._contains_jsx(code_segment)
    # --- End Helper functions ---

    def detect_elements(self, file_path: str, verbose: bool = False) -> List[JsTsExtendedTag]:
        """Detect JS/TS-specific elements in the given file"""
        try:
            code = Path(file_path).read_text(encoding='utf-8', errors='replace')
            lines = code.splitlines()
            results = []
            self._process_js_ts_file(file_path, lines, results, verbose) # Pass verbose
            return results
        except Exception as e:
            if verbose:
                console.print(f"[red]JS/TS element detection error for {file_path}: {e}[/red]")
            return []

    def _process_js_ts_file(self, file_path: str, lines: List[str], results: List[JsTsExtendedTag], verbose: bool = False):
        """Process JavaScript/TypeScript files (Adapted from FrontendElementDetector)"""
        # Track imports
        imports = []

        # Track components, functions, variables, hooks, methods
        components = []
        functions = []
        variables = []
        hooks = []
        methods = []  # Add methods tracking

        # Track exports
        exports = []

        # Store mapping from simple name to import source
        import_details = {}

        # First pass: identify imports, exports, and declarations
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Skip empty lines and comments
            if not line or line.startswith("//") or line.startswith("/*") or line.startswith("*"):
                i += 1
                continue

            # --- Add require() detection ---
            require_match = re.match(r'(const|let|var)\s+([\w\d_\{\}\s,]+)\s*=\s*require\(\s*[\'"]([^\'"]+)[\'"]\s*\);?', line)
            if require_match:
                declaration_type = require_match.group(1)
                imported_names_raw = require_match.group(2).strip()
                source_module = require_match.group(3)
                start_line_idx = i

                # Basic handling for both single variable and destructuring
                display_name = f"{imported_names_raw} from '{source_module}' (require)"
                import_info = {
                    "name": display_name,
                    "start": start_line_idx,
                    "end": i
                }
                imports.append(import_info)

                # Add to import_details for usage tracking (simple version for now)
                # This won't correctly handle destructuring details for usage yet
                if '{' not in imported_names_raw: # Add simple names
                    import_details[imported_names_raw] = source_module
                else: # Attempt to add destructured names (basic split)
                    try:
                        names = imported_names_raw.strip('{}').split(',')
                        for name_part in names:
                            name = name_part.split(':')[0].strip() # Handle aliasing like { original: alias }
                            if name:
                                import_details[name] = source_module
                    except Exception:
                         if verbose:
                             console.print(f"[yellow]Warning: Could not parse destructured require names at line {start_line_idx+1}: {line}[/yellow]")


                i += 1 # Move to next line
                continue # Skip other checks for this line
            # --- End require() detection ---

            # Check for imports
            elif line.startswith("import "):
                import_statement = line
                start_line_idx = i # Store original start line index
                # Handle multi-line imports
                while ";" not in import_statement and "}" not in import_statement and i < len(lines) - 1:
                    i += 1
                    import_statement += " " + lines[i].strip()

                # Parse import name and details
                try:
                    source_module = None
                    import_info = {"name": "unknown import", "start": start_line_idx, "end": i} # Use original start index
                    if " from " in import_statement:
                        parts = import_statement.split(" from ")
                        import_clause = parts[0][6:].strip() # After 'import '
                        source_module = parts[1].strip().rstrip(';').strip("'").strip('"')
                        import_info["name"] = f"'{source_module}'" # Use source module as default name

                        # Destructured imports: import { useState, useEffect as effect } from 'react'
                        if import_clause.startswith("{") and import_clause.endswith("}"):
                            import_names = []
                            names = import_clause[1:-1].split(',')
                            for name_part in names:
                                name_part = name_part.strip()
                                if " as " in name_part:
                                    original, alias = name_part.split(" as ")
                                    import_details[alias.strip()] = source_module
                                    import_names.append(alias.strip())
                                else:
                                    import_details[name_part] = source_module
                                    import_names.append(name_part)
                            import_info["name"] = f"{{{', '.join(import_names)}}} from '{source_module}'"

                        # Default import: import React from 'react'
                        elif "* as" not in import_clause and "{" not in import_clause:
                            default_name = import_clause.split(',')[0].strip()
                            import_details[default_name] = source_module
                            import_info["name"] = f"{default_name} from '{source_module}'"
                        # Namespace import: import * as React from 'react'
                        elif "* as" in import_clause:
                            alias = import_clause.split("* as")[1].strip()
                            import_details[alias] = source_module
                            import_info["name"] = f"* as {alias} from '{source_module}'"

                    # Side effect import: import './styles.css'
                    elif import_statement.startswith("import ") and " from " not in import_statement:
                        source_module = import_statement.split("import ")[1].strip().rstrip(';').strip("'").strip('"')
                        import_info["name"] = f"(side effect) '{source_module}'"
                        # No names added to import_details for side-effect imports

                    imports.append(import_info)

                except Exception as e:
                    if verbose:
                        console.print(f"[yellow]Warning: Could not parse import line {start_line_idx+1}: {import_statement} ({e})[/yellow]")


            # Check for explicit export declarations
            elif line.startswith("export "):
                export_line = line
                start_line = i
                end_line = i # Default end line

                # Handle different export types
                if "default" in export_line:
                    export_name = "default"
                    export_type = "default"
                    details = ""

                    # Check if it's exporting a named entity defined inline
                    if "function" in export_line:
                        try:
                            export_name = export_line.split("function ")[1].split("(")[0].strip()
                            export_type = "function"
                            end_line = self._find_element_end(lines, i)
                            details = f" (as default)"
                        except: pass
                    elif "class" in export_line:
                        try:
                            export_name = export_line.split("class ")[1].split(" ")[0].strip().split("{")[0] # Handle potential generic/extends
                            export_type = "class"
                            end_line = self._find_element_end(lines, i)
                            details = f" (as default)"
                        except: pass
                    elif "const" in export_line or "let" in export_line or "var" in export_line:
                         try:
                             decl_type = "const" if "const" in export_line else "let" if "let" in export_line else "var"
                             export_name = export_line.split(f"{decl_type} ")[1].split("=")[0].strip()
                             export_type = "variable"
                             end_line = self._find_element_end(lines, i) if "{" in export_line else i
                             details = f" (as default)"
                         except: pass
                    # Handle "export default SomeIdentifier;"
                    elif "default " in export_line and not export_line.endswith("default"):
                        try:
                            export_name = export_line.split("default ")[1].strip().rstrip(";")
                            export_type = "value" # Assume value, could be component/func
                            if self._is_pascal_case(export_name):
                                export_type = "component"
                            # Cannot easily determine end_line here
                            details = f" (as default)"
                        except: pass
                    # Handle "export default {" or "export default [" or "export default function()..."
                    elif export_line.endswith("default"):
                         details = " (as default)"
                         # Cannot easily determine end_line here, might be anonymous function/object

                    exports.append({
                        "name": f"{export_name}{details}",
                        "type": export_type,
                        "start": start_line,
                        "end": end_line
                    })

                elif "const " in export_line or "let " in export_line or "var " in export_line:
                    try:
                        for decl in ["const ", "let ", "var "]:
                            if decl in export_line:
                                var_parts = export_line.split(decl)[1].split("=")[0].strip()
                                export_name = var_parts # Handle destructuring later if needed
                                break

                        # Find variable declaration end if multi-line object/array
                        current_end = i
                        if "=" in line and ("{" in line.split("=")[1] or "[" in line.split("=")[1]):
                             current_end = self._find_element_end(lines, i, '{' if '{' in line else '[', '}' if '{' in line else ']')

                        exports.append({
                            "name": export_name,
                            "type": "variable",
                            "start": start_line,
                            "end": current_end
                        })
                    except: pass

                elif "function " in export_line:
                    try:
                        export_name = export_line.split("function ")[1].split("(")[0].strip()
                        exports.append({
                            "name": export_name,
                            "type": "function",
                            "start": start_line,
                            "end": self._find_element_end(lines, i)
                        })
                    except: pass

                elif "class " in export_line:
                    try:
                        export_name = export_line.split("class ")[1].split(" ")[0].strip().split("{")[0]
                        exports.append({
                            "name": export_name,
                            "type": "class",
                            "start": start_line,
                            "end": self._find_element_end(lines, i)
                        })
                    except: pass

                elif "{" in export_line and "}" in export_line and "from" not in export_line:
                    # Handle named exports like "export { Component1, Component2 }"
                    try:
                        export_items_str = export_line.split("{")[1].split("}")[0].strip()
                        for item in export_items_str.split(","):
                            item_name = item.strip()
                            display_name = item_name
                            if " as " in item_name:
                                original_name, alias_name = item_name.split(" as ")
                                display_name = f"{original_name.strip()} as {alias_name.strip()}"
                                item_name = alias_name.strip() # Actual exported name

                            # We don't know the type here easily, mark as 'named'
                            exports.append({
                                "name": display_name,
                                "type": "named",
                                "start": start_line,
                                "end": end_line # Stays as single line
                            })
                    except: pass
                elif "from" in export_line: # Handle export * from './mod' or export { name } from './mod'
                    export_details = export_line.split("export ")[1].strip()
                    exports.append({
                        "name": f"re-export: {export_details}",
                        "type": "re-export",
                        "start": start_line,
                        "end": end_line
                    })


            # Check for class component declarations
            # Simplified check - focus on PascalCase and extends Component/PureComponent
            elif "class " in line and self._is_pascal_case(line.split("class")[1].strip().split()[0].strip().split("{")[0].split("<")[0].strip()):
                 # Look for 'extends React.Component' or 'extends Component' etc.
                 component_patterns = ["Component", "PureComponent", "React.Component", "React.PureComponent"]
                 is_component = False
                 
                 for pattern in component_patterns:
                     if pattern in line or pattern in "".join(lines[i:min(i+5, len(lines))]):
                         is_component = True
                         break
                                 
                 if is_component:
                    try:
                        # Extract class name more carefully
                        class_declaration = line.split("class")[1].strip()
                        class_name = class_declaration.split("extends")[0].strip() if "extends" in class_declaration else class_declaration.split("{")[0].strip()
                        # Remove any generic type parameters
                        if "<" in class_name:
                            class_name = class_name.split("<")[0].strip()
                        # Remove any whitespace or curly braces
                        class_name = class_name.split()[0].strip()
                        
                        if verbose:
                            console.print(f"[green]Found class component: {class_name}[/green]")
                        
                        start_line = i
                        end_line = self._find_element_end(lines, i)

                        is_exported = line.startswith("export ")
                        components.append({
                            "name": class_name,
                            "start": start_line,
                            "end": end_line,
                            "exported": is_exported,
                            "type": "class component",
                            "references": set() # Placeholder
                        })
                        
                        # Scan for class methods
                        class_body = "\n".join(lines[start_line:end_line+1])
                        method_patterns = [
                            r'(\w+)\s*\([^)]*\)\s*{'  # methodName() {
                        ]
                        
                        for pattern in method_patterns:
                            method_matches = re.finditer(pattern, class_body)
                            for match in method_matches:
                                method_name = match.group(1)
                                # Skip constructor if it appears in class pattern match
                                if method_name not in ['if', 'for', 'while', 'switch', 'catch', 'class']:
                                    # Find method boundaries
                                    method_start_pos = class_body.find(match.group(0))
                                    if method_start_pos != -1:
                                        # Convert position to line number
                                        method_lines = class_body[:method_start_pos].count('\n')
                                        method_start = start_line + method_lines
                                        
                                        # Find end of method by tracking braces
                                        method_body = class_body[method_start_pos:]
                                        brace_count = 0
                                        in_method = False
                                        for idx, char in enumerate(method_body):
                                            if char == '{':
                                                brace_count += 1
                                                in_method = True
                                            elif char == '}':
                                                brace_count -= 1
                                                if in_method and brace_count == 0:
                                                    # End of method found
                                                    method_end_pos = method_start_pos + idx
                                                    method_end_lines = class_body[:method_end_pos].count('\n')
                                                    method_end = start_line + method_end_lines
                                                    
                                                    # Add the method with Java-style format: ClassName.methodName
                                                    display_name = f"{class_name}.{method_name}"
                                                    methods.append({
                                                        "name": display_name,
                                                        "start": method_start,
                                                        "end": method_end,
                                                        "references": set()
                                                    })
                                                    break
                        
                        i = end_line # Move past the class block
                    except Exception as e:
                        if verbose:
                            console.print(f"[yellow]Warning: Could not parse class component at line {i+1}: {e}[/yellow]")


            # Check for React functional component or hooks
            # More robust check based on function/const + name convention or return value
            elif (("function" in line and "(" in line) or
                 ("const" in line and "=" in line and ("=>" in line or "=>" in "".join(lines[i:min(i+3, len(lines))])))):
                try:
                    is_func = "function " in line
                    name_part = line.split("function ")[1].split("(")[0].strip() if is_func else line.split("const ")[1].split("=")[0].strip()
                    # Handle type annotations like const MyComponent: React.FC = ...
                    if ":" in name_part:
                        name_part = name_part.split(":")[0].strip()

                    start_line = i
                    end_line = self._find_element_end(lines, i)

                    is_hook = name_part.startswith("use") and name_part[3].isupper() # Starts with use and is camelCase/PascalCase
                    is_component = self._is_pascal_case(name_part)

                    # Refine component detection: check for JSX return within the block
                    has_jsx = False
                    if is_component:
                        component_body = "\n".join(lines[start_line:end_line+1])
                        if self._contains_jsx(component_body):
                            has_jsx = True
                        # Check common type hints
                        elif any(type_hint in line for type_hint in ["React.FC", "React.FunctionComponent", "FC<", "FunctionComponent<", "Component<"]):
                             has_jsx = True # Assume component if typed as such

                    is_exported = line.startswith("export ")

                    if is_hook:
                        hooks.append({
                            "name": name_part,
                            "start": start_line,
                            "end": end_line,
                            "exported": is_exported,
                            "references": set()
                        })
                        i = end_line # Move past the hook block
                    elif is_component and has_jsx:
                         components.append({
                            "name": name_part,
                            "start": start_line,
                            "end": end_line,
                            "exported": is_exported,
                            "type": "functional component",
                            "references": set()
                        })
                         i = end_line # Move past the component block
                    # If not component or hook, consider it a regular function
                    elif not is_component and not is_hook:
                        # Check if it's nested - rudimentary check
                        is_nested = False
                        for block in components + hooks:
                             if block["start"] < i < block["end"]:
                                 is_nested = True
                                 break

                        if not is_nested:
                             functions.append({
                                "name": name_part,
                                "start": start_line,
                                "end": end_line,
                                "exported": is_exported,
                                "references": set()
                            })
                             i = end_line # Move past the function block

                except Exception as e:
                    # print(f"Error parsing func/comp/hook at line {i+1}: {e}") # Debugging
                    pass

            # Check for top-level variable declarations (not already caught by export or function/comp/hook)
            elif any(decl in line for decl in ["const ", "let ", "var "]):
                 # Ensure it's not inside another block we've already identified
                 is_nested = False
                 for block in components + hooks + functions:
                     if block["start"] < i < block["end"]:
                         is_nested = True
                         break

                 if not is_nested:
                    try:
                        for decl in ["const ", "let ", "var "]:
                            if decl in line:
                                # Extract variable name(s)
                                decl_part = line.split(decl)[1]
                                var_assign_part = decl_part.split("=")[0].strip()
                                var_name = var_assign_part
                                if ":" in var_name: # Handle type annotation
                                    var_name = var_name.split(":")[0].strip()

                                # Find variable declaration end (handle multi-line obj/arr)
                                end_line = i
                                if "=" in decl_part:
                                    value_part = decl_part.split("=", 1)[1].strip()
                                    if (value_part.startswith("{") and not value_part.endswith("}")) or \
                                       (value_part.startswith("[") and not value_part.endswith("]")):
                                        open_char = "{" if value_part.startswith("{") else "["
                                        close_char = "}" if open_char == "{" else "]"
                                        # Need to find the start of the actual value if it's on next line
                                        val_start_idx = i
                                        temp_line_idx = i
                                        while open_char not in lines[temp_line_idx] and temp_line_idx < len(lines) -1:
                                            temp_line_idx += 1
                                            if open_char in lines[temp_line_idx]:
                                                val_start_idx = temp_line_idx
                                                break
                                        end_line = self._find_element_end(lines, val_start_idx, open_char, close_char)

                                is_exported = line.startswith("export ") # Should be caught by export block, but check anyway
                                variables.append({
                                    "name": var_name, # Can be complex like { a, b }
                                    "start": i,
                                    "end": end_line,
                                    "exported": is_exported,
                                    "references": set()
                                })
                                i = end_line # Move past variable block
                                break # Found declaration type
                    except: pass

            # Check for object literals with method definitions
            # Examples: Page({ method1() {}, method2() {} }) or const obj = { method() {} }
            elif '{' in line and i < len(lines) - 1:
                # Identify potential object literal declarations
                # This could be a Page call, object assignment, etc.
                object_start = i
                object_name = ""
                
                # Try to get the object name
                if '=' in line:
                    try:
                        object_name = line.split('=')[0].strip()
                        if ' ' in object_name:  # Handle 'const obj =' pattern
                            object_name = object_name.split(' ')[-1].strip()
                    except:
                        object_name = "anonymous object"
                elif '(' in line and '{' in line:  # Handle Page({...}) pattern
                    try:
                        object_name = line.split('(')[0].strip()
                    except:
                        object_name = "anonymous function call"
                
                # Find the closing brace of the object
                brace_count = line.count('{') - line.count('}')
                j = i + 1
                object_end = i
                
                if brace_count > 0:  # We have an unclosed object
                    while j < len(lines) and brace_count > 0:
                        current = lines[j].strip()
                        brace_count += current.count('{') - current.count('}')
                        if brace_count == 0:
                            object_end = j
                        j += 1
                
                # If we found an object, scan it for methods
                if object_end > object_start:
                    object_body = "\n".join(lines[object_start:object_end+1])
                    
                    # Extract methods - pattern: methodName(args) { ... }
                    # Also catch methodName: function(args) { ... } and methodName: (args) => { ... }
                    method_patterns = [
                        r'(\w+)\s*\([^)]*\)\s*{',                # methodName() { 
                        r'(\w+)\s*:\s*function\s*\([^)]*\)\s*{', # methodName: function() {
                        r'(\w+)\s*:\s*\([^)]*\)\s*=>\s*{'        # methodName: () => {
                    ]
                    
                    for pattern in method_patterns:
                        method_matches = re.finditer(pattern, object_body)
                        for match in method_matches:
                            method_name = match.group(1)
                            if method_name not in ['if', 'for', 'while', 'switch', 'catch']:  # Skip control structures
                                # Find method boundaries
                                method_start_pos = object_body.find(match.group(0))
                                if method_start_pos != -1:
                                    # Convert position to line number
                                    method_lines = object_body[:method_start_pos].count('\n')
                                    method_start = object_start + method_lines
                                    
                                    # Find end of method by tracking braces
                                    method_body = object_body[method_start_pos:]
                                    brace_count = 0
                                    in_method = False
                                    for idx, char in enumerate(method_body):
                                        if char == '{':
                                            brace_count += 1
                                            in_method = True
                                        elif char == '}':
                                            brace_count -= 1
                                            if in_method and brace_count == 0:
                                                # End of method found
                                                method_end_pos = method_start_pos + idx
                                                method_end_lines = object_body[:method_end_pos].count('\n')
                                                method_end = object_start + method_end_lines
                                                
                                                # Add the method with Java-style format: ClassName.methodName
                                                display_name = f"{object_name}.{method_name}"
                                                methods.append({
                                                    "name": display_name,
                                                    "start": method_start,
                                                    "end": method_end,
                                                    "references": set()
                                                })
                                                break
                    
                    # Continue parsing from the end of the object
                    i = object_end

            i += 1


        # --- Second Pass: Scan components, hooks, functions for import usage ---
        import_pattern = None
        if import_details:
            # Escape names and ensure they are whole words
            escaped_names = [re.escape(name) for name in import_details.keys() if name] # Ensure name is not empty
            if escaped_names:
                 import_pattern = re.compile(r'(?<![\w.])(' + '|'.join(escaped_names) + r')(?![>\w])') # Avoid matching self closing tags like <Component/> or object properties

        if import_pattern:
            # Scan only the major blocks for performance
            element_lists = [components, hooks, functions, methods]  # Add methods to the elements to scan
            for elem_list in element_lists:
                for elem in elem_list:
                    elem_body = "\n".join(lines[elem["start"]:elem["end"] + 1])
                    # Simple comment removal (might not handle all edge cases)
                    elem_body = re.sub(r'//.*', '', elem_body) # Remove single line comments
                    elem_body = re.sub(r'/\*.*?\*/', '', elem_body, flags=re.DOTALL) # Remove multi-line comments

                    # Find unique matches within the block
                    found_refs = set(import_pattern.findall(elem_body))
                    elem["references"] = found_refs

        # --- End Second Pass ---

        # Create result elements
        rel_fname = Path(file_path).name

        # Imports
        for imp in imports:
            results.append(JsTsExtendedTag(
                rel_fname=rel_fname, fname=file_path,
                line=imp["start"], end_line=imp["end"],
                name=imp["name"], kind="def", type_info="import"
            ))

        # Components
        for comp in components:
            ref_str = f" (uses: {', '.join(sorted(list(comp['references'])))})" if comp.get('references') else ""
            results.append(JsTsExtendedTag(
                rel_fname=rel_fname, fname=file_path,
                line=comp["start"], end_line=comp["end"],
                name=f"{comp['name']}{ref_str}", kind="def", type_info="component"
            ))

        # Hooks
        for hook in hooks:
            ref_str = f" (uses: {', '.join(sorted(list(hook['references'])))})" if hook.get('references') else ""
            results.append(JsTsExtendedTag(
                rel_fname=rel_fname, fname=file_path,
                line=hook["start"], end_line=hook["end"],
                name=f"{hook['name']}{ref_str}", kind="def", type_info="hook"
            ))

        # Functions
        for func in functions:
            ref_str = f" (uses: {', '.join(sorted(list(func['references'])))})" if func.get('references') else ""
            results.append(JsTsExtendedTag(
                rel_fname=rel_fname, fname=file_path,
                line=func["start"], end_line=func["end"],
                name=f"{func['name']}{ref_str}", kind="def", type_info="function"
            ))

        # Methods
        for method in methods:
            ref_str = f" (uses: {', '.join(sorted(list(method['references'])))})" if method.get('references') else ""
            results.append(JsTsExtendedTag(
                rel_fname=rel_fname, fname=file_path,
                line=method["start"], end_line=method["end"],
                name=f"{method['name']}{ref_str}", kind="def", type_info="method"
            ))

        # Variables
        for var in variables:
            # Usage tracking not implemented for top-level variables in this pass
            results.append(JsTsExtendedTag(
                rel_fname=rel_fname, fname=file_path,
                line=var["start"], end_line=var["end"],
                name=var['name'], kind="def", type_info="variable"
            ))

        # Exports - make sure all exports are included in the results
        for exp in exports:
             # Avoid duplicating components/hooks/functions/vars already added if they were exported inline
             # This check is imperfect as names might clash or end lines differ slightly
             is_duplicate = False
             for block_list in [components, hooks, functions, variables]:
                 for block in block_list:
                     # Check if export refers to an already captured block
                     if block["start"] == exp["start"] and block["exported"]:
                         is_duplicate = True
                         break
                 if is_duplicate: break

             # Also avoid adding default exports that just reference an identifier if we captured that identifier
             if exp["name"].endswith("(as default)") and exp["type"] in ["component", "function", "class", "value"]:
                  potential_original_name = exp["name"].replace(" (as default)","")
                  for block_list in [components, hooks, functions, variables]:
                      for block in block_list:
                           if block["name"] == potential_original_name and block["start"] < exp["start"]: # Export default Identifier;
                                is_duplicate = True
                                break
                      if is_duplicate: break

             if not is_duplicate:
                results.append(JsTsExtendedTag(
                    rel_fname=rel_fname, fname=file_path,
                    line=exp["start"], end_line=exp["end"],
                    name=exp["name"], kind="def", type_info="export"
                ))


class JsTsParser(LanguageParser):
    """JavaScript/TypeScript language parser factory"""

    def create_element_detector(self) -> JsTsElementDetector:
        """Create a JS/TS-specific element detector"""
        return JsTsElementDetector()

    def get_file_extensions(self) -> List[str]:
        """Get the list of file extensions supported by this parser"""
        return [".js", ".jsx", ".ts", ".tsx"]

    def get_language_name(self) -> str:
        """Get the name of the language supported by this parser"""
        return "javascript/typescript"

# Register the parser
ParserRegistry.register(JsTsParser()) 