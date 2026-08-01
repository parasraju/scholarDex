# ScholarDex — Design Review

A long-term maintainability review of the current implementation,
judged against the principles in *A Philosophy of Software Design*:
complexity is the primary enemy, modules should be deep, interfaces
simple, information hidden, and defaults should handle almost every
use case.

Scope: design only. Assumes current behavior is correct.

---

## 1. Complexity Estimate

Ranked sources of *accidental* complexity (complexity not intrinsic to
the problem).

| Rank | Area | Why it is accidental |
|---|---|---|
| 1 | `cli.py` orchestration | The CLI is the de-facto application layer. `search` runs a full workflow (search → interactive select → summarize → save). Command handlers know about providers, AI, storage, and files. |
| 2 | `fetch.py` identifier sniffing | Regex dispatch over URLs/DOIs/IDs plus a `<title>` page-scraper to guess a paper. Every new identifier shape is a new `if`. |
| 3 | `search.py` orchestration + notes tuple | `search_all` returns `(papers, notes)` — operational diagnostics leak into every caller and the public contract. |
| 4 | Provider logic duplication | arXiv, `scholarly`, and `USER_AGENT` are imported/defined in both `search.py` and `fetch.py`. Same provider, two home-rolled adapters. |
| 5 | Chunk-and-merge summarization | The "summarize a long paper" pipeline (chunk → per-chunk calls → merge call) is embedded in `summarize.py` with the prompt. Not composable, hard to test, not reusable for other models. |
| 6 | Library storage + export fused | `library.py` owns both on-disk layout and two export formats. Two reasons to change in one file. |
| 7 | Presentation inside `models.py` | `Paper.display_authors()` is UI formatting in a data class. |
| 8 | `config.py` | Reasonable. Mild sprawl: it owns both the config file *and* the library directory path. |

Intrinsic complexity (correctly present): talking to 4 academic
sources, PDF text extraction, LLM summarization, a persisted library.

---

## 2. Shallow Modules

### `models.py` — shallow-ish
One `Paper` dataclass. Fine as a value object, but it is *data-only
plus one display helper*. It should be either pure data or carry real
behavior (see §4: `paper.summary()`, `paper.save()`). As written it is
a carrier struct, and the display method makes it a "struct with one
method" — a shallow class.

**Make it deeper:** move behavior *onto* Paper: `paper.summarize()`,
`paper.save()`, `paper.citation(style)`. The model becomes the deep
facade over providers + AI + storage.

### `banner.py` — trivial
A constant. Not a module. Inline it in `cli.py`.

### `extract.py` — two shallow functions fused
`extract_text()` (PyMuPDF, page limit) and `chunk_text()` (paragraph
splitting) are unrelated concerns sharing a file. `chunk_text` is a
leaf utility with subtle edge cases (oversized paragraph handling)
that belongs *inside* the summarizer, where the chunk size policy
lives. `extract_text` belongs inside a `PDF` loader / Paper factory.

**Make deeper:** a `PaperLoader` that turns *any* input (PDF path,
URL, DOI, arXiv ID) into a fully-populated `Paper`, hiding where text
comes from and whether it was chunked.

### `config.py` — shallow but fine
Load/save/get with env fallback. Acceptable. The only smell: it
declares `LIBRARY_DIR`, a storage concern.

---

## 3. Public CLI Review

| Command | Obvious? | Problem |
|---|---|---|
| `search` | Yes | Does too much: search → interactive `IntPrompt` → summarize → save prompt. Not scriptable; interactive prompts in a CLI are a special case. The summarize/save workflow inside `search` duplicates `summarize`. |
| `summarize` | Yes | Two ways to summarize (`search` and `summarize`) — a redundancy, not cohesion. Takes URL/DOI/arXiv ID but *not* a local file; `pdf` exists for that. |
| `pdf` | Weak | A noun as a verb, and a special case: it's really "summarize a local file." Three input kinds (url/doi/id/file) split across two commands. |
| `library` | Yes | Fine. |
| `export` | Ok | "Export" of *what* — ambiguous, though the help says summaries. Two formats always exported at once; no `--format`. |
| `config` | Yes | Fine. |

**Recommendation — collapse to a "paper first" grammar.** The core
concept users hold is *a paper*. Inputs are *identifiers* (URL, DOI,
arXiv ID, local PDF). Actions are *lookup*, *summarize*, *save*,
*list*, *export*.

```
scholardex search "query"                      # table of results only
scholardex search "query" --summarize 3        # lookup + summarize one
scholardex get <url|doi|arxiv-id|file.pdf>     # resolve + print metadata
scholardex summarize <url|doi|arxiv-id|file.pdf>   # resolve + AI summary
scholardex library                             # list saved
scholardex export [--format md|json]           # export library
scholardex config [--set-key K] [--set-model M]
```

- Remove interactive prompts → scriptable, composable, testable.
- `summarize` accepts *any* paper reference, killing the `pdf`
  special case.
- No implementation detail (`PDF`, `arXiv`, `DOI`) in command names;
  those are identifier shapes, not workflows.

---

## 4. Internal API Design

Today a developer calling the library needs to know: `search_all`
returns a tuple, then `summarize_paper(paper)`, then
`add_summary(paper, result)`, and that `fetch.resolve` exists. That is
a shallow, leaky, multi-step API.

**Target API (as specified):**

```python
from scholardex import ScholarDex

sdk = ScholarDex()                      # one facade
papers = sdk.search("graph neural networks")
paper = papers[0]                       # Paper is the deep object
summary = paper.summary()               # AI pipeline, hidden chunking
paper.save()                            # storage, hidden layout
print(paper.citation("APA"))            # citation formatting
```

Design rules behind it:
- `ScholarDex` is the *only* thing the outside world imports.
- `Paper` is deep: it knows how to obtain its own content, summarize
  itself, persist itself, and cite itself — all by delegating inward.
- Everything else (providers, AI, storage, config) is an internal
  detail reachable from the facade, never from user code.

---

## 5. Information Hiding

These must never leak past their owning module:

| Detail | Hidden behind |
|---|---|
| Provider ordering / fallback | `ScholarDex.search()` — the facade |
| Which provider served a result | `Paper.source` value only; never ordering logic |
| HTTP requests, retries, rate limits | Provider adapters (`scholardex/providers/*`) |
| Gemini prompt text | `summarizer.py` |
| Chunking policy & chunk size | `summarizer.py` — callers pass a Paper, not text |
| PDF extraction strategy (PyMuPDF) | `loader.py` |
| Identifier sniffing (URL/DOI/ID regex) | `loader.py` / `PaperRef` |
| Storage layout (`index.json`, `.md` files, `~/.scholardex`) | `library.py` |
| Export format details | `exporters/` |
| Config file format (TOML) | `config.py` |

The current leak: `search_all`'s `notes` list surfaces provider
diagnostics to the caller — the reverse of hiding.

---

## 6. Layer Review

Target layering, strictly top-down, one-way:

```
CLI (scholardex/cli.py)
  depends only on: application API
  forbidden: any provider, model, storage import

Application API (Scholardex facade + Paper)
  depends only on: engines below
  forbidden: typer, rich, google.genai

Search / Resolve Engines
  depends only on: provider adapters, Paper
  forbidden: cli, storage, ai

Provider Abstractions (scholardex/providers/*)
  depends only on: models, http libs
  forbidden: cli, storage, ai

AI Pipeline (summarizer)
  depends only on: Paper, config
  forbidden: cli, storage, providers

Storage (library)
  depends only on: models, config(dir)
  forbidden: cli, ai, providers

Infrastructure (config, http) — bottom layer, imported by all above
```

Today: `cli.py` imports `config`, `fetch`, `library`, `search`,
`summarize` — it reaches every layer. That is the core layering
violation and the source of most coupling.

---

## 7. Module Cohesion

| Module | One reason to change? | Verdict |
|---|---|---|
| `cli.py` | No — commands, orchestration, rendering all mixed | Split: keep only typer commands + thin calls to facade; move rendering to small helpers or let rich calls stay but keep them dumb |
| `search.py` | No — four providers + orchestration + dedupe | Split providers into `providers/`; keep orchestration in facade |
| `fetch.py` | Yes (resolve) but over-specialized | Merge into `loader.py` as the Paper factory; keep `search` and `resolve` using *the same* provider adapters |
| `extract.py` | No — two concerns | Move chunking into `summarizer.py`; PDF extraction into `loader.py` |
| `summarize.py` | Yes — AI summarization | Good; extract the chunk/merge as internal detail |
| `library.py` | No — storage + export | Split `library.py` (store) from `exporters/` |
| `config.py` | Yes | Good, minus `LIBRARY_DIR` ownership |
| `models.py` | Yes — Paper value | Good, once display moves out and behavior moves in |

---

## 8. Coupling Analysis

Current coupling problems and fixes:

| Coupling | Problem | Fix |
|---|---|---|
| CLI → everything | `cli.py` imports all six modules; one command touches 5 layers | Route everything through `ScholarDex` facade |
| `search_all` → `(papers, notes)` | Caller must consume diagnostics | Return `list[Paper]`; log notes internally |
| `fetch.py` + `search.py` share providers | Duplicate arXiv/scholarly/UA logic | One `providers/` set, shared by search and resolve |
| `models.py` ↔ rich | `display_authors` ties data class to UI | Remove method; format in CLI |
| `summarize.py` ↔ `extract.chunk_text` | Chunking imported across modules | Move chunking into summarizer |
| `config.LIBRARY_DIR` | Config owns storage path | Storage owns its own dir under the config dir |
| `library.py` ↔ `SummaryResult` | Storage depends on AI result type | Pass plain fields, or keep as-is if small — low priority |

---

## 9. Folder Structure

```
scholarDex/
├── pyproject.toml
└── scholardex/
    ├── __init__.py        # public surface: re-export ScholarDex, Paper
    ├── cli.py             # thin typer commands only
    ├── app.py             # ScholarDex facade (search / resolve entry)
    ├── models.py          # Paper, SummaryResult (pure data)
    ├── loader.py          # any reference -> Paper (URL/DOI/ID/PDF)
    ├── providers/
    │   ├── __init__.py    # registry + base protocol
    │   ├── scholar.py
    │   ├── arxiv.py
    │   ├── semantic.py
    │   └── crossref.py
    ├── summarizer.py      # chunking + prompts + merge (model-agnostic shell)
    ├── storage.py         # library save/list/load (layout + index)
    ├── exporters.py       # markdown / json export
    └── config.py          # config load/save/keys
```

Every folder earns its existence:
- `providers/` — one file per external source; the unit of growth.
- No `utils/`, `helpers/`, `services/` — banned (§12).

---

## 10. Future Features

| Future | Would today's design survive? |
|---|---|
| 100 providers | No. Hard-coded `search_all` + per-source functions would be a maintenance wall. Fixed by the provider registry + protocol (§11). |
| OpenAI / Claude / Ollama | No. `summarize.py` is Gemini-import-bound. Needs a model abstraction (small, worth it). |
| MCP / plugins | No. Requires a registry; the provider registry is the seed, but MCP is a separate project decision. |
| Embeddings / vector search / RAG | No. Nothing stores embeddings. Recommend **against** adding now — it is feature expansion that buys little for a personal research tool. |
| Recommendations / citation graphs | No. Would need relational storage; `index.json` would break. Revisit only if actually needed. |

**Verdict:** support providers + multiple models + exporters with a
registry (cheap). Defer MCP, RAG, embeddings, graphs — each adds more
complexity than it returns today.

---

## 11. Plugin Architecture

Keep it *boring* — one decorator + one registry dict. No import
hooks, no entry-point scanning.

```python
# providers/__init__.py
class SearchProvider(Protocol):
    name: str
    def search(self, query: str, limit: int) -> list[Paper]: ...
    def resolve(self, ref: PaperRef) -> Paper | None: ...

_REGISTRY: dict[str, SearchProvider] = {}

def register(provider: SearchProvider) -> SearchProvider:
    _REGISTRY[provider.name] = provider
    return provider
```

Adding a provider = drop a file in `providers/` that calls
`@register`. Adding a model = a `summarizer` implementation behind a
`"model": "gemini" | "openai"` config key. Adding an exporter = one
function in `exporters.py` + a `--format` flag.

Rules: no lifecycle, no plugin objects, no async orchestration. The
facade iterates the registry. That is the entire system.

---

## 12. Naming Review

| Current | Problem | Better |
|---|---|---|
| `cli.search` (command) | collides with `search` module | fine after facade; command can stay `search` |
| `search_all` | "all" is meaningless; returns a tuple | `search()` returning `list[Paper]` |
| `fetch.py` | vague; "fetch what?" | `loader.py` |
| `resolve()` / `fetch_*` | `resolve` is good; `fetch_url`/`fetch_semantic_url` are overloaded | `Loader.load(ref)` |
| `extract.py` | vague | absorb into `loader.py` + `summarizer.py` |
| `summarize_paper` | `Paper` already implies it | `summarize()` |
| `display_authors` | presentation in model | removed; format in CLI |
| `SummaryResult` | fine | keep |
| `library_cmd`, `config_cmd` | `_cmd` suffix noise | `library()`, `config()` |
| `_summarize_and_store` | verb "and" = two jobs | split into facade methods `summarize()` + `save()` |
| `banner.py` | module for a constant | inline in `cli.py` |
| `LIBRARY_DIR` | fine, wrong owner | `storage.LIBRARY_DIR` |
| `PaperRef` (new) | explicit reference type | better than string-typed identifiers |

No `utils`, `helpers`, `manager`, `service`, `processor`, `handler`,
`engine` anywhere.

---

## 13. Configuration Philosophy

Ousterhout: defaults should handle almost every use case.

- **Automatic, zero config:** provider selection and fallback order;
  chunking; prompts; storage location default; export formats.
- **Never configurable:** prompt text, chunk size, provider order —
  these are code, and making them config adds surface with no payoff.
- **Belongs in config:** Gemini API key, model name. That's it.
- **Config → code, not code → config:** current defaults are already
  sensible. The only fix: `model` default `gemini-2.5-flash` is right;
  add nothing else.

Do **not** add: provider enable/disable toggles, per-source keys,
retry counts, page limits. Each is config sprawl.

---

## 14. Error Handling

Today: `RuntimeError` strings, silent `return []` on provider failure,
`typer.Exit(1)` in handlers, and the "No API key" RuntimeError raised
deep inside `_make_client()`.

Target architecture:
- A tiny exception set: `ConfigError`, `ResolutionError`,
  `SummaryError`, `StorageError` — one module, ~10 lines.
- **Providers never raise to the user.** The facade catches per-provider
  failures, logs, moves on. Users see the *outcome* (fewer sources),
  never the provider internals.
- **The CLI is the only catcher.** Handlers catch the four exceptions
  and print one friendly line each. No `except Exception` scattered in
  commands.
- Resolve failures become `ResolutionError("couldn't find a paper for 'X'")`.
- Missing API key → `ConfigError` at facade construction, caught by CLI
  before any status spinner starts.

---

## 15. Technical Debt (ranked by impact)

| Rank | Debt | Impact |
|---|---|---|
| 1 | CLI orchestrates every layer | Every feature change touches the CLI; impossible to unit test workflows |
| 2 | Duplicated provider adapters in `search.py` + `fetch.py` | Provider changes must be made twice; drift over time |
| 3 | Identifier sniffing special-cases in `fetch.py` | Every new URL shape is a branch; `<title>` scraping is fragile |
| 4 | `search_all` returns notes tuple | Contract leak; forces every caller to know diagnostics |
| 5 | Chunk/merge summarization fused with Gemini | Can't swap models; merge logic untestable in isolation |
| 6 | Presentation in `models.py` | Model couples to UI |
| 7 | Storage + export fused in `library.py` | Two reasons to change |
| 8 | Interactive prompts in CLI | Non-scriptable; hard to test |

---

## 16. Maintenance Simulation — ScholarDex in 2036

- **Painful:** Google Scholar scraping (`scholarly`) — breaks
  whenever Scholar changes HTML. arXiv/Semantic Scholar are stable
  APIs; Scholar is the chronic wound. Mitigated now by fallback, but
  expect ongoing maintenance there.
- **Painful:** the CLI's embedded workflow. Any new command would
  require reading the full `cli.py` because behavior isn't factored.
- **Confusing:** `search_all`'s tuple contract, the `search`/`fetch`
  split, identifier regexes. A new maintainer would not know where a
  paper's text comes from.
- **Major rewrites required:** none if the facade + provider registry
  land now. Without them: a provider rewrite touches both `search.py`
  and `fetch.py`, and adding a second AI model means forking
  `summarize.py`.
- **Still elegant:** `Paper` (small), `config.py`, the value of the
  library concept.

---

## 17. Design It Twice (simpler wins)

| Subsystem | Design A | Design B | Choose |
|---|---|---|---|
| Search | 4 free functions + orchestrator | Provider registry + facade loop | **B** — only if it stays a plain dict+decorator; the moment B grows lifecycle code, fall back to A |
| Resolve | Regex dispatch in `fetch.py` | `PaperRef` + providers that self-report "can I resolve this?" | **B** — moves the special-case *into* the provider that owns it (arXiv resolves arXiv), eliminating the dispatch chain |
| Summarization | Gemini-only `summarize_paper` | Model-agnostic `summarizer` with provider key | **B** only when a 2nd model is actually added; until then keep Gemini path but isolate it behind one function |
| Storage | `index.json` + `.md` files | SQLite | **A** — human-readable, trivially exported, no migration. SQLite is over-engineering for a personal notes library |
| Export | two functions in `library.py` | `exporters.py` with `--format` | **B** — cheap, gives `--format` for free, removes a reason-to-change from storage |

---

## 18. Refactoring Roadmap (by ROI)

| # | Change | Difficulty | Complexity ↓ | Risk | Payoff |
|---|---|---|---|---|---|
| 1 | Introduce `ScholarDex` facade; make CLI thin | Medium | High | Low | High |
| 2 | Provider registry; shared `providers/` used by both search and resolve | Medium | High | Low | High |
| 3 | Kill the `(papers, notes)` tuple → `list[Paper]`, log internally | Trivial | Medium | Low | High |
| 4 | Collapse `pdf` into `summarize`; drop interactive prompts | Low | Medium | Low | High |
| 5 | Move chunking into summarizer; isolate Gemini behind one function | Low | Medium | Low | Medium |
| 6 | Move `display_authors` out of `Paper` | Trivial | Low | Low | Medium |
| 7 | Add the 4-exception hierarchy + CLI-level catching | Medium | Medium | Medium | Medium |
| 8 | Split `exporters.py` with `--format` | Trivial | Low | Low | Low |
| 9 | Move `LIBRARY_DIR` ownership to storage | Trivial | Low | Low | Low |

Suggested order: 1 → 2 → 3 (foundation), then 4 → 5 (UI/UX), then
6 → 7 → 8 → 9 (polish). Items 1–3 are the structural payoff; 4–5 the
immediate usability win.

---

## 19. Scorecard

| Dimension | /10 | Evidence |
|---|---|---|
| Simplicity | 6 | Small codebase, but the CLI embeds a full workflow and provider logic is duplicated across two files |
| Information Hiding | 4 | `notes` tuple leaks diagnostics; CLI reaches every layer; display helper in the model |
| Deep Modules | 5 | `Paper` is a shallow struct; `config` shallow-but-fine; providers are thin functions with no depth |
| Naming | 6 | Most names fine; `fetch`, `extract`, `_cmd` suffixes, `search_all` are weak; `display_authors` misplaced |
| Layering | 4 | `cli.py` imports all six modules — no separation of CLI / application / infrastructure |
| Extensibility | 4 | Adding a provider touches orchestrator; adding a model means forking the summarizer |
| Maintainability | 5 | Would survive small changes; structural issues compound for larger ones |
| Cognitive Load | 6 | Tuple returns, two resolve paths, three ways to trigger a summary |
| API Design | 3 | No public API; multi-step, leaky, tuple-returning internals |
| CLI Design | 5 | Commands are clear but `pdf` is a special case, prompts hurt scripting, two commands duplicate summarize |
| Architecture | 4 | No stable boundary between CLI, application, providers, AI, storage |
| **Overall** | **4.8** | Working, small, but the plumbing is the problem — all of it fixable at low risk |

---

## Bottom line

The functionality is right; the shape isn't. The single highest-value
move is a `ScholarDex` facade that makes the CLI thin and the module
`Paper` deep. Everything else (provider registry, killing the notes
tuple, collapsing `pdf` into `summarize`, isolating the Gemini path)
follows naturally from that one boundary. Skip MCP, RAG, embeddings,
and citation graphs — they add complexity the tool doesn't need.
