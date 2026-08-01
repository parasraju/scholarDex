"""Local summary library: storage layout, index, save, list.

The on-disk format (`index.json` + one `.md` per paper) is hidden here.
Export is a separate concern (see exporters.py).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from . import config
from .errors import StorageError
from .models import Paper, SummaryResult, format_authors

LIBRARY_DIR = config.CONFIG_DIR / "library"
_INDEX_PATH = LIBRARY_DIR / "index.json"

_SLUG_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789- ")


def _slug(title: str, year: int | None = None) -> str:
    slug = "".join(c.lower() if c in _SLUG_CHARS else "-" for c in title)
    slug = "-".join(slug.split())
    slug = slug.strip("-")[:80] or "untitled"
    if year:
        slug = f"{year}-{slug}"
    return slug


def _ensure_dirs() -> None:
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)


def _load_index() -> dict:
    if _INDEX_PATH.exists():
        try:
            return json.loads(_INDEX_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            raise StorageError(f"Could not read library index: {e}") from e
    return {}


def _save_index(index: dict) -> None:
    _INDEX_PATH.write_text(json.dumps(index, indent=2, default=str), encoding="utf-8")


def save_paper(paper: Paper, result: SummaryResult) -> Path:
    """Persist a paper + its summary, returning the Markdown path."""
    _ensure_dirs()
    slug = _slug(paper.title, paper.year)
    md_path = LIBRARY_DIR / f"{slug}.md"
    date = datetime.now().strftime("%Y-%m-%d %H:%M")

    md = [
        f"# {paper.title}",
        "",
        f"- **Authors:** {format_authors(paper.authors)}",
        f"- **Year:** {paper.year or 'Unknown'}",
        f"- **Source:** {paper.source or 'Unknown'}",
        f"- **URL:** {paper.url or 'N/A'}",
        f"- **DOI:** {paper.doi or 'N/A'}",
        f"- **Added:** {date}",
        f"- **Model:** {result.model}",
        "",
        "---",
        "",
        result.summary,
        "",
    ]
    md_path.write_text("\n".join(md), encoding="utf-8")

    index = _load_index()
    index[slug] = {
        "title": paper.title,
        "year": paper.year,
        "source": paper.source,
        "url": paper.url,
        "doi": paper.doi,
        "citations": paper.citations,
        "added": date,
        "model": result.model,
        "file": str(md_path),
    }
    _save_index(index)
    return md_path


def list_papers() -> list[dict]:
    """Return saved papers, newest first."""
    index = _load_index()
    return sorted(
        index.values(),
        key=lambda meta: str(meta.get("year", "")),
        reverse=True,
    )


def index_path() -> Path:
    return _INDEX_PATH
