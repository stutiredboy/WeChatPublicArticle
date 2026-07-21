---
name: km
description: |
  本仓库的知识管理 Agent。当用户说"分类新文章"/"更新知识库索引"/"看看有哪些新文章要分类"/
  "按分类查看文章"/"知识库统计"时触发。底层调用 km CLI（Python）做文件读写，
  分类理解由 agent（你）自己完成--不需要外部 API key。
  非破坏式，只生成 knowledge_index.json + INDEX.md，不移动文件。
  触发词：分类文章、更新索引、知识库统计、km。
---

# km - 知识管理 Agent

## 核心理念
**你就是 LLM。** 不需要配外部 API key。你（agent）读文章、理解内容、做分类，
CLI（km）只负责文件扫描和索引读写。两者分工：

| 角色 | 职责 |
|------|------|
| agent（你） | 读 markdown 内容 → 理解 → 按 taxonomy 分类 → 产出 JSON |
| km CLI | 扫描文件、校验分类、合并索引、生成 INDEX.md |

## 前置条件
- Python venv: `~/.venv`（已装 click/httpx/pydantic/PyYAML/rich）
- 分类法: `taxonomy.yaml`（用户可编辑高阶分类，你不可自创分类）

## 命令速查
所有命令用 `~/.venv/bin/python -m km` 运行：

| 意图 | 命令 |
|------|------|
| 看有哪些待分类 | `~/.venv/bin/python -m km todo` |
| 待分类(只要 inbox) | `~/.venv/bin/python -m km todo --area inbox` |
| 待分类(前 10 篇,JSON) | `~/.venv/bin/python -m km todo --limit 10 --json` |
| 导入分类结果 | `~/.venv/bin/python -m km add --file /tmp/batch.json` |
| 重新生成 INDEX.md | `~/.venv/bin/python -m km index` |
| 按分类查看 | `~/.venv/bin/python -m km show ai-agent` |
| 统计概览 | `~/.venv/bin/python -m km stats` |

## 可用分类 id（见 taxonomy.yaml）
ai-agent / aiops-sre / gpu-tpu / storage / network / datacenter / security /
mem-thesis / career / finance / industry / life

## 工作流程（用户说"分类新文章"时）

### 第 1 步：看待办
```bash
~/.venv/bin/python -m km todo --limit 10 --json
```
拿到待分类文章列表（含 md_path）。

### 第 2 步：读文章 + 分类（你来做）
用 read 工具并行读取这批文章的 markdown。对每篇，按 taxonomy.yaml 的分类法判断：
- primary_category：必须从 12 个固定 id 中选
- sub_topic：自由命名（2-8 字），体现细分方向
- summary：1-2 句中文
- article_type：从枚举选（技术深度/实战复盘/观点评论/教程指南/行业资讯/学术论文/方法论/生活随笔）
- keywords：3-5 个
- confidence：0-1
- reason：一句话

### 第 3 步：写 JSON + 导入
把分类结果写成 JSON 数组，写到临时文件：
```json
[
  {"path":"2026/07/...","summary":"...","primary_category":"ai-agent",
   "sub_topic":"CLI化","article_type":"观点评论","keywords":["CLI","Agent"],
   "confidence":0.9,"reason":"讨论Agent时代CLI的价值"}
]
```
然后导入：
```bash
~/.venv/bin/python -m km add --file /tmp/km_batch.json
```

### 第 4 步：重复
如果还有未分类文章，回到第 1 步继续（每批 10 篇左右）。

### 第 5 步：收尾
```bash
~/.venv/bin/python -m km stats
```
向用户展示分类统计，并告知 INDEX.md 已更新。

## 注意事项
- **每批控制在 10 篇以内**，避免 context 过大影响分类质量
- path 字段必须和 `km todo` 输出的 path 完全一致（包括文章所在目录或文件路径）
- 如果某篇实在无法判断，归入 `life`，confidence 设 0.3，sub_topic 设"待人工确认"
- 全量重分类（改了 taxonomy 后）：先删 knowledge_index.json，再重新跑流程
