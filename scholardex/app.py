"""The ScholarDex facade: the only public entry point.

External code does:
    from scholardex import ScholarDex
    sdk = ScholarDex()
    papers = sdk.search("graph neural networks")
    paper = papers[0]
    paper.summary()   # or sdk.summarize(paper)
    paper.save()      # or sdk.save(paper)

Everything beneath — providers, AI pipeline, storage, config — is an
internal detail reachable only through this facade.
"""

from __future__ import annotations

from pathlib import Path

from . import exporters, storage
from .loader import Loader, parse_ref
from .models import Paper, PaperRef, SummaryResult
from .providers import search_all
from .summarizer import make_summarizer


class ScholarDex:
    def __init__(self) -> None:
        self._loader = Loader()
        self._summarizer = make_summarizer()

    # -- lookup ------------------------------------------------------------
    def search(self, query: str, limit: int = 5) -> list[Paper]:
        """Search all sources; provider failures degrade silently."""
        papers = search_all(query, limit)
        for paper in papers:
            paper._bind_app(self)
        return papers

    def load(self, identifier: str) -> Paper:
        """Resolve any identifier (URL, DOI, arXiv ID, PDF path) to a Paper."""
        ref = parse_ref(identifier)
        paper = self._loader.load(ref)
        paper._bind_app(self)
        return paper

    def summarize(self, paper: Paper) -> SummaryResult:
        """Summarize a paper with the configured AI model."""
        return self._summarizer.summarize(paper)

    # -- persistence -------------------------------------------------------
    def save(self, paper: Paper, result: SummaryResult) -> Path:
        """Save a paper + its summary to the library."""
        return storage.save_paper(paper, result)

    def save_paper(self, paper: Paper) -> Path:
        """Summarize and save a paper in one call."""
        return storage.save_paper(paper, self.summarize(paper))

    def library(self) -> list[dict]:
        """List saved papers, newest first."""
        return storage.list_papers()

    def export(self, format_name: str = "md") -> Path:
        """Export the library as 'md', 'json', or 'all'."""
        return exporters.export(format_name)
