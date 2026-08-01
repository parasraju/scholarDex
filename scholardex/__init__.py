"""scholarDex - AI-powered research paper search and summarization.

Public surface: the ScholarDex facade and Paper model.
"""

from .app import ScholarDex
from .errors import (
    ConfigError,
    ResolutionError,
    ScholarDexError,
    StorageError,
    SummaryError,
)
from .models import Paper, PaperRef, SummaryResult

__version__ = "1.1.0"
__all__ = [
    "ScholarDex",
    "Paper",
    "PaperRef",
    "SummaryResult",
    "ScholarDexError",
    "ConfigError",
    "ResolutionError",
    "StorageError",
    "SummaryError",
]
