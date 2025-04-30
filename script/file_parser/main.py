#!/usr/bin/env python3
"""
Main module for language-specific file parsing using the Abstract Factory pattern.
"""
import argparse
import sys
from pathlib import Path

from .base_parser import ParserRegistry
from .common_utils import get_tags_raw, console, display_file_structure

# Import language-specific parsers to register them
from . import python_parser
from . import java_parser
from . import css_parser
from . import js_ts_parser
from . import html_parser
from . import markdown_parser
from . import properties_parser
from . import json_parser
from . import xml_parser
from . import yaml_parser


def parse_file(file_path: str, verbose: bool = False):
    """Parse a single file using the appropriate parser.
    
    Args:
        file_path: Path to the file to analyze
        verbose: Whether to print verbose information
    """
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        console.print(f"[bold red]错误: 文件不存在: {file_path}[/bold red]")
        return

    # Get the appropriate parser for the file
    parser = ParserRegistry.get_parser_for_file(file_path)
    if not parser:
        console.print(f"[bold yellow]警告: 不支持的文件类型: {path.suffix}[/bold yellow]")
        return
        
    # Create the detector for the file type
    detector = parser.create_element_detector()
    
    # Detect elements
    elements = detector.detect_elements(file_path, verbose)
    if verbose:
        console.print(f"检测到 {len(elements)} 个元素")
    
    # Display results
    display_file_structure(file_path, elements, detector, verbose)

def list_supported_languages():
    """List all supported languages and their file extensions"""
    console.print("[bold]支持的语言和文件扩展名:[/bold]")
    for lang_name in ParserRegistry.available_parsers():
        parser = ParserRegistry.get_parser_by_name(lang_name)
        if not parser:
            continue
        
        exts = ", ".join(parser.get_file_extensions())
        console.print(f"- [bold]{lang_name}[/bold]: {exts}")

def main():
    """Main entry point for CLI"""
    parser = argparse.ArgumentParser(description="多语言文件解析 (基于抽象工厂模式)")
    parser.add_argument("file_path", help="要解析的文件路径", nargs="?")
    parser.add_argument("-v", "--verbose", action="store_true", help="显示详细信息")
    parser.add_argument("-l", "--list", action="store_true", help="列出支持的语言和文件扩展名")
    args = parser.parse_args()

    console.print("[bold]多语言文件解析 (基于抽象工厂模式)[/bold]")
    console.print("-" * 50)
    
    if args.list:
        list_supported_languages()
        return
        
    if not args.file_path:
        parser.print_help()
        return
    
    parse_file(args.file_path, args.verbose)

if __name__ == "__main__":
    main() 