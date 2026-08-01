"""arXiv provider."""

from __future__ import annotations

import arxiv

from ..models import Paper, PaperRef
from . import register


class ArxivProvider:
    name = "arxiv"

    def search(self, query: str, limit: int = 5) -> list[Paper]:
        papers: list[Paper] = []
        try:
            client = arxiv.Client()
            search = arxiv.Search(
                query=query,
                max_results=limit,
                sort_by=arxiv.SortCriterion.Relevance,
            )
            for result in client.results(search):
                papers.append(
                    Paper(
                        title=result.title.replace("\n", " ").strip(),
                        authors=[a.name for a in result.authors],
                        year=result.published.year,
                        source="arXiv",
                        url=result.entry_id,
                        arxiv_id=result.entry_id.split("/abs/")[-1],
                        abstract=result.summary.replace("\n", " ").strip(),
                    )
                )
        except Exception:
            return []
        return papers

    def can_resolve(self, ref: PaperRef) -> bool:
        return ref.kind == "arxiv"

    def resolve(self, ref: PaperRef) -> Paper | None:
        try:
            client = arxiv.Client()
            search = arxiv.Search(id_list=[ref.value])
            result = next(client.results(search))
        except Exception:
            return None
        return Paper(
            title=result.title.replace("\n", " ").strip(),
            authors=[a.name for a in result.authors],
            year=result.published.year,
            source="arXiv",
            url=result.entry_id,
            arxiv_id=ref.value,
            abstract=result.summary.replace("\n", " ").strip(),
            full_text=result.summary.replace("\n", " ").strip(),
        )


register(ArxivProvider())
