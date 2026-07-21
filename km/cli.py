"""km CLI 入口。

两种工作模式：
  1. Agent 驱动（推荐，在 opencode 中使用，无需 API key）：
     km todo [--limit N]        # 列出待分类文章
     km add --file <json>       # 导入 agent 产出的分类结果
     km index                   # 重新生成 INDEX.md
  2. 独立模式（可选，需配 .env，用于 cron/批处理）：
     km extract [--limit N]     # 自调 LLM 提取元数据

通用命令：
  km scan [--area X]            # 列出所有文章
  km show <category>            # 按分类查看
  km stats                      # 统计概览
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click
import httpx
from rich.console import Console
from rich.table import Table

from .config import INDEX_JSON, INDEX_MD, LLMConfig, ROOT, TAXONOMY_PATH
from .extractor import extract_one
from .models import ArticleMeta
from .scanner import scan_articles
from .taxonomy import load_taxonomy
from .writer import write_index

console = Console()


def _load_existing() -> dict[str, ArticleMeta]:
    """加载已有索引，返回 path -> meta 的字典。"""
    if not INDEX_JSON.exists():
        return {}
    data = json.loads(INDEX_JSON.read_text(encoding="utf-8"))
    return {a["path"]: ArticleMeta(**a) for a in data.get("articles", [])}


def _save_all(metas: list[ArticleMeta], tax) -> None:
    write_index(metas, tax)
    console.print(f"[green]已写出[/green] {INDEX_JSON.name} + {INDEX_MD.name}")


@click.group()
def cli():
    """知识管理 Agent - 对本仓库文章分门别类。"""
    pass


@cli.command()
@click.option("--area", default=None, help="只看某来源区域: inbox/aiops/gpu-tpu/mem")
def scan(area):
    """列出发现的文章。"""
    articles = scan_articles()
    if area:
        articles = [a for a in articles if a.source_area == area]

    table = Table(title=f"发现 {len(articles)} 篇文章")
    table.add_column("区域", style="cyan", width=8)
    table.add_column("标题", style="white")
    table.add_column("路径", style="dim")
    for a in articles:
        table.add_row(a.source_area, a.title, a.path)
    console.print(table)


@cli.command()
@click.option("--limit", default=0, help="最多列出 N 篇（0=全部）")
@click.option("--area", default=None, help="只看某来源区域")
@click.option("--json", "as_json", is_flag=True, help="输出 JSON（供 agent 消费）")
def todo(limit, area, as_json):
    """列出尚未分类（不在索引中）的文章。

    agent 驱动模式的核心入口：先跑这个看有哪些待处理，再读文章、分类、调 km add。
    """
    articles = scan_articles()
    if area:
        articles = [a for a in articles if a.source_area == area]

    existing = _load_existing()
    todo_list = [a for a in articles if a.path not in existing]
    if limit:
        todo_list = todo_list[:limit]

    if not todo_list:
        console.print(f"[green]没有待分类的文章[/green]（已索引 {len(existing)} 篇）")
        return

    if as_json:
        import json as _json
        out = [{"path": a.path, "title": a.title, "source_area": a.source_area,
                "md_path": a.md_path} for a in todo_list]
        console.print_json(_json.dumps(out, ensure_ascii=False))
        return

    console.print(f"[cyan]待分类 {len(todo_list)} 篇[/cyan]（已索引 {len(existing)} 篇）\n")
    table = Table(title="待分类文章")
    table.add_column("#", style="dim", width=4)
    table.add_column("区域", style="cyan", width=8)
    table.add_column("标题", style="white")
    table.add_column("md_path", style="dim")
    for i, a in enumerate(todo_list, 1):
        table.add_row(str(i), a.source_area, a.title, a.md_path)
    console.print(table)


@cli.command()
@click.option("--file", "file_path", default=None,
              help="JSON 文件路径（数组）。不传则从 stdin 读。")
def add(file_path):
    """导入 agent 产出的分类结果（JSON 数组）。

    JSON 格式（每项）：
      {"path": "...", "summary": "...", "primary_category": "ai-agent",
       "sub_topic": "...", "article_type": "...", "keywords": [...],
       "confidence": 0.9, "reason": "..."}

    path 必须匹配 km todo 列出的路径；title/source_area 会自动从扫描补全。
    """
    raw = _read_input(file_path)
    try:
        items = json.loads(raw)
    except json.JSONDecodeError as e:
        console.print(f"[red]JSON 解析失败: {e}[/red]")
        sys.exit(1)

    if not isinstance(items, list):
        items = [items]

    tax = load_taxonomy(TAXONOMY_PATH)
    valid_ids = set(tax.category_ids())
    valid_types = set(tax.article_types)

    articles = {a.path: a for a in scan_articles()}
    existing = _load_existing()
    metas = dict(existing)

    added, skipped = 0, 0
    for item in items:
        path = item.get("path", "")
        article = articles.get(path)
        if not article:
            console.print(f"[yellow]跳过：路径不在扫描结果中[/yellow] {path}")
            skipped += 1
            continue

        cat_id = item.get("primary_category", "")
        if cat_id not in valid_ids:
            console.print(f"[yellow]跳过：未知分类 '{cat_id}'[/yellow] {path}")
            skipped += 1
            continue

        cat = tax.get_category(cat_id)
        atype = item.get("article_type", "")
        if atype and atype not in valid_types:
            atype = ""  # 容忍，不跳过

        metas[path] = ArticleMeta(
            path=path,
            title=article.title,
            source_area=article.source_area,
            summary=item.get("summary", ""),
            primary_category=cat_id,
            primary_category_name=cat.name if cat else "",
            sub_topic=item.get("sub_topic", ""),
            article_type=atype,
            keywords=item.get("keywords", []),
            confidence=float(item.get("confidence", 0.8)),
            reason=item.get("reason", ""),
        )
        added += 1

    _save_all(list(metas.values()), tax)
    console.print(f"[green]导入 {added} 篇[/green]，跳过 {skipped} 篇，"
                  f"索引总计 {len(metas)} 篇")


def _read_input(file_path: str | None) -> str:
    if file_path:
        return Path(file_path).read_text(encoding="utf-8")
    if sys.stdin.isatty():
        console.print("[red]请用 --file 指定 JSON 文件，或通过管道传入[/red]")
        sys.exit(1)
    return sys.stdin.read()


@cli.command()
@click.option("--limit", default=0, help="最多处理 N 篇（0=全部）")
@click.option("--force", is_flag=True, help="强制重新提取，忽略已有索引")
@click.option("--area", default=None, help="只处理某来源区域")
def extract(limit, force, area):
    """[独立模式] 自调 LLM 提取元数据。

    需要在 .env 配置 KM_LLM_API_KEY。在 opencode 中通常不需要这个命令——
    agent 本身就是 LLM，用 `km todo` + `km add` 即可。
    """
    cfg = LLMConfig.from_env()
    tax = load_taxonomy(TAXONOMY_PATH)
    articles = scan_articles()
    if area:
        articles = [a for a in articles if a.source_area == area]

    existing = {} if force else _load_existing()
    todo = [a for a in articles if a.path not in existing]
    if limit:
        todo = todo[:limit]

    if not todo:
        console.print("[yellow]没有需要处理的新文章[/yellow]")
        if existing:
            _save_all(list(existing.values()), tax)
        return

    console.print(f"[cyan]待处理 {len(todo)} 篇[/cyan]（已有 {len(existing)} 篇）")

    metas = dict(existing)
    client = httpx.Client(timeout=90)
    failed = 0
    with click.progressbar(todo, label="提取中") as bar:
        for article in bar:
            meta = extract_one(article, tax, cfg, client)
            metas[article.path] = meta
            if meta.confidence == 0:
                failed += 1
    client.close()

    _save_all(list(metas.values()), tax)
    if failed:
        console.print(f"[yellow]{failed} 篇提取失败，已兜底归入 life/待分类[/yellow]")


@cli.command()
def index():
    """从已有 knowledge_index.json 重新生成 INDEX.md（不调 LLM，不花钱）。"""
    if not INDEX_JSON.exists():
        console.print("[red]没有 knowledge_index.json，先跑 extract[/red]")
        sys.exit(1)
    tax = load_taxonomy(TAXONOMY_PATH)
    data = json.loads(INDEX_JSON.read_text(encoding="utf-8"))
    metas = [ArticleMeta(**a) for a in data.get("articles", [])]
    _save_all(metas, tax)


@cli.command()
@click.argument("category")
def show(category):
    """按分类 id 查看文章。"""
    if not INDEX_JSON.exists():
        console.print("[red]没有索引，先跑 extract[/red]")
        sys.exit(1)
    tax = load_taxonomy(TAXONOMY_PATH)
    cat = tax.get_category(category)
    if not cat:
        console.print(f"[red]未知分类: {category}[/red]")
        console.print(f"可选: {', '.join(tax.category_ids())}")
        sys.exit(1)

    data = json.loads(INDEX_JSON.read_text(encoding="utf-8"))
    items = [ArticleMeta(**a) for a in data["articles"]
             if a["primary_category"] == category]
    items.sort(key=lambda m: (m.sub_topic, m.title))

    console.print(f"\n[bold]{cat.name}[/bold] - {len(items)} 篇\n")
    cur = None
    for m in items:
        if m.sub_topic != cur:
            cur = m.sub_topic
            console.print(f"\n[cyan]{cur}[/cyan]")
        console.print(f"  {m.title} [{m.article_type}] conf={m.confidence:.1f}")
        console.print(f"    [dim]{m.summary}[/dim]")


@cli.command()
def stats():
    """统计概览。"""
    if not INDEX_JSON.exists():
        console.print("[red]没有索引，先跑 extract[/red]")
        sys.exit(1)
    tax = load_taxonomy(TAXONOMY_PATH)
    data = json.loads(INDEX_JSON.read_text(encoding="utf-8"))
    metas = [ArticleMeta(**a) for a in data["articles"]]

    table = Table(title=f"知识库统计 - 共 {len(metas)} 篇")
    table.add_column("分类", style="cyan")
    table.add_column("篇数", justify="right")
    table.add_column("平均置信度", justify="right")

    from collections import defaultdict
    by_cat = defaultdict(list)
    for m in metas:
        by_cat[m.primary_category].append(m)

    for cat in tax.categories:
        items = by_cat.get(cat.id, [])
        if not items:
            continue
        avg_conf = sum(i.confidence for i in items) / len(items)
        table.add_row(cat.name, str(len(items)), f"{avg_conf:.2f}")
    console.print(table)


def main():
    cli()


if __name__ == "__main__":
    main()
