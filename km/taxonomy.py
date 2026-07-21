"""加载 taxonomy.yaml，供 extractor 构建 prompt。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Category:
    id: str
    name: str
    desc: str


@dataclass
class Taxonomy:
    categories: list[Category]
    article_types: list[str]

    def get_category(self, cid: str) -> Category | None:
        for c in self.categories:
            if c.id == cid:
                return c
        return None

    def category_ids(self) -> list[str]:
        return [c.id for c in self.categories]


def load_taxonomy(path: Path) -> Taxonomy:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    cats = [
        Category(id=c["id"], name=c["name"], desc=c["desc"].strip())
        for c in raw["categories"]
    ]
    types = list(raw.get("article_types", []))
    return Taxonomy(categories=cats, article_types=types)


def format_taxonomy_for_prompt(tax: Taxonomy) -> str:
    """生成给 LLM 看的 taxonomy 说明文本。"""
    lines = ["可选一级分类（必须从中选一个 primary_category）：", ""]
    for c in tax.categories:
        desc_oneline = " ".join(c.desc.split())
        lines.append(f"- id={c.id} | 名称={c.name} | 范围: {desc_oneline}")
    lines.append("")
    lines.append("可选文章类型（article_type 选一）：")
    for t in tax.article_types:
        lines.append(f"- {t}")
    return "\n".join(lines)
