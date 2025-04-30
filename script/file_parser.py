#!/usr/bin/env python3
"""
多语言文件解析工具 (基于抽象工厂模式)

这个脚本使用抽象工厂设计模式，整合了原有三个文件解析器的功能：
- Python 文件解析
- Java 文件解析
- 前端文件解析 (JS/TS/JSX/TSX/HTML/CSS)

用法:
    python treesitter_multiparser.py [文件路径] [-v] [-l]

参数:
    [文件路径]  要解析的文件路径
    -v, --verbose  显示详细信息
    -l, --list  列出支持的语言和文件扩展名
"""
import sys
from file_parser.main import main

if __name__ == "__main__":
    main() 