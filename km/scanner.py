"""扫描器：遍历仓库，发现所有文章。"""
from __future__ import annotations

import os
from pathlib import Path

from .config import ROOT, SKIP_DIRS, SKIP_MD
from .models import Article


def _detect_source_area(rel_path: str) -> str:
    parts = rel_path.split(os.sep)
    if not parts:
        return "root"
    first = parts[0]
    if first == "2026":
        return "inbox"
    if first in ("aiops", "gpu-tpu", "mem"):
        return first
    return "root"


def scan_articles(root: Path | None = None) -> list[Article]:
    """遍历目录，每个 .md 文件视为一篇文章。

    规则：
    - 跳过 SKIP_DIRS（.git/images/km 等）
    - 跳过 SKIP_MD（INDEX.md/README.md/生成物等）
    - 若 md 文件名与所在目录名相同或是 index.md，文章路径取目录；
      否则文章路径取文件本身
    """
    root = root or ROOT
    articles: list[Article] = []
    seen: set[str] = set()

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS and not d.startswith(".")
        ]

        for f in sorted(filenames):
            if not f.endswith(".md"):
                continue
            if f in SKIP_MD:
                continue

            md_abs = os.path.join(dirpath, f)
            rel_md = os.path.relpath(md_abs, root)

            parent_name = os.path.basename(dirpath)
            stem = os.path.splitext(f)[0]

            if stem == parent_name or f.lower() == "index.md":
                article_path = os.path.relpath(dirpath, root)
                title = parent_name
            else:
                article_path = rel_md
                title = stem

            if article_path in seen:
                continue
            seen.add(article_path)

            articles.append(Article(
                path=article_path,
                title=title,
                md_path=md_abs,
                source_area=_detect_source_area(rel_md),
            ))

    articles.sort(key=lambda a: a.path)
    return articles
