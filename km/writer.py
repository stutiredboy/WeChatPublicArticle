"""输出器：生成 knowledge_index.json + INDEX.md。"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from .config import INDEX_JSON, INDEX_MD
from .models import ArticleMeta
from .taxonomy import Taxonomy


def write_index(metas: list[ArticleMeta], tax: Taxonomy) -> tuple[Path, Path]:
    """写出 JSON 索引 + Markdown 可读索引，返回两个路径。"""
    _write_json(metas)
    _write_md(metas, tax)
    return INDEX_JSON, INDEX_MD


def _write_json(metas: list[ArticleMeta]) -> None:
    data = {
        "generated_at": datetime.now().isoformat(),
        "total": len(metas),
        "articles": [m.model_dump() for m in metas],
    }
    INDEX_JSON.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_md(metas: list[ArticleMeta], tax: Taxonomy) -> None:
    by_cat: dict[str, list[ArticleMeta]] = defaultdict(list)
    for m in metas:
        by_cat[m.primary_category].append(m)

    lines = [
        "# 知识库索引",
        "",
        f"> 自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
        f"共 {len(metas)} 篇 | 由 km Agent 分类",
        "",
        "## 总览",
        "",
        "| 分类 | 篇数 |",
        "|------|------|",
    ]
    for cat in tax.categories:
        count = len(by_cat.get(cat.id, []))
        if count:
            lines.append(f"| {cat.name} | {count} |")
    lines.append("")

    for cat in tax.categories:
        items = by_cat.get(cat.id, [])
        if not items:
            continue
        items.sort(key=lambda m: (m.sub_topic, m.title))
        lines.append(f"## {cat.name} ({len(items)})")
        lines.append("")
        lines.append(cat.desc.strip().split("\n")[0])
        lines.append("")

        cur_sub = None
        for m in items:
            if m.sub_topic != cur_sub:
                cur_sub = m.sub_topic
                lines.append(f"### {cur_sub}")
                lines.append("")
            stars = "★" * round(m.confidence) if m.confidence > 0 else "？"
            kws = "、".join(m.keywords) if m.keywords else "-"
            lines.append(f"- **{m.title}** [{m.article_type}] {stars}")
            lines.append(f"  - {m.summary}")
            lines.append(f"  - 关键词: {kws} | 路径: `{m.path}`")
            lines.append("")

    INDEX_MD.write_text("\n".join(lines), encoding="utf-8")
