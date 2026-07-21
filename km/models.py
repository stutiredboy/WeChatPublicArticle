"""数据模型。"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field


class Article(BaseModel):
    """扫描发现的一篇文章。"""
    path: str          # 相对仓库根的路径（文章所在目录或文件）
    title: str         # 文章标题（目录名或文件名）
    md_path: str       # markdown 文件绝对路径
    source_area: str   # 来源区域: inbox / aiops / gpu-tpu / mem / root


class ArticleMeta(BaseModel):
    """LLM 提取 + 分类后的文章元数据。"""
    path: str
    title: str
    source_area: str
    summary: str = Field(description="1-2 句中文摘要")
    primary_category: str = Field(description="taxonomy 一级分类 id")
    primary_category_name: str = ""
    sub_topic: str = Field(description="二级细分主题，LLM 自由命名")
    article_type: str = Field(description="文章类型枚举之一")
    keywords: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1, description="分类置信度 0-1")
    reason: str = Field(description="一句话说明为何归此类")
    extracted_at: str = Field(default_factory=lambda: datetime.now().isoformat())
