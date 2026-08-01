"""Crossref provider (DOI resolution + bibliographic search)."""

from __future__ import annotations

import re

import requests

from ..models import Paper, PaperRef
from . import register

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def _clean_year(raw) -> int | None:
    if not raw:
        return None
    parts = (raw.get("date-parts") or [[]])[0]
    return parts[0] if parts and parts[0] else None


def _clean_abstract(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _from_item(item: dict, source: str = "Crossref") -> Paper:
    title = item.get("title") or [""]
    return Paper(
        title=title[0],
        authors=[
            a.get("family", "") + " " + a.get("given", "")
            for a in item.get("author", [])
        ],
        year=_clean_year(
            item.get("issued") or item.get("published-print") or item.get("published-online")
        ),
        source=source,
        url=item.get("URL", ""),
        doi=item.get("DOI", ""),
        abstract=_clean_abstract(item.get("abstract", "")),
    )


class CrossrefProvider:
    name = "crossref"

    def search(self, query: str, limit: int = 5) -> list[Paper]:
        try:
            resp = requests.get(
                "https://api.crossref.org/works",
                params={
                    "query": query,
                    "rows": limit,
                    "select": "title,author,issued,DOI,abstract,URL",
                },
                timeout=15,
                headers={"User-Agent": USER_AGENT},
            )
            resp.raise_for_status()
        except Exception:
            return []
        items = resp.json().get("message", {}).get("items", [])
        return [_from_item(item) for item in items]

    def can_resolve(self, ref: PaperRef) -> bool:
        return ref.kind == "doi"

    def resolve(self, ref: PaperRef) -> Paper | None:
        try:
            resp = requests.get(
                f"https://api.crossref.org/works/{ref.value}",
                timeout=20,
                headers={"User-Agent": USER_AGENT},
            )
            resp.raise_for_status()
        except Exception:
            return None
        return _from_item(resp.json().get("message", {}))


register(CrossrefProvider())
