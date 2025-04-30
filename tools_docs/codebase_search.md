# codebase_search 工具使用指南

## 基本功能
codebase_search 是一个语义搜索工具，用于在代码库中查找与搜索查询语义相关的代码片段。

## 必要参数
- `query`: 搜索查询，通常应该重用用户的原始查询内容

## 可选参数
- `explanation`: 解释为什么使用此工具以及它如何有助于目标
- `target_directories`: 要搜索的目录的 Glob 模式数组

## 使用示例

```markdown
codebase_search(
  query="如何实现用户认证功能",
  explanation="寻找与用户认证相关的代码实现",
  target_directories=["src/auth", "src/user"]
)
```

## 最佳实践
1. 尽可能重用用户的精确查询和措辞，因为这对语义搜索很有帮助
2. 如果知道可能包含相关代码的目录，使用 target_directories 参数限制搜索范围
3. 对于特定功能、函数或组件的搜索，此工具优于 grep_search、file_search 和 list_dir
4. 结果将显示与查询最相关的代码片段，包括文件路径和相关代码行 