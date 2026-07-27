---
kind: error_handling
name: Python CLI 工具的错误处理模式：异常捕获、降级与用户反馈
category: error_handling
scope:
    - '**'
source_files:
    - km/cli.py
    - km/config.py
    - km/extractor.py
    - km/scanner.py
    - km/writer.py
---

该仓库的 km Python CLI 工具采用轻量级的 Python 原生错误处理模式，没有定义专门的错误类型或统一的错误框架。主要特点如下：

**异常捕获策略**
- 文件读取使用 try/except Exception 包裹（extractor.py:26-29），失败时返回空字符串而非抛出异常
- JSON 解析使用具体的 json.JSONDecodeError 捕获（cli.py:127-131），提供友好的错误消息后退出
- LLM 调用使用通用 Exception 捕获并实现重试机制（extractor.py:91-132），最多重试2次，间隔递增

**降级与兜底机制**
- LLM 调用失败时通过 _fallback_meta() 函数将文章归入 "life" 分类，标记低置信度（confidence=0.0）
- 内容读取失败时直接返回空内容，由上层逻辑判断并跳过处理
- 分类 ID 无效时自动回退到 "life" 分类（extractor.py:110-114）

**配置验证**
- LLM 配置缺失时立即抛出 RuntimeError（config.py:40-42），阻止程序继续执行
- 环境变量验证在初始化阶段完成，避免运行时出现难以调试的问题

**用户反馈方式**
- 使用 Rich 库的 Console 输出彩色错误信息（[red]、[yellow]、[green] 标签）
- 关键错误通过 sys.exit(1) 终止程序，正常流程使用 console.print() 输出状态
- 进度条显示处理进度，失败统计在最后汇总输出

**设计原则**
- 优先保证程序健壮性而非精确的错误分类
- 外部依赖（文件系统、网络请求）的错误被吞掉并降级处理
- 用户输入错误通过明确的错误消息和退出码传达
- 不定义自定义异常类型，统一使用 Python 内置异常