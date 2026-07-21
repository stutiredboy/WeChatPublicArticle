"""提取器：调 LLM 读文章，产出分类元数据。

设计要点：
- 单次 LLM 调用同时完成「理解」+「归类」，省 token
- LLM 拿到 taxonomy 后选 primary_category（高阶固定）+ 自由命名 sub_topic（细分自动）
- 用 OpenAI 兼容接口，httpx 直连，不依赖 SDK
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import httpx

from .config import LLMConfig
from .models import Article, ArticleMeta
from .taxonomy import Taxonomy, format_taxonomy_for_prompt

MAX_CONTENT_CHARS = 6000


def _read_md_content(md_path: str, max_chars: int = MAX_CONTENT_CHARS) -> str:
    """读 markdown，去掉图片引用和多余空白，截断。"""
    try:
        text = Path(md_path).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"<img[^>]*>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n...(内容截断)"
    return text


def _build_prompt(article: Article, content: str, tax: Taxonomy) -> str:
    tax_text = format_taxonomy_for_prompt(tax)
    return f"""你是知识管理助手。阅读下面的文章，按给定分类法归类并提取元数据。

{tax_text}

要求：
1. primary_category 必须从上面的 id 列表中选一个，不可自创
2. sub_topic 自由命名（2-8 字），体现该文章在所属分类下的细分方向
3. summary 用中文，1-2 句，说清文章讲什么
4. keywords 3-5 个，中文为主
5. confidence 0-1，表示你对分类的把握
6. reason 一句话说明为何归此类

只返回 JSON，不要 markdown 代码块，不要多余解释。格式：
{{
  "summary": "...",
  "primary_category": "...",
  "sub_topic": "...",
  "article_type": "...",
  "keywords": ["...", "..."],
  "confidence": 0.0,
  "reason": "..."
}}

文章标题：{article.title}
文章路径：{article.path}
来源区域：{article.source_area}

文章内容：
---
{content}
---"""


def extract_one(
    article: Article,
    tax: Taxonomy,
    cfg: LLMConfig,
    client: httpx.Client | None = None,
    retries: int = 2,
) -> ArticleMeta:
    """对单篇文章调 LLM 提取元数据。"""
    content = _read_md_content(article.md_path)
    if not content.strip():
        return _fallback_meta(article, tax, "内容为空")

    prompt = _build_prompt(article, content, tax)
    own_client = client is None
    if own_client:
        client = httpx.Client(timeout=90)

    last_err = ""
    for attempt in range(retries + 1):
        try:
            resp = client.post(
                f"{cfg.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {cfg.api_key}"},
                json={
                    "model": cfg.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.2,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"].strip()
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            parsed = json.loads(text)

            cat = tax.get_category(parsed.get("primary_category", ""))
            if not cat:
                parsed["primary_category"] = "life"
                cat = tax.get_category("life")

            return ArticleMeta(
                path=article.path,
                title=article.title,
                source_area=article.source_area,
                summary=parsed.get("summary", ""),
                primary_category=cat.id,
                primary_category_name=cat.name,
                sub_topic=parsed.get("sub_topic", ""),
                article_type=parsed.get("article_type", ""),
                keywords=parsed.get("keywords", []),
                confidence=float(parsed.get("confidence", 0.5)),
                reason=parsed.get("reason", ""),
            )
        except Exception as e:
            last_err = str(e)[:200]
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
            continue

    if own_client:
        client.close()
    return _fallback_meta(article, tax, f"LLM 调用失败: {last_err}")


def _fallback_meta(article: Article, tax: Taxonomy, reason: str) -> ArticleMeta:
    """LLM 失败时的兜底，归入 life 并标记低置信度。"""
    cat = tax.get_category("life")
    return ArticleMeta(
        path=article.path,
        title=article.title,
        source_area=article.source_area,
        summary=f"(待人工补充) {reason}",
        primary_category="life",
        primary_category_name=cat.name if cat else "生活",
        sub_topic="待分类",
        article_type="",
        keywords=[],
        confidence=0.0,
        reason=reason,
    )
