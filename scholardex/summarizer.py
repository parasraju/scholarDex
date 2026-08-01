"""AI summarization pipeline.

The chunking policy and prompt text are internal details: callers pass
a `Paper` and get a `SummaryResult`. The Gemini client is isolated so
a second model can be added behind the same `summarize()` contract.
"""

from __future__ import annotations

from . import config
from .errors import SummaryError
from .models import Paper, SummaryResult

_PROMPT = """You are an expert research assistant. Summarize the following academic paper.

Produce a structured summary with these sections:
1. **Abstract** - 2-3 sentence plain-language summary
2. **Key Contributions** - bullet list of the main contributions
3. **Methods** - brief overview of approach/methodology
4. **Findings** - bullet list of main results/findings
5. **Limitations** - bullet list of limitations or open questions

Use concise, technical-but-readable language. Output Markdown only.

Title: {title}
Authors: {authors}
Year: {year}
Source: {source}
URL: {url}

Paper content:
{text}
"""

_MERGE_PROMPT = """You summarized a long academic paper in parts. Merge the part summaries into one
coherent structured summary with sections: Abstract, Key Contributions, Methods,
Findings, Limitations. Remove redundancy. Output Markdown only.

Title: {title}

Part summaries:
{parts}
"""

_MAX_CHUNK_CHARS = 8000


def chunk_text(text: str, max_chars: int = _MAX_CHUNK_CHARS) -> list[str]:
    """Split text into chunks by paragraphs, keeping each under max_chars."""
    if len(text) <= max_chars:
        return [text]
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_chars:
            current = f"{current}\n\n{para}".strip()
        else:
            if current:
                chunks.append(current)
            if len(para) > max_chars:
                for i in range(0, len(para), max_chars):
                    chunks.append(para[i : i + max_chars])
                current = ""
            else:
                current = para
    if current:
        chunks.append(current)
    return chunks


class GeminiSummarizer:
    """Gemini-backed summarizer.

    The client is created lazily so a missing API key fails only when
    summarization is actually requested.
    """

    def __init__(self) -> None:
        self._client = None
        self._model_name: str | None = None

    def summarize(self, paper: Paper) -> SummaryResult:
        text = paper.full_text or paper.abstract or "(No abstract or full text available.)"
        chunks = chunk_text(text)

        prompts = [self._prompt(_PROMPT, paper, chunk) for chunk in chunks]
        parts = [self._generate(p) for p in prompts]

        if len(parts) == 1:
            final = parts[0]
        else:
            merge = _MERGE_PROMPT.format(title=paper.title, parts="\n\n".join(parts))
            final = self._generate(merge)

        return SummaryResult(title=paper.title, summary=final, model=self.model_name)

    @property
    def model_name(self) -> str:
        self._ensure_client()
        return self._model_name

    def _ensure_client(self):
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=config.api_key())
            self._model_name = config.model()

    def _generate(self, prompt: str) -> str:
        self._ensure_client()
        try:
            response = self._client.models.generate_content(
                model=self._model_name, contents=prompt
            )
        except Exception as e:
            raise SummaryError(f"Gemini request failed: {e}") from e
        return response.text

    @staticmethod
    def _prompt(template: str, paper: Paper, text: str) -> str:
        return template.format(
            title=paper.title,
            authors=", ".join(paper.authors) or "Unknown",
            year=paper.year or "Unknown",
            source=paper.source or "Unknown",
            url=paper.url or "",
            text=text,
        )


def make_summarizer() -> GeminiSummarizer:
    return GeminiSummarizer()
