"""Query command for testing RAG index locally with Claude Code-style animations."""

import sys
import time

import click
from rich.console import Console
from rich.live import Live
from rich.text import Text
from rich.progress import track

from prometh_cortex.indexer import DocumentIndexer, IndexerError
from prometh_cortex.cli.animations import (
    ClaudeProgress,
    ClaudeStatusDisplay,
    ClaudeResultsTable,
    ClaudeAnimator,
    CLAUDE_COLORS
)

console = Console()


@click.command()
@click.argument("search_term", required=True)
@click.option(
    "--max-results",
    "-n",
    type=int,
    help="Maximum number of results to return"
)
@click.option(
    "--show-content",
    is_flag=True,
    help="Show full content snippets in results"
)
@click.option(
    "--show-filters",
    is_flag=True,
    help="Show applied filters and query parsing information"
)
@click.option(
    "--source",
    "-s",
    help="Filter by specific source (default: search all sources)"
)
@click.pass_context
def query(ctx: click.Context, search_term: str, max_results: int, show_content: bool, show_filters: bool, source: str):
    """Query the unified RAG index with optional source filtering.

    Per-source chunking (v0.3.0+): Search across all sources in the unified collection
    or filter by a specific source for more targeted results.

    RECOMMENDED: Use tags for precise filtering, semantic text for content matching.

    Examples:
      pcortex query "meeting notes"                           # Search all sources
      pcortex query "agenda" --source meetings                # Filter by source
      pcortex query "tags:meetings,work discussion"          # Tag filter + semantic text
      pcortex query "created:2024-12-08 agenda"               # Date filtering

    TIP: Run 'pcortex sources' to see available sources.
    """
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]
    
    # Use config default if max_results not specified
    if max_results is None:
        max_results = config.max_query_results

    # Validate source if specified
    if source:
        valid_sources = [s.name for s in config.sources]
        if source not in valid_sources:
            suggestions = [
                f"Available sources: {', '.join(valid_sources)}",
                f"Run 'pcortex sources' to list all sources"
            ]
            console.print(ClaudeStatusDisplay.create_error_panel(
                "Source Not Found",
                f"Source '{source}' does not exist",
                suggestions
            ))
            sys.exit(1)

    # Beautiful header
    if verbose:
        header_text = Text()
        header_text.append("🔍 ", style="bold blue")
        header_text.append("Semantic Search", style="bold blue")

        query_info = [
            f"Query: [bold cyan]'{search_term}'[/bold cyan]",
            f"Max Results: [dim]{max_results}[/dim]",
            f"Vector Store: [bold cyan]{config.vector_store_type.upper()}[/bold cyan]",
        ]

        if source:
            query_info.append(f"Source Filter: [bold yellow]{source}[/bold yellow]")
        else:
            query_info.append(f"Sources: [bold yellow]All ({len(config.sources)})[/bold yellow]")

        console.print(ClaudeStatusDisplay.create_info_panel(
            header_text.plain,
            "\n".join(query_info)
        ))
        console.print()

    # Check if we can query (different logic for FAISS vs Qdrant)
    if config.vector_store_type == 'faiss':
        index_dir = config.rag_index_dir
        if not index_dir.exists() or not any(index_dir.iterdir()):
            suggestions = [
                "Run 'pcortex build' to create your first index",
                "Check your DATALAKE_REPOS path in config",
                "Verify you have markdown files to index"
            ]
            console.print(ClaudeStatusDisplay.create_error_panel(
                "No Index Found",
                "FAISS index directory is empty or doesn't exist",
                suggestions
            ))
            sys.exit(1)

    try:
        # Phase 1: Initialize with animated connection
        progress = ClaudeProgress.create_connection_progress()

        with Live(progress, console=console, refresh_per_second=10):
            connect_task = progress.add_task(
                f"[bold blue]Initializing indexer ({len(config.sources)} sources)...[/bold blue]",
                total=None
            )

            indexer = DocumentIndexer(config)
            progress.update(connect_task, description="[bold blue]Loading unified index...[/bold blue]")
            indexer.load_index()
            progress.update(connect_task, description="[bold green]✓ Connected[/bold green]")
            time.sleep(0.2)  # Let user see the success
        
        # Phase 2: Animated query processing
        query_progress = ClaudeProgress.create_connection_progress()

        with Live(query_progress, console=console, refresh_per_second=10):
            search_task = query_progress.add_task(
                "[bold blue]🧠 Embedding query...[/bold blue]",
                total=None
            )

            start_time = time.time()
            time.sleep(0.3)  # Show embedding phase

            query_progress.update(search_task, description="[bold blue]🔍 Searching vectors...[/bold blue]")
            results = indexer.query(search_term, source_type=source, max_results=max_results)
            query_time = (time.time() - start_time) * 1000

            query_progress.update(search_task, description="[bold green]✓ Search complete[/bold green]")
            time.sleep(0.2)
        
        console.print()
        
        # Display results with beautiful formatting
        if not results:
            console.print(ClaudeStatusDisplay.create_info_panel(
                "No Results",
                f"No semantic matches found for '{search_term}'\nTry different keywords or check your index has content"
            ))
            return
        
        # Performance celebration
        perf_color = "green" if query_time < 100 else "yellow" if query_time < 200 else "red"
        perf_emoji = "⚡" if query_time < 100 else "🐌" if query_time > 500 else "🚀"

        perf_text = Text()
        perf_text.append(f"{perf_emoji} ", style=perf_color)
        perf_text.append(f"Query completed in {query_time:.1f}ms", style=f"bold {perf_color}")
        perf_text.append(f" • Found {len(results)} results", style="dim")

        # Show source breakdown if searching all sources
        if not source and results:
            from collections import Counter
            source_counts = Counter(r.get("source_type", "unknown") for r in results)
            breakdown = ", ".join([f"{s}: {count}" for s, count in sorted(source_counts.items())])
            perf_text.append(f" • {breakdown}", style="dim")

        console.print(perf_text)
        console.print()
        
        # Create beautiful results table
        if show_content:
            table = ClaudeResultsTable.create_query_results(results, search_term)
        else:
            # Compact table without content
            from rich.table import Table
            table = Table(
                title=f"Search Results for: [bold cyan]'{search_term}'[/bold cyan]",
                show_header=True,
                header_style="bold blue",
                border_style="blue"
            )
            
            table.add_column("#", style="dim", width=3)
            table.add_column("Score", style="green", width=8)
            table.add_column("Source File", style="cyan", width=40)
            table.add_column("Preview", style="white")
            
            for i, result in enumerate(results, 1):
                # Score visualization
                score = result.get("similarity_score", 0)
                score_bar = "█" * int(score * 8) + "░" * (8 - int(score * 8))
                score_text = f"{score:.3f}\n[dim]{score_bar}[/dim]"
                
                # Source file
                source = result.get("source_file", "Unknown")
                source_name = source.split("/")[-1] if "/" in source else source
                
                # Content preview
                content = result.get("content", "")[:80]
                if len(content) > 77:
                    content = content + "..."
                
                table.add_row(
                    str(i),
                    score_text,
                    source_name,
                    content
                )
        
        console.print(table)
        
        # Show beautiful top result details if not showing all content
        if not show_content and results:
            console.print()
            top_result = results[0]
            content = top_result.get('content', 'No content available')
            metadata = top_result.get('metadata', {})
            
            # Create metadata table
            if metadata:
                from rich.table import Table
                meta_table = Table(
                    title="[bold blue]📋 Top Result Metadata[/bold blue]",
                    show_header=False,
                    border_style="blue"
                )
                meta_table.add_column("Property", style="bold cyan", width=15)
                meta_table.add_column("Value", style="white")
                
                for key, value in list(metadata.items())[:6]:  # Show first 6 metadata items
                    if isinstance(value, (list, dict)):
                        value = str(value)[:60] + ("..." if len(str(value)) > 60 else "")
                    meta_table.add_row(key.title(), str(value))
                
                console.print(meta_table)
                console.print()
            
            # Beautiful content preview
            content_preview = content[:400] + ("..." if len(content) > 400 else "")
            from rich.panel import Panel
            content_panel = Panel(
                content_preview,
                title="[bold green]📄 Top Result Content[/bold green]",
                border_style="green",
                padding=(1, 2)
            )
            console.print(content_panel)
        
        # Show query parsing information if requested or verbose
        if (show_filters or verbose) and results:
            top_result = results[0]
            query_info = top_result.get('query_info', {})
            if query_info:
                console.print()
                from rich.table import Table
                
                query_table = Table(
                    title="[bold cyan]🔍 Query Analysis[/bold cyan]",
                    show_header=False,
                    border_style="cyan"
                )
                query_table.add_column("Property", style="bold cyan", width=16)
                query_table.add_column("Value", style="white")
                
                query_table.add_row("Original Query", f"[yellow]{query_info.get('original_query', 'N/A')}[/yellow]")
                query_table.add_row("Semantic Query", f"[green]{query_info.get('semantic_query', 'N/A')}[/green]")
                
                applied_filters = query_info.get('applied_filters', {})
                if applied_filters:
                    filter_text = ", ".join([f"{k}={v}" for k, v in applied_filters.items()])
                    query_table.add_row("Applied Filters", f"[blue]{filter_text}[/blue]")
                else:
                    query_table.add_row("Applied Filters", "[dim]None[/dim]")
                
                console.print(query_table)
        
        # Final stats
        if verbose:
            stats_text = Text()
            if len(results) < max_results:
                stats_text.append(f"ℹ️  Only {len(results)} results available ", style="dim")
            stats_text.append(f"📊 Structured search complete", style="bold green")
            console.print()
            console.print(stats_text)
    
    except KeyboardInterrupt:
        console.print()
        from rich.panel import Panel
        cancel_panel = Panel(
            "[yellow]Search cancelled by user[/yellow]",
            title="[yellow]⚠[/yellow] Cancelled",
            border_style="yellow"
        )
        console.print(cancel_panel)
        sys.exit(130)
    except IndexerError as e:
        suggestions = [
            "Check your vector store connection",
            "Ensure index exists (run 'pcortex build')",
            "Try a different search term",
            "Verify your configuration in .env"
        ]
        console.print(ClaudeStatusDisplay.create_error_panel(
            "Query Failed",
            str(e),
            suggestions
        ))
        if verbose:
            import traceback
            console.print(f"\n[dim]Stack trace:\n{traceback.format_exc()}[/dim]")
        sys.exit(1)
    except Exception as e:
        suggestions = [
            "Try running with --verbose for more details",
            "Check if your index is corrupted (rebuild with 'pcortex rebuild')",
            "Ensure all dependencies are installed"
        ]
        console.print(ClaudeStatusDisplay.create_error_panel(
            "Unexpected Error",
            f"An unexpected error occurred during search: {e}",
            suggestions
        ))
        if verbose:
            import traceback
            console.print(f"\n[dim]Stack trace:\n{traceback.format_exc()}[/dim]")
        sys.exit(1)