# grep_search 工具使用指南

## 基本功能
grep_search 是一个基于文本的正则表达式搜索工具，用于在文件或目录中查找精确的模式匹配，使用 ripgrep 命令进行高效搜索。

## 必要参数
- `query`: 要搜索的正则表达式模式

## 可选参数
- `explanation`: 解释为什么使用此工具以及它如何有助于目标
- `case_sensitive`: 搜索是否区分大小写（布尔值）
- `include_pattern`: 要包含的文件的 Glob 模式（例如 "*.ts" 表示 TypeScript 文件）
- `exclude_pattern`: 要排除的文件的 Glob 模式

## 使用示例

```markdown
# 基本搜索
grep_search(
  query="function getUserData\\(",
  explanation="查找获取用户数据的函数定义"
)

# 带过滤器的搜索
grep_search(
  query="import React",
  case_sensitive=true,
  include_pattern="*.js",
  exclude_pattern="node_modules",
  explanation="查找所有JavaScript文件中导入React的语句"
)
```

## 最佳实践
1. 查询必须是有效的正则表达式，特殊字符需要转义（如 `\\(` 表示左括号）
2. 当我们知道确切的符号/函数名/字符串时，比语义搜索更精确
3. 对于查找特定字符串或模式的搜索非常有用
4. 结果将以 ripgrep 风格格式化，包括行号和内容
5. 为避免输出过多，结果上限为50个匹配项
6. 使用 include_pattern 或 exclude_pattern 按文件类型或特定路径过滤搜索范围 