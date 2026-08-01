"""Core data model for scholarDex.

`Paper` is deliberately deep: besides carrying metadata it knows how to
summarize, save, and cite itself by delegating to the `ScholarDex`
facade it was produced by. The facade injects itself via `_bind_app`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from .errors import SummaryError

if TYPE_CHECKING:
    from .app import ScholarDex


@dataclass
class SummaryResult:
    title: str
    summary: str
    model: str


@dataclass(frozen=True)
class PaperRef:
    """A normalized reference to a paper: arxiv id, DOI, URL, or file path."""

    kind: str  # "arxiv" | "doi" | "url" | "file" | "unknown"
    value: str


@dataclass
class Paper:
    title: str
    authors: list[str] = field(default_factory=list)
    year: Optional[int] = None
    source: str = ""
    url: str = ""
    doi: str = ""
    arxiv_id: str = ""
    citations: int = 0
    abstract: str = ""
    full_text: str = ""

    _app: Optional["ScholarDex"] = field(default=None, repr=False, compare=False)

    def _bind_app(self, app: "ScholarDex") -> None:
        self._app = app

    def summary(self) -> SummaryResult:
        """Summarize this paper with the configured AI model."""
        if self._app is None:
            raise SummaryError("This paper is not bound to a ScholarDex instance.")
        return self._app.summarize(self)

    def save(self) -> Path:
        """Summarize (if needed) and persist this paper to the library."""
        if self._app is None:
            raise SummaryError("This paper is not bound to a ScholarDex instance.")
        return self._app.save_paper(self)

    def citation(self, style: str = "APA") -> str:
        """Return a formatted citation in the given style."""
        return format_citation(self, style)


def format_authors(authors: list[str], limit: int | None = None) -> str:
    if not authors:
        return "Unknown"
    shown = ", ".join(authors[:limit] if limit else authors)
    if limit and len(authors) > limit:
        shown += " et al."
    return shown


def format_citation(paper: Paper, style: str = "APA") -> str:
    style = style.upper()
    authors = format_authors(paper.authors)
    year = str(paper.year) if paper.year else "n.d."
    title = paper.title or "Untitled"
    if style == "MLA":
        return f"{authors}. \"{title}.\" {year}."
    return f"{authors} ({year}). {title}."
