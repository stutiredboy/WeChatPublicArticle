---
kind: logging_system
name: 日志系统 — 基于 Rich 控制台输出的轻量 CLI 日志
category: logging_system
scope:
    - '**'
source_files:
    - km/cli.py
    - km/extractor.py
    - km/writer.py
---

本仓库是一个微信公众号技术文章知识库与自动分类工具，核心代码集中在 `km/` 目录下。该仓库**没有使用任何结构化日志框架**（如 Python 标准库 `logging`、loguru、structlog 等），而是采用了一种极简的“控制台输出即日志”的方式：所有运行信息通过 `rich.console.Console` 直接打印到终端，作为唯一的输出与调试手段。

### 1. 使用的系统与方式
- **无专用日志框架**：全仓未导入 `logging`、`loguru`、`structlog`、`logzero`、`logbook` 等任何日志库。
- **Rich Console 作为唯一输出通道**：`cli.py` 中定义全局 `console = Console()`，所有状态提示、错误、统计表格均通过 `console.print(...)` 输出，并使用 Rich 的 Markdown 风格样式（如 `[green]已写出[/green]`、`[red]JSON 解析失败: {e}[/red]`）来区分信息类型。
- **CLI 命令级反馈**：每个 `click` 子命令在执行前后通过 `console.print` 报告进度、结果和错误，例如 `extract` 命令中的 `console.print(f"[cyan]待处理 {len(todo)} 篇[/cyan]")`、`add` 命令中的 `console.print(f"[yellow]跳过：路径不在扫描结果中[/yellow] {path}")`。
- **标准错误退出码**：当出现致命错误（如 JSON 解析失败、缺少索引文件）时，通过 `sys.exit(1)` 返回非零退出码，供外部调用者判断。

### 2. 关键文件与位置
- `km/cli.py`：全部用户可见的输出都集中在此，包括 scan/todo/add/extract/index/show/stats 等命令的控制台输出。
- `km/extractor.py`：LLM 调用失败时的兜底逻辑通过 `_fallback_meta` 返回低置信度元数据，并在 `cli.py` 中以黄色提示显示失败数量。
- `km/writer.py`：写入 `knowledge_index.json` 和 `INDEX.md` 后通过 `cli.py` 中的 `_save_all` 统一打印确认消息。
- `km/scanner.py`、`km/config.py`、`km/models.py`、`km/taxonomy.py`：纯数据处理模块，不产生任何日志输出。

### 3. 架构与约定
- **无日志级别**：没有 debug/info/warning/error 分级，仅靠 Rich 样式颜色（green/red/yellow/cyan/dim）在视觉上区分成功、错误、警告、信息等。
- **无结构化字段**：输出为人类可读的富文本字符串，而非 JSON 或键值对格式，无法被机器解析或聚合。
- **无日志文件输出**：所有输出直接打到 stdout/stderr，没有文件 sink、没有日志轮转、没有远程收集。
- **幂等性提示**：重复执行相同命令会给出一致的提示（如“没有需要处理的新文章”、“没有待分类的文章”），便于人工判断状态。

### 4. 约定与约束
- **观察到的模式**：所有用户交互信息必须通过 `console.print` 输出，禁止使用 `print()` 裸函数；错误场景优先使用 `[red]...[/red]` 样式并配合 `sys.exit(1)`。
- **无强制约束机制**：仓库中没有 lint 规则、CI 检查或文档强制要求使用 Rich Console，但现有代码完全遵循这一约定。
- **可观测性局限**：由于缺乏结构化日志，无法进行日志聚合、搜索、告警或性能分析；调试依赖人工阅读终端输出。

总结：该仓库的“日志系统”本质上就是 Rich Console 控制台输出，简单直接，适合个人工具型 CLI 应用，但不具备企业级日志系统的结构化、可聚合、可配置等能力。