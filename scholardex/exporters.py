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
    """Export the library in the given format (``md``, ``json``, or ``all``)."""
    if format_name == "json":
        return _export_json()
    if format_name == "all":
        _export_json()
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


def _load_index_raw() -> dict:
    path = storage.index_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise StorageError(f"Could not read library index: {e}") from e
