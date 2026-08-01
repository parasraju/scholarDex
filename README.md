<div align="center">

  <pre>
  _____      __          __          ____
  / ___/_____/ /_  ____  / /___ ______/ __ \___  _  __
  \__ \/ ___/ __ \/ __ \/ / __ `/ ___/ / / / _ \| |/_/
 ___/ / /__/ / / / /_/ / / /_/ / /  / /_/ /  __/>  <
/____/\___/_/ /_/\____/_/\__,_/_/  /_____/\___/_/|_|
  </pre>

  **AI-powered research paper search & summarization for your terminal**

  Search across Google Scholar, arXiv, Semantic Scholar, and Crossref — then get
  clean, structured Gemini summaries you can save into a local library.

  [![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org)
  [![Gemini](https://img.shields.io/badge/Powered%20by-Gemini-4285F4?logo=google&logoColor=white)](https://ai.google.dev)
  [![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
  [![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)]()

  <a href="#quick-start"><img src="https://img.shields.io/badge/%E2%9A%A1-Quick%20Start-7c3aed?style=for-the-badge"></a>
  <a href="#usage"><img src="https://img.shields.io/badge/%F0%9F%93%9A-Usage-2563eb?style=for-the-badge"></a>
  <a href="#python-sdk"><img src="https://img.shields.io/badge/%F0%9F%A7%AA-Python%20SDK-0d9488?style=for-the-badge"></a>
  <a href="#architecture"><img src="https://img.shields.io/badge/%F0%9F%8F%97-Architecture-475569?style=for-the-badge"></a>
  <a href="#contributing"><img src="https://img.shields.io/badge/%F0%9F%A4%9D-Contributing-c026d3?style=for-the-badge"></a>

</div>

---

## What it does

- **Search** — one query, four sources: Google Scholar, arXiv, Semantic Scholar, Crossref. Provider failures degrade silently.
- **Summarize** — structured AI summaries (Abstract, Contributions, Methods, Findings, Limitations) via Google Gemini.
- **Read** — open any paper in your browser straight from the terminal.
- **Library** — every summary is saved locally and can be exported to Obsidian-friendly Markdown or JSON.
- **Flexible input** — pass a URL, a DOI, an arXiv ID, or a local PDF file. Anything works.

## Quick Start

```bash
# 1. Install
pip install -e .

# 2. Add your free Gemini API key (aistudio.google.com/apikey)
scholardex config --set-key YOUR_GEMINI_API_KEY
```

That's it. Run `scholardex --help` to see everything.

## Usage

### Search & summarize

```bash
# List results (no quotes needed for multi-word queries)
scholardex search Ironic process theory

# List results, then summarize result #3
scholardex search graph neural networks --summarize 3

# Summarize without saving to the library
scholardex search graph neural networks -s 3 --no-save
```

### Summarize any paper

```bash
scholardex summarize https://arxiv.org/abs/2005.11401   # URL
scholardex summarize 10.48550/arXiv.2005.11401          # DOI
scholardex summarize paper.pdf                          # local PDF
```

### Read & manage

```bash
scholardex open https://arxiv.org/abs/2005.11401        # open in browser
scholardex get 10.48550/arXiv.2005.11401                # show metadata only
scholardex library                                      # list saved summaries
scholardex export --format all                          # md | json | all
scholardex config --show                                # view current config
```

## Commands

| Command | Description |
|---|---|
| `search` | Search all providers, optionally summarize a result (`-s N`) |
| `summarize` | Resolve a URL / DOI / arXiv ID / PDF and summarize it |
| `open` | Open a paper in your default browser |
| `get` | Resolve a paper and show its metadata |
| `library` | List everything saved locally |
| `export` | Export the library to Markdown / JSON |
| `config` | Manage the Gemini API key and model |

## Python SDK

The CLI is a thin layer over a clean facade. Use scholarDex as a library:

```python
from scholardex import ScholarDex

sdk = ScholarDex()
papers = sdk.search("graph neural networks")
paper = papers[0]

summary = paper.summary()        # or sdk.summarize(paper)
paper.save()                     # or sdk.save(paper, summary)
print(paper.citation("APA"))     # "Lewis, Patrick (2020). Retrieval-..."
```

## Architecture

```
CLI ──► ScholarDex facade ──► providers / loader / summarizer / storage
```

- **Facade** (`app.py`) — the only public entry point; `Paper` is a deep object.
- **Providers** (`providers/`) — pluggable; drop in a module that calls `register()`.
- **Summarizer** (`summarizer.py`) — chunking + prompts, Gemini isolated.
- **Storage** (`storage.py`, `exporters.py`) — local library + exports.
- Full design notes in [`DESIGN.md`](DESIGN.md).

## Notes

- Long papers are chunked and summarized in parts, then merged.
- Scanned / image-based PDFs have no extractable text and aren't supported.
- Summaries live in `~/.scholardex/library/`.

## Contributing

Adding a paper source? Create `scholardex/providers/your_source.py` implementing
`search` / `can_resolve` / `resolve` and call `register()` — done.

## License

[MIT](LICENSE)
