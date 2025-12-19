"""Analyze command for chunk size optimization recommendations."""

import sys
import time
from pathlib import Path

import click
from rich.console import Console
from rich.live import Live
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from prometh_cortex.analyzer import DocumentAnalyzer
from prometh_cortex.cli.animations import ClaudeProgress, ClaudeStatusDisplay

console = Console()


@click.command()
@click.option(
    "--samples",
    type=int,
    default=5,
    help="Number of most recent files to sample per collection",
)
@click.option(
    "--output",
    type=Path,
    default=None,
    help="Output report path (default: CHUNK_ANALYSIS_REPORT.md)",
)
@click.pass_context
def analyze(ctx: click.Context, samples: int, output: Path):
    """Analyze collections and recommend optimal chunk sizes.

    Samples the most recent files (by modification time) from each collection
    to provide data-driven chunking recommendations.

    Examples:
      pcortex analyze                    # Analyze with default settings
      pcortex analyze --samples 10       # Sample 10 most recent files per collection
      pcortex analyze --output ~/report.md  # Save report to specific location
    """
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]

    if not config.collections:
        console.print(
            ClaudeStatusDisplay.create_info_panel(
                "No Collections Configured",
                "No RAG collections are configured in your settings",
            )
        )
        return

    # Determine output path
    if output is None:
        output = Path("CHUNK_ANALYSIS_REPORT.md")
    else:
        output = Path(output).expanduser()

    try:
        # Initialize analyzer
        analyzer = DocumentAnalyzer()
        console.print()
        console.print(
            ClaudeStatusDisplay.create_info_panel(
                "Collection Analyzer",
                f"Sampling up to {samples} most recent files per collection",
            )
        )
        console.print()

        # Create progress display
        progress = ClaudeProgress.create_build_progress()
        collection_tasks = {}

        def update_progress(msg: str):
            """Update progress display."""
            console.print(msg)

        # Analyze each collection
        start_time = time.time()
        analysis_results = []

        with Live(progress, console=console, refresh_per_second=10):
            for i, coll_config in enumerate(config.collections):
                # Add task for this collection
                task_id = progress.add_task(
                    f"[bold blue]Analyzing: {coll_config.name}[/bold blue] (sampling {samples} files)",
                    total=None,
                    status="🔍 Scanning",
                )
                collection_tasks[coll_config.name] = task_id

                try:
                    # Analyze collection
                    result = analyzer.analyze_collection(
                        coll_config,
                        max_samples=samples,
                    )
                    analysis_results.append(result)

                    # Update task to complete
                    file_count = len(result.sampled_files)
                    progress.update(
                        task_id,
                        description=f"[bold green]✓ {coll_config.name}[/bold green] ({file_count} sampled, {result.recommended_chunk_size}/{result.recommended_overlap} recommended)",
                        status="✅ Complete",
                    )

                except Exception as e:
                    console.print(f"[red]✗[/red] Error analyzing {coll_config.name}: {e}")
                    if verbose:
                        import traceback

                        console.print(traceback.format_exc())
                    progress.update(
                        task_id,
                        description=f"[bold red]✗ {coll_config.name}[/bold red]",
                        status="❌ Failed",
                    )

        # Generate report
        console.print()
        report_content = analyzer.generate_report(analysis_results)

        # Save report
        output.write_text(report_content, encoding="utf-8")

        # Display summary
        console.print()
        console.print(
            ClaudeStatusDisplay.create_success_panel(
                "Analysis Complete",
                f"Report saved to: {output}",
            )
        )
        console.print()

        # Show summary table
        console.print("[bold cyan]📊 Analysis Summary:[/bold cyan]")
        console.print()

        table = Table(
            show_header=True,
            header_style="bold blue",
            border_style="blue",
        )
        table.add_column("Collection", style="cyan", width=25)
        table.add_column("Current", style="yellow", width=12)
        table.add_column("Recommended", style="green", width=14)
        table.add_column("Change", style="dim", width=15)
        table.add_column("Sampled", style="magenta", width=10)

        for result in analysis_results:
            current = f"{result.current_chunk_size}/{result.current_overlap}"
            recommended = f"{result.recommended_chunk_size}/{result.recommended_overlap}"
            change = result.chunk_change
            sampled = f"{len(result.sampled_files)} files"

            table.add_row(result.collection_name, current, recommended, change, sampled)

        console.print(table)
        console.print()

        # Show timing
        elapsed = time.time() - start_time
        console.print(
            f"[dim]Analysis completed in {elapsed:.1f}s • Analyzed {sum(len(r.sampled_files) for r in analysis_results)} files[/dim]"
        )

        if verbose:
            console.print()
            console.print("[bold cyan]Implementation Steps:[/bold cyan]")
            console.print()
            console.print("1. Update your config.toml with the recommended chunk_size and chunk_overlap values")
            console.print("2. Run: pcortex rebuild --confirm")
            console.print("3. Test with sample queries to verify improved retrieval quality")
            console.print()
            console.print(f"Full report available at: [bold]{output}[/bold]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Analysis cancelled by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[red]✗[/red] Analysis failed: {e}")
        if verbose:
            import traceback

            console.print(traceback.format_exc())
        sys.exit(1)
