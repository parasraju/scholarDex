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
    """Search every provider, merging and deduping results.

    Provider failures are logged and swallowed here: callers see the
    outcome (fewer results), never the provider internals.
    """
    papers: list[Paper] = []
    for provider in providers():
        try:
            papers.extend(provider.search(query, limit))
        except Exception:
            logger.exception("provider '%s' search failed", provider.name)
    return _dedupe(papers)


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
