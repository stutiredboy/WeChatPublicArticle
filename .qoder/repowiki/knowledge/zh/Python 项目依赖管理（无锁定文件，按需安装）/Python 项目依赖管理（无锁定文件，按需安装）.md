---
kind: dependency_management
name: Python 项目依赖管理（无锁定文件，按需安装）
category: dependency_management
scope:
    - '**'
source_files:
    - km/cli.py
    - km/extractor.py
    - km/models.py
    - km/config.py
    - scripts/build_mem_guide_pdf.py
---

本仓库是一个以 Markdown 文章为主的知识库，核心可执行代码集中在 `km/` 包（Python CLI 工具），以及 `scripts/build_mem_guide_pdf.py` 一个独立的 PDF 生成脚本。该仓库**没有使用任何 Python 包管理器或锁定文件**来声明和管理第三方依赖：不存在 `requirements.txt`、`pyproject.toml`、`setup.py`、`Pipfile`、`poetry.lock`、`environment.yml`、`conda` 环境文件或 `go.mod`/`package.json` 等任何依赖清单。因此无法通过工具自动推断依赖版本与来源。

从源码中可直接观察到的运行时依赖如下：
- `km/cli.py`、`km/extractor.py` 等模块直接 `import click`、`httpx`、`rich.console.Console`、`rich.table.Table`；`km/models.py` 使用 `pydantic` 定义数据模型。
- `km/config.py` 仅使用标准库 `os`、`pathlib.Path`、`dataclasses.dataclass`。
- `scripts/build_mem_guide_pdf.py` 在 `try/except ModuleNotFoundError` 中显式检查并提示安装 `beautifulsoup4` 和 `reportlab`（以及 `pillow`），并通过 `subprocess` 调用外部工具 `pandoc` 完成 Markdown→HTML 转换。

依赖获取方式与约束：
- 所有依赖均为**运行时动态导入**，未在任何清单文件中声明；使用者需自行通过 `pip install` 安装所需包。
- LLM 客户端配置通过 `.env` 文件中的 `KM_LLM_BASE_URL`、`KM_LLM_MODEL`、`KM_LLM_API_KEY` 环境变量注入（见 `config.py` 的 `LLMConfig.from_env`），密钥不入库。
- 脚本对缺失依赖采取“运行时报错 + 打印安装提示”的策略（如 `build_mem_guide_pdf.py` 中对 `beautifulsoup4`、`reportlab`、`pillow` 的 `ModuleNotFoundError` 捕获），而非在构建阶段拦截。
- 外部二进制依赖 `pandoc` 通过 `subprocess.check_output` 调用，要求宿主系统已安装且 PATH 中可用。

由于缺乏统一的依赖声明与锁定机制，本仓库的依赖管理处于**手工维护**状态：新增依赖需在源码 import 处引入，并在 README 或文档中补充安装说明，否则 CI/本地环境可能因缺少包而失败。