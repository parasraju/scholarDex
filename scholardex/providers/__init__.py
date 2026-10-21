"""Provider registry for scholarDex.

A provider is any object exposing:

    name: str
    search(query, limit) -> list[Paper]
    can_resolve(ref) -> bool
    resolve(ref) -> Paper | None

Adding a provider = drop a module in `providers/` that calls
`register()`. The facade iterates the registry; there is no other
wiring to touch.
"""

from __future__ import annotations

import logging
from typing import Protocol

from ..models import Paper

logger = logging.getLogger(__name__)


class SearchProvider(Protocol):
    name: str

    def search(self, query: str, limit: int) -> list[Paper]: ...

    def can_resolve(self, ref: "PaperRef") -> bool: ...

    def resolve(self, ref: "PaperRef") -> Paper | None: ...


_REGISTRY: dict[str, SearchProvider] = {}


def register(provider: SearchProvider) -> SearchProvider:
    _REGISTRY[provider.name] = provider
    return provider


def providers() -> list[SearchProvider]:
    return list(_REGISTRY.values())


def search_all(query: str, limit: int = 5) -> list[Paper]:
    """Search every provider concurrently using ThreadPoolExecutor,
    merging, deduping, and ranking results by citation count and year.

    Provider failures (including scholarly/scraping errors) are logged and
    swallowed here: callers see the outcome, never the provider internals.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    papers: list[Paper] = []
    prov_list = providers()
    if not prov_list:
        return papers

    def _search_one(provider: SearchProvider) -> list[Paper]:
        try:
            return provider.search(query, limit)
        except Exception:
            logger.exception("provider '%s' search failed", provider.name)
            return []

    with ThreadPoolExecutor(max_workers=len(prov_list)) as executor:
        futures = {executor.submit(_search_one, p): p for p in prov_list}
        for future in as_completed(futures):
            try:
                res = future.result()
                if res:
                    papers.extend(res)
            except Exception:
                provider = futures[future]
                logger.exception("provider '%s' search execution failed", provider.name)

    deduped = _dedupe(papers)
    return _rank(deduped)


def _rank(papers: list[Paper]) -> list[Paper]:
    """Sort papers by citation count (descending) and year (descending).

    None values for citations or year are treated as 0 / 0 (or lowest priority).
    """
    return sorted(
        papers,
        key=lambda p: (p.citations if p.citations is not None else 0, p.year if p.year is not None else 0),
        reverse=True,
    )


def resolve(ref: "PaperRef") -> Paper | None:
    """Resolve a reference using the first provider that claims it."""
    for provider in providers():
        if not provider.can_resolve(ref):
            continue
        try:
            paper = provider.resolve(ref)
        except Exception:
            logger.exception("provider '%s' resolve failed", provider.name)
            continue
        if paper is not None:
            return paper
    return None


def _dedupe(papers: list[Paper]) -> list[Paper]:
    seen: set[str] = set()
    result: list[Paper] = []
    for p in papers:
        key = "".join(ch.lower() if ch.isalnum() else "" for ch in p.title)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(p)
    return result


from . import arxiv, crossref, scholar, semantic  # noqa: E402  (register on import)
