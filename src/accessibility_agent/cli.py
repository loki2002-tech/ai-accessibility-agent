"""
CLI Entry Point — AI Accessibility Testing Agent.

Provides the ``a11y-agent`` command with subcommands:
    scan        Run an accessibility scan
    report      Re-generate a report from an existing JSON result
    version     Show version information

Usage examples:
    a11y-agent scan --url https://example.com
    a11y-agent scan --url https://example.com --mode full --output ./reports
    a11y-agent scan --url https://example.com --no-headless --browser firefox
    a11y-agent version
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from accessibility_agent.logging_config import configure_logging, get_logger

app = typer.Typer(
    name="a11y-agent",
    help="AI-Powered Accessibility Testing Agent — deterministic-first, AI-assisted.",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()
err_console = Console(stderr=True)


@app.callback()
def _global_options() -> None:
    """Configure logging before any command runs."""
    configure_logging()


@app.command("scan")
def cmd_scan(
    url: Annotated[str, typer.Option("--url", "-u", help="Target URL to scan")],
    mode: Annotated[
        str,
        typer.Option(
            "--mode", "-m",
            help="Scan mode: automated | keyboard | semantic | visual | interaction | dynamic | manual-assist | ai-analysis | full",
        ),
    ] = "automated",
    output: Annotated[
        Optional[Path],
        typer.Option("--output", "-o", help="Output directory for reports"),
    ] = None,
    browser: Annotated[
        str,
        typer.Option("--browser", "-b", help="Browser: chromium | firefox | webkit"),
    ] = "chromium",
    headless: Annotated[
        bool,
        typer.Option("--headless/--no-headless", help="Run browser in headless mode"),
    ] = True,
    viewport: Annotated[
        str,
        typer.Option("--viewport", help="Viewport as WIDTHxHEIGHT, e.g. 1280x720"),
    ] = "1280x720",
    formats: Annotated[
        str,
        typer.Option("--formats", help="Comma-separated report formats: json,html,csv"),
    ] = "json,html",
    agentic: Annotated[
        bool,
        typer.Option("--agentic", help="Enable Agentic Observe/Plan/Act loop for dynamic DOM interaction"),
    ] = False,
) -> None:
    """
    Run an accessibility scan against a URL.

    Examples:

    \b
    # Basic automated scan
    a11y-agent scan --url https://example.com

    \b
    # Full audit in Firefox, non-headless
    a11y-agent scan --url https://example.com --mode full --browser firefox --no-headless
    """
    log = get_logger("cli")

    # Parse viewport
    try:
        w, h = map(int, viewport.lower().split("x"))
    except ValueError:
        err_console.print(f"[red]Invalid viewport format: {viewport}. Use WIDTHxHEIGHT (e.g. 1280x720)[/red]")
        raise typer.Exit(1)

    report_formats = [f.strip() for f in formats.split(",")]
    valid_modes = {"automated", "keyboard", "semantic", "visual", "interaction",
                   "dynamic", "manual-assist", "ai-analysis", "full"}
    if mode not in valid_modes:
        err_console.print(f"[red]Invalid mode: {mode}. Choose from: {', '.join(sorted(valid_modes))}[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold blue]♿ AI Accessibility Testing Agent[/bold blue]")
    console.print(f"   URL: [link={url}]{url}[/link]")
    console.print(f"   Mode: {mode}")
    console.print(f"   Agentic: {agentic}")
    console.print(f"   Browser: {browser} ({'headless' if headless else 'headed'})")
    console.print(f"   Viewport: {viewport}\n")

    # Run the scan
    from accessibility_agent.agent.orchestrator import ScanOrchestrator

    orchestrator = ScanOrchestrator(
        url=url,
        mode=mode,
        output_dir=output,
        browser_type=browser,
        headless=headless,
        viewport=(w, h),
        report_formats=report_formats,
        agentic=agentic,
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(f"Scanning {url}...", total=None)
        try:
            result = asyncio.run(orchestrator.run())
        except KeyboardInterrupt:
            console.print("\n[yellow]Scan interrupted by user.[/yellow]")
            raise typer.Exit(130)
        except Exception as exc:
            err_console.print(f"\n[red]Scan failed: {exc}[/red]")
            log.exception("cli.scan_failed", error=str(exc))
            raise typer.Exit(1)

    # Display summary
    _print_summary(result)


def _print_summary(result: "ScanResult") -> None:  # type: ignore[name-defined]
    """Print a rich summary table of the scan results."""
    from accessibility_agent.wcag.schemas import ScanResult  # local import

    m = result.metrics
    console.print("\n[bold]📊 Scan Complete[/bold]\n")

    table = Table(title=f"Results — {result.run_id}", show_header=True)
    table.add_column("Metric", style="bold")
    table.add_column("Count", justify="right")

    table.add_row("[red]Confirmed Findings[/red]", str(m.confirmed_findings))
    table.add_row("[yellow]Likely Findings[/yellow]", str(m.likely_findings))
    table.add_row("[blue]Manual Review Required[/blue]", str(m.manual_review_findings))
    table.add_row("[green]Passed Checks[/green]", str(m.passed_checks))
    table.add_row("Duplicates Removed", str(m.duplicate_findings))
    table.add_row("Level A Failures", str(m.level_a_findings))
    table.add_row("Level AA Failures", str(m.level_aa_findings))
    table.add_row("axe Violations", str(m.axe_violations))
    table.add_row("axe Incomplete", str(m.axe_incomplete))

    console.print(table)

    if m.wcag_criteria_affected:
        console.print(f"\n[bold]WCAG Criteria Affected:[/bold] {', '.join(sorted(m.wcag_criteria_affected))}")

    if result.errors:
        console.print("\n[yellow]⚠️ Scan Errors:[/yellow]")
        for e in result.errors:
            console.print(f"  • {e}")

    console.print(
        "\n[dim]⚠️  A clean scan does NOT constitute WCAG conformance. "
        "Human expert review is required.[/dim]\n"
    )


@app.command("version")
def cmd_version() -> None:
    """Display version and dependency information."""
    from accessibility_agent import __version__
    from accessibility_agent.config import settings

    console.print(f"[bold]AI Accessibility Testing Agent[/bold] v{__version__}")
    console.print(f"  axe-core version: {settings.axe_version}")
    console.print(f"  Default browser: {settings.browser_type.value}")
    console.print(f"  LLM provider: {settings.llm_provider.value}")


@app.command("serve")
def cmd_serve(
    host: Annotated[str, typer.Option("--host", help="Host to bind the server to")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", help="Port to bind the server to")] = 8000,
    reload: Annotated[bool, typer.Option("--reload", help="Enable auto-reload for development")] = False,
) -> None:
    """
    Start the REST API server.

    Examples:
    
    \b
    # Start on default port 8000
    a11y-agent serve

    \b
    # Start on custom host/port
    a11y-agent serve --host 0.0.0.0 --port 8080
    """
    console.print(f"\n[bold blue]🚀 Starting API Server on http://{host}:{port}[/bold blue]\n")
    try:
        from accessibility_agent.api.server import run_server
        run_server(host=host, port=port, reload=reload)
    except ImportError as e:
        err_console.print(f"[red]Error starting server: {e}[/red]")
        err_console.print("Ensure you have installed fastapi and uvicorn: pip install fastapi uvicorn")
        raise typer.Exit(1)

if __name__ == "__main__":
    app()
