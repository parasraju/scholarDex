"""Google Scholar provider.

Uses the `scholarly` library. Scholar has no API and can block
scraping; failures are expected and handled by the registry, which
silently moves on to other providers.
"""

from __future__ import annotations

import re

from ..models import Paper, PaperRef
from . import register


def _clean_year(raw) -> int | None:
    if raw is None:
        return None
    match = re.search(r"(19|20)\d{2}", str(raw))
    return int(match.group(0)) if match else None


class ScholarProvider:
    name = "scholar"

    def search(self, query: str, limit: int = 5) -> list[Paper]:
        try:
            import sys
            # Avoid hanging if scholarly or its dependencies block or misbehave
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                from scholarly import scholarly
        except Exception:
            return []

        papers: list[Paper] = []
        try:
            for entry in scholarly.search_pubs(query):
                bib = entry.get("bib", {})
                url = entry.get("eprint_url") or entry.get("pub_url") or ""
                papers.append(
                    Paper(
                        title=bib.get("title", ""),
                        authors=bib.get("author", []),
                        year=_clean_year(bib.get("pub_year") or entry.get("year")),
                        source="Google Scholar",
                        url=url,
                        citations=entry.get("num_citations", 0),
                        abstract=bib.get("abstract", ""),
                    )
                )
                if len(papers) >= limit:
                    break
        except Exception:
            return []
        return papers

    def can_resolve(self, ref: PaperRef) -> bool:
        return False

    def resolve(self, ref: PaperRef) -> Paper | None:
        return None


register(ScholarProvider())
