"""配置加载：从 .env 读 LLM 配置，确定项目路径。"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip("'\"")
        os.environ.setdefault(k, v)


_load_env(ROOT / ".env")


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    model: str
    api_key: str

    @classmethod
    def from_env(cls) -> "LLMConfig":
        base = os.environ.get("KM_LLM_BASE_URL", "https://api.openai.com/v1")
        model = os.environ.get("KM_LLM_MODEL", "gpt-4o-mini")
        key = os.environ.get("KM_LLM_API_KEY", "")
        if not key:
            raise RuntimeError(
                "KM_LLM_API_KEY 未设置。请复制 .env.example 为 .env 并填写。"
            )
        return cls(base_url=base.rstrip("/"), model=model, api_key=key)


TAXONOMY_PATH = ROOT / "taxonomy.yaml"
INDEX_JSON = ROOT / "knowledge_index.json"
INDEX_MD = ROOT / "INDEX.md"

SKIP_DIRS = {
    ".git", ".gstack", ".playwright-mcp", ".claude", ".opencode",
    "scripts", "images", "node_modules", "__pycache__", "km",
    ".DS_Store",
}

SKIP_MD = {
    "INDEX.md", "README.md", "CLAUDE.md", "AGENTS.md",
    "非全日制MEM毕业论文实战指南.md",  # gitignored 生成物
    "AI赋能运维质量_MEM论文选题建议报告.md",  # gitignored
}
