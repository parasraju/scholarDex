"""Turn any user identifier (URL, DOI, arXiv ID, or local PDF path)
into a fully-populated `Paper`.

All identifier sniffing lives here; providers never see raw user
input. The chunking policy stays in the summarizer, not here.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import providers
from .errors import ResolutionError
from .models import Paper, PaperRef

_ARXIV_URL_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d+(?:v\d+)?)", re.I)
_ARXIV_ID_RE = re.compile(r"\d{4}\.\d+(?:v\d+)?")
_DOI_RE = re.compile(r"10\.\d{4,9}/\S+")

_MAX_PDF_PAGES = 100


def parse_ref(identifier: str) -> PaperRef:
    """Classify a user-supplied identifier into a normalized PaperRef."""
    value = identifier.strip()
    if not value:
        raise ResolutionError("Empty identifier.")

    path = Path(value)
    if path.exists() and path.is_file():
        return PaperRef(kind="file", value=value)

    match = _ARXIV_URL_RE.search(value)
    if match:
        return PaperRef(kind="arxiv", value=match.group(1))

    if _ARXIV_ID_RE.fullmatch(value):
        return PaperRef(kind="arxiv", value=value)

    if "arxiv.org" in value.lower():
        return PaperRef(kind="arxiv", value=value.rstrip("/").split("/")[-1])

    match = _DOI_RE.search(value)
    if match:
        return PaperRef(kind="doi", value=match.group(0))

    if value.lower().startswith(("http://", "https://")):
        return PaperRef(kind="url", value=value)

    return PaperRef(kind="doi", value=value)


class Loader:
    def load(self, ref: PaperRef) -> Paper:
        if ref.kind == "file":
            return self._from_pdf(Path(ref.value))
        paper = providers.resolve(ref)
        if paper is None:
            raise ResolutionError(f"Could not find a paper for '{ref.value}'.")
        return paper

    def _from_pdf(self, path: Path) -> Paper:
        text = _extract_pdf(path)
        if not text.strip():
            raise ResolutionError(
                f"No extractable text in '{path.name}' (scanned PDFs are not supported)."
            )
        return Paper(
            title=path.stem,
            source=f"PDF ({path.name})",
            url=str(path),
            full_text=text,
        )


def _extract_pdf(path: Path) -> str:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ResolutionError("PyMuPDF is not installed. Run `pip install PyMuPDF`.")

    try:
        doc = fitz.open(str(path))
    except Exception as e:
        raise ResolutionError(f"Could not open PDF: {e}")

    try:
        if doc.page_count > _MAX_PDF_PAGES:
            raise ResolutionError(
                f"PDF has {doc.page_count} pages; refusing to read more than {_MAX_PDF_PAGES}."
            )
        chunks: list[str] = []
        for page in doc:
            text = page.get_text("text")
            if text and text.strip():
                chunks.append(text.strip())
    finally:
        doc.close()
    return "\n".join(chunks)
