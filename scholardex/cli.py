"""scholarDex CLI — thin typer commands over the ScholarDex facade.

No provider, AI, storage, or config imports here. All workflows live
behind `ScholarDex`. Errors are caught once, at the edge.
"""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import config as config_mod
from .app import ScholarDex
from .errors import ScholarDexError
from .models import Paper, format_authors

BANNER = r"""
  _____      __          __          ____            
  / ___/_____/ /_  ____  / /___ ______/ __ \___  _  __
  \__ \/ ___/ __ \/ __ \/ / __ `/ ___/ / / / _ \| |/_/
 ___/ / /__/ / / / /_/ / / /_/ / /  / /_/ /  __/>  <  
/____/\___/_/ /_/\____/_/\__,_/_/  /_____/\___/_/|_|  
"""

app = typer.Typer(help="AI-powered research paper search and summarization.", add_completion=False)
console = Console()
err_console = Console(stderr=True)


@app.callback(invoke_without_command=True)
def _main(no_banner: bool = typer.Option(False, "--no-banner", help="Skip the banner")) -> None:
    if not no_banner:
        console.print(f"[cyan]{BANNER}[/cyan]")


@app.command()
def search(
    query: list[str] = typer.Argument(help="Search query (multiple words OK, no quotes needed)"),
    count: int = typer.Option(5, "--count", "-n", min=1, max=15, help="Results per source"),
    summarize_result: Optional[int] = typer.Option(
        None, "--summarize", "-s", min=1, help="Summarize result #N after listing"
    ),
    save: bool = typer.Option(True, "--save/--no-save", help="Save the summary to the library"),
) -> None:
    """Search papers across all providers, then optionally summarize one result."""
    _run(lambda sdk: _do_search(sdk, " ".join(query), count, summarize_result, save))


@app.command()
def get(identifier: str) -> None:
    """Resolve a URL, DOI, arXiv ID, or local PDF and show its metadata."""
    _run(lambda sdk: _do_get(sdk, identifier))


@app.command()
def open(identifier: str) -> None:
    """Open a paper's page in your default browser to read it."""
    _run(lambda sdk: _do_open(sdk, identifier))


@app.command()
def summarize(
    identifier: str,
    save: bool = typer.Option(True, "--save/--no-save", help="Save the summary to the library"),
) -> None:
    """Resolve a paper (URL, DOI, arXiv ID, or PDF) and summarize it."""
    _run(lambda sdk: _do_summarize(sdk, identifier, save))


@app.command("library")
def library() -> None:
    """List all saved summaries."""
    _run(_do_library)


@app.command()
def export(
    format: str = typer.Option("md", "--format", "-f", help="Export format: md, json, or all"),
) -> None:
    """Export the library to Markdown/JSON."""
    _run(lambda sdk: _do_export(sdk, format))


@app.command()
def config(
    set_key: Optional[str] = typer.Option(None, "--set-key", "-k", help="Set Gemini API key"),
    set_model: Optional[str] = typer.Option(None, "--set-model", "-m", help="Set Gemini model name"),
    show: bool = typer.Option(False, "--show", help="Show current config"),
) -> None:
    """View or update the Gemini configuration."""
    _run(lambda _sdk: _do_config(set_key, set_model, show))


# ---------------------------------------------------------------------------
# Command bodies
# ---------------------------------------------------------------------------
def _run(fn) -> None:
    try:
        sdk = ScholarDex()
        fn(sdk)
    except ScholarDexError as e:
        err_console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e


def _do_search(sdk: ScholarDex, query: str, count: int, pick: Optional[int], save: bool) -> None:
    with console.status(f"Searching for '{query}'..."):
        papers = sdk.search(query, limit=count)

    if not papers:
        err_console.print("[red]No results found from any source.[/red]")
        raise typer.Exit(1)

    table = Table(title=f'Results for "{query}"')
    table.add_column("#", justify="right", style="cyan")
    table.add_column("Title", style="bold")
    table.add_column("Year", justify="right")
    table.add_column("Citations", justify="right")
    table.add_column("Source")
    for i, p in enumerate(papers, 1):
        table.add_row(
            str(i),
            p.title[:100],
            str(p.year or "?"),
            str(p.citations) if p.citations else "-",
            p.source,
        )
    console.print(table)

    if pick is not None:
        if pick < 1 or pick > len(papers):
            err_console.print(f"[red]No result #{pick}. Pick 1-{len(papers)}.[/red]")
            raise typer.Exit(1)
        paper = papers[pick - 1]
        console.print(f"[dim]Summarizing result #{pick}...[/dim]")
        _print_paper(paper)
        result = _summarize(sdk, paper)
        console.print(Panel(result.summary, title=f"Summary ({result.model})", border_style="green"))
        if save:
            path = sdk.save(paper, result)
            console.print(f"[green]Saved to {path}[/green]")
        else:
            console.print("[dim]Not saved (--no-save).[/dim]")


def _do_get(sdk: ScholarDex, identifier: str) -> None:
    with console.status("Resolving paper..."):
        paper = sdk.load(identifier)
    _print_paper(paper)


def _do_open(sdk: ScholarDex, identifier: str) -> None:
    import webbrowser

    with console.status("Resolving paper..."):
        paper = sdk.load(identifier)
    url = paper.url
    if not url and paper.doi:
        url = f"https://doi.org/{paper.doi}"
    if not url:
        err_console.print("[red]No URL available for this paper.[/red]")
        raise typer.Exit(1)
    console.print(f"[dim]Opening {url}[/dim]")
    webbrowser.open(url)


def _do_summarize(sdk: ScholarDex, identifier: str, save: bool) -> None:
    with console.status("Resolving paper..."):
        paper = sdk.load(identifier)
    _print_paper(paper)

    result = _summarize(sdk, paper)
    console.print(Panel(result.summary, title=f"Summary ({result.model})", border_style="green"))

    if save:
        path = sdk.save(paper, result)
        console.print(f"[green]Saved to {path}[/green]")
    else:
        console.print("[dim]Not saved (--no-save).[/dim]")


def _do_library(sdk: ScholarDex) -> None:
    papers = sdk.library()
    if not papers:
        console.print("Library is empty. Run `scholardex summarize` to add a paper.")
        return
    table = Table(title="scholarDex Library")
    table.add_column("Title", style="bold")
    table.add_column("Year", justify="right")
    table.add_column("Source")
    for meta in papers:
        table.add_row(meta["title"][:80], str(meta.get("year") or "?"), meta.get("source", ""))
    console.print(table)


def _do_export(sdk: ScholarDex, format: str) -> None:
    path = sdk.export(format)
    console.print(f"[green]Exported[/green] {path}")


def _do_config(set_key, set_model, show) -> None:
    cfg = config_mod.load_config()
    if set_key:
        cfg["gemini"]["api_key"] = set_key
        config_mod.save_config(cfg)
        console.print("[green]API key saved.[/green]")
    if set_model:
        cfg["gemini"]["model"] = set_model
        config_mod.save_config(cfg)
        console.print(f"[green]Model set to {set_model}.[/green]")
    if show or not (set_key or set_model):
        console.print(Panel(
            f"API key: {'[green]set[/green]' if cfg['gemini']['api_key'] else '[red]not set[/red]'}\n"
            f"Model:   {cfg['gemini']['model']}",
            title="scholarDex config",
        ))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _print_paper(paper: Paper) -> None:
    console.print(Panel(
        f"[bold]{paper.title}[/bold]\n"
        f"Authors: {format_authors(paper.authors)}\n"
        f"Year: {paper.year or 'Unknown'}  |  Source: {paper.source or 'Unknown'}  |  "
        f"Citations: {paper.citations or '-'}\n"
        f"URL: {paper.url or 'N/A'}"
        + (f"\nDOI: {paper.doi}" if paper.doi else ""),
        title="Paper",
    ))


def _summarize(sdk: ScholarDex, paper: Paper):
    with console.status("Summarizing with Gemini..."):
        return sdk.summarize(paper)


def main() -> None:
    app()


if __name__ == "__main__":
    app()
