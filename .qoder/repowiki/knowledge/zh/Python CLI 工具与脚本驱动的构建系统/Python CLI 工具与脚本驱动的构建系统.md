---
kind: build_system
name: Python CLI 工具与脚本驱动的构建系统
category: build_system
scope:
    - '**'
source_files:
    - km/cli.py
    - km/config.py
    - km/__main__.py
    - scripts/build_mem_guide_pdf.py
    - taxonomy.yaml
    - .env
---

该仓库采用轻量级 Python CLI 工具驱动的知识管理构建系统，没有传统意义上的 Makefile、Dockerfile 或 CI/CD 流水线。核心构建流程由 Python 脚本和命令行工具组成：

**主要构建组件：**
- `km` Python 包提供完整的 CLI 工具集（使用 click 框架），支持文章扫描、分类提取、索引生成等命令
- `scripts/build_mem_guide_pdf.py` 专门用于将 Markdown 指南转换为 PDF 文档，使用 reportlab 和 pandoc 进行格式转换
- 配置文件通过 `.env` 文件管理 LLM API 密钥和配置参数

**构建流程特点：**
- 无自动化构建脚本，所有操作通过直接运行 Python 命令执行
- 依赖外部工具：pandoc（Markdown 转 HTML）、reportlab（PDF 生成）、beautifulsoup4（HTML 解析）
- 使用 `knowledge_index.json` 作为中间产物存储文章元数据
- 分类体系通过 `taxonomy.yaml` 配置文件定义，支持灵活调整

**环境要求：**
- Python 虚拟环境建议使用 `~/.venv`
- 需要安装 beautifulsoup4、reportlab、click、httpx 等 Python 依赖
- 系统需安装 pandoc 命令行工具
- LLM 服务通过环境变量配置（KM_LLM_BASE_URL、KM_LLM_MODEL、KM_LLM_API_KEY）

**输出产物：**
- `INDEX.md`：生成的知识库索引文档
- `knowledge_index.json`：结构化文章元数据
- PDF 文档：通过专用脚本从 Markdown 生成

该系统设计简洁，专注于个人知识管理场景，没有复杂的依赖管理和版本控制机制。