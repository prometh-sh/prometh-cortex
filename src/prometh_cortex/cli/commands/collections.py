"""Collections command for listing and managing RAG collections."""

import sys
import logging

import click
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.panel import Panel

from prometh_cortex.indexer import DocumentIndexer, IndexerError
from prometh_cortex.cli.animations import (
    ClaudeStatusDisplay,
    CLAUDE_COLORS
)

logger = logging.getLogger(__name__)
console = Console()


@click.command()
@click.pass_context
def collections(ctx: click.Context):
    """List all RAG collections and their statistics.

    Multi-collection support (v0.2.0+): Displays all configured collections,
    document counts, chunking parameters, and source patterns for each.

    Examples:
      pcortex collections                 # List all collections
      pcortex collections --verbose       # Detailed collection information
    """
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]

    if not config.collections:
        console.print(ClaudeStatusDisplay.create_info_panel(
            "No Collections Configured",
            "No RAG collections are configured in your settings"
        ))
        return

    try:
        # Beautiful header
        if verbose:
            header_text = Text()
            header_text.append("📚 ", style="bold blue")
            header_text.append("RAG Collections", style="bold blue")
            console.print(ClaudeStatusDisplay.create_info_panel(
                header_text.plain,
                f"Total collections: {len(config.collections)}"
            ))
            console.print()

        # Initialize indexer to get statistics
        try:
            indexer = DocumentIndexer(config)
            indexer.load_index()
            collections_list = indexer.list_collections()
        except IndexerError as e:
            logger.warning(f"Could not load index statistics: {e}")
            collections_list = None

        # Create collections table
        table = Table(
            title=f"[bold cyan]RAG Collections ({len(config.collections)})[/bold cyan]",
            show_header=True,
            header_style="bold blue",
            border_style="blue"
        )

        table.add_column("Collection", style="cyan", width=15)
        table.add_column("Documents", style="green", width=12)
        table.add_column("Chunk Size", style="yellow", width=12)
        table.add_column("Source Patterns", style="dim", width=30)

        for i, coll_config in enumerate(config.collections):
            # Get document count from loaded data if available
            doc_count = "N/A"
            if collections_list and i < len(collections_list):
                coll_info = collections_list[i]
                doc_count = str(coll_info.get("document_count", 0))

            # Format chunk size info
            chunk_info = f"{coll_config.chunk_size}"
            if coll_config.chunk_overlap:
                chunk_info += f" (overlap: {coll_config.chunk_overlap})"

            # Format source patterns
            patterns = ", ".join(coll_config.source_patterns)
            if len(patterns) > 25:
                patterns = patterns[:22] + "..."

            table.add_row(
                coll_config.name,
                doc_count,
                chunk_info,
                patterns
            )

        console.print(table)
        console.print()

        # Show detailed information if verbose
        if verbose:
            for i, coll_config in enumerate(config.collections):
                console.print()
                console.print(f"[bold cyan]Collection: {coll_config.name}[/bold cyan]")
                console.print()

                details_table = Table(
                    show_header=False,
                    border_style="blue"
                )
                details_table.add_column("Property", style="bold cyan", width=18)
                details_table.add_column("Value", style="white")

                details_table.add_row("Chunk Size", str(coll_config.chunk_size))
                details_table.add_row("Chunk Overlap", str(coll_config.chunk_overlap))

                patterns_str = "\n".join(coll_config.source_patterns)
                details_table.add_row("Source Patterns", patterns_str)

                if collections_list and i < len(collections_list):
                    coll_info = collections_list[i]
                    details_table.add_row(
                        "Document Count",
                        str(coll_info.get("document_count", 0))
                    )
                    if coll_info.get("last_updated"):
                        details_table.add_row(
                            "Last Updated",
                            str(coll_info["last_updated"])
                        )

                console.print(details_table)

        # Summary statistics
        console.print()
        if collections_list:
            total_docs = sum(c.get("document_count", 0) for c in collections_list)
            console.print(f"[bold green]Total Documents:[/bold green] {total_docs}")
            console.print()

        # Next steps
        if verbose:
            next_steps = Text()
            next_steps.append("💡 Next steps: ", style="dim")
            next_steps.append("pcortex query 'search term'", style="bold cyan")
            next_steps.append(" or ", style="dim")
            next_steps.append("pcortex query --collection name 'search'", style="bold cyan")
            console.print(next_steps)

    except KeyboardInterrupt:
        console.print()
        console.print("[yellow]⚠  Cancelled by user[/yellow]")
        sys.exit(130)
    except IndexerError as e:
        suggestions = [
            "Run 'pcortex build' to create indexes for your collections",
            "Check your configuration with 'pcortex config --sample'",
            "Verify your DATALAKE_REPOS paths are correct"
        ]
        console.print(ClaudeStatusDisplay.create_error_panel(
            "Collections Error",
            str(e),
            suggestions
        ))
        if verbose:
            import traceback
            console.print(f"\n[dim]Stack trace:\n{traceback.format_exc()}[/dim]")
        sys.exit(1)
    except Exception as e:
        suggestions = [
            "Check your configuration",
            "Run with --verbose for more details",
            "Ensure all dependencies are installed"
        ]
        console.print(ClaudeStatusDisplay.create_error_panel(
            "Unexpected Error",
            f"An unexpected error occurred: {e}",
            suggestions
        ))
        if verbose:
            import traceback
            console.print(f"\n[dim]Stack trace:\n{traceback.format_exc()}[/dim]")
        sys.exit(1)
