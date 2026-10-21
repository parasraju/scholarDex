"""Library export to Markdown / JSON.

Storage format is read via storage's index; nothing here knows the
on-disk layout beyond `storage.LIBRARY_DIR` and `storage.index_path`.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import storage
from .errors import StorageError


def export(format_name: str) -> Path:
    """Export the library in the given format (``md``, ``json``, ``bib``, or ``all``)."""
    format_name = format_name.lower()
    if format_name == "json":
        return _export_json()
    if format_name == "bib" or format_name == "bibtex":
        return _export_bibtex()
    if format_name == "all":
        _export_json()
        _export_bibtex()
        return _export_markdown()
    if format_name == "md":
        return _export_markdown()
    raise StorageError(f"Unknown export format: {format_name}")


def _export_markdown() -> Path:
    papers = storage.list_papers()
    if not papers:
        raise StorageError("No summaries in the library yet.")

    lines = ["# scholarDex Library", ""]
    for meta in papers:
        path = Path(meta.get("file", ""))
        if not path.exists():
            continue
        body = path.read_text(encoding="utf-8")
        lines.append(body)
        lines.append("")
        lines.append("---")
        lines.append("")

    out = storage.LIBRARY_DIR / "library.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def _export_json() -> Path:
    index = _load_index_raw()
    out = storage.LIBRARY_DIR / "library.json"
    out.write_text(json.dumps(index, indent=2, default=str), encoding="utf-8")
    return out


def _export_bibtex() -> Path:
    index = _load_index_raw()
    if not index:
        raise StorageError("No summaries in the library yet.")

    entries = []
    for slug, meta in index.items():
        title = meta.get("title", "Untitled")
        year = meta.get("year", "")
        source = meta.get("source", "")
        url = meta.get("url", "")
        doi = meta.get("doi", "")
        
        # Derive citation key from slug or authors/year
        cite_key = slug.replace("-", "")[:20] or "paper"
        if not cite_key or not cite_key[0].isalpha():
            cite_key = f"ref_{cite_key}"

        # Format authors for BibTeX
        authors = meta.get("authors", [])
        if isinstance(authors, list):
            author_str = " and ".join(authors)
        elif isinstance(authors, str):
            author_str = authors
        else:
            author_str = ""

        fields = [
            f"  title={{{title}}}"
        ]
        if author_str:
            fields.append(f"  author={{{author_str}}}")
        if year:
            fields.append(f"  year={{{year}}}")
        if doi:
            fields.append(f"  doi={{{doi}}}")
        if url:
            fields.append(f"  url={{{url}}}")
        if source:
            fields.append(f"  note={{Source: {source}}}")

        entry = f"@article{{{cite_key},\n" + ",\n".join(fields) + "\n}"
        entries.append(entry)

    out = storage.LIBRARY_DIR / "library.bib"
    out.write_text("\n\n".join(entries) + "\n", encoding="utf-8")
    return out


def _load_index_raw() -> dict:
    path = storage.index_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise StorageError(f"Could not read library index: {e}") from e
