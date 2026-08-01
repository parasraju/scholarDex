"""Exception hierarchy for scholarDex.

Four public exceptions. Providers never raise these to the user; the
facade catches per-provider failures, logs, and moves on. The CLI is
the only place that catches them for display.
"""

from __future__ import annotations


class ScholarDexError(Exception):
    """Base class for all scholarDex errors."""


class ConfigError(ScholarDexError):
    """Configuration problem (e.g. missing API key)."""


class ResolutionError(ScholarDexError):
    """Could not resolve a reference (URL/DOI/arXiv ID/file) to a paper."""


class SummaryError(ScholarDexError):
    """AI summarization failed."""


class StorageError(ScholarDexError):
    """Local library storage or export failed."""
