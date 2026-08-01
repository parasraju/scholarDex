"""Semantic Scholar provider."""

from __future__ import annotations

import re

import requests

from ..models import Paper, PaperRef
from . import register

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

_SEARCH_FIELDS = "title,authors,year,externalIds,abstract,citationCount,url"


def _from_item(item: dict) -> Paper:
    ids = item.get("externalIds") or {}
    return Paper(
        title=item.get("title", ""),
        authors=[a["name"] for a in item.get("authors", [])],
        year=item.get("year"),
        source="Semantic Scholar",
        url=item.get("url", ""),
        doi=ids.get("DOI", ""),
        arxiv_id=ids.get("ArXiv", ""),
        citations=item.get("citationCount", 0),
        abstract=item.get("abstract", "") or "",
    )


class SemanticProvider:
    name = "semantic"

    def search(self, query: str, limit: int = 5) -> list[Paper]:
        try:
            resp = requests.get(
                "https://api.semanticscholar.org/graph/v1/paper/search",
                params={"query": query, "limit": limit, "fields": _SEARCH_FIELDS},
                timeout=15,
                headers={"User-Agent": USER_AGENT},
            )
            resp.raise_for_status()
        except Exception:
            return []
        return [_from_item(item) for item in resp.json().get("data", [])]

    def can_resolve(self, ref: PaperRef) -> bool:
        return ref.kind == "url"

    def resolve(self, ref: PaperRef) -> Paper | None:
        title = _page_title(ref.value)
        if not title:
            return None
        try:
            resp = requests.get(
                "https://api.semanticscholar.org/graph/v1/paper/search/match",
                params={"query": title, "fields": _SEARCH_FIELDS},
                timeout=15,
                headers={"User-Agent": USER_AGENT},
            )
            resp.raise_for_status()
        except Exception:
            return None
        data = resp.json().get("data")
        if not data:
            return None
        return _from_item(data[0])


def _page_title(url: str) -> str:
    try:
        resp = requests.get(url, timeout=20, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
    except Exception:
        return ""
    match = re.search(r"<title[^>]*>(.*?)</title>", resp.text, re.I | re.S)
    if not match:
        return ""
    return match.group(1).strip().split("|")[0].strip()


register(SemanticProvider())
