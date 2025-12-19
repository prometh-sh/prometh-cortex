"""Sources command for listing and managing RAG document sources."""

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
def sources(ctx: click.Context):
    """List all document sources and their configuration.

    Per-source chunking (v0.3.0+): Displays all configured sources,
    chunking parameters, and source patterns for the unified collection.

    Examples:
      pcortex sources                 # List all sources
      pcortex sources --verbose       # Detailed source information
    """
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]

    if not config.sources:
        console.print(ClaudeStatusDisplay.create_info_panel(
            "No Sources Configured",
            "No document sources are configured in your settings"
        ))
        return

    try:
        # Beautiful header
        if verbose:
            header_text = Text()
            header_text.append("📚 ", style="bold blue")
            header_text.append("Document Sources", style="bold blue")
            console.print(ClaudeStatusDisplay.create_info_panel(
                header_text.plain,
                f"Collection: {config.collection.name} • Sources: {len(config.sources)}"
            ))
            console.print()

        # Initialize indexer to get statistics
        try:
            indexer = DocumentIndexer(config)
            indexer.load_index()
            sources_list = indexer.list_sources()
        except IndexerError as e:
            logger.warning(f"Could not load index statistics: {e}")
            sources_list = None

        # Create sources table
        table = Table(
            title=f"[bold cyan]Document Sources ({len(config.sources)})[/bold cyan]",
            show_header=True,
            header_style="bold blue",
            border_style="blue"
        )

        table.add_column("Source", style="cyan", width=15)
        table.add_column("Chunk Size", style="yellow", width=12)
        table.add_column("Overlap", style="yellow", width=10)
        table.add_column("Source Patterns", style="dim", width=40)

        for source_config in config.sources:
            # Get document count from loaded data if available
            doc_count = "—"
            if sources_list:
                for src in sources_list.get("sources", []):
                    if src.get("name") == source_config.name:
                        doc_count = str(src.get("document_count", 0))
                        break

            patterns = ", ".join(source_config.source_patterns)
            if len(patterns) > 40:
                patterns = patterns[:37] + "..."

            table.add_row(
                source_config.name,
                str(source_config.chunk_size),
                str(source_config.chunk_overlap),
                patterns
            )

        console.print(table)
        console.print()

        # Collection information panel
        collection_info = {
            "Collection Name": config.collection.name,
            "Vector Store": config.vector_store_type.upper(),
            "Total Sources": len(config.sources),
        }

        if sources_list:
            collection_info["Total Documents"] = sources_list.get("total_documents", 0)

        if config.vector_store_type == 'faiss':
            collection_info["Storage Path"] = str(config.rag_index_dir)
        else:
            collection_info["Qdrant Host"] = f"{config.qdrant_host}:{config.qdrant_port}"

        info_panel_text = "\n".join([
            f"{k}: [bold white]{v}[/bold white]"
            for k, v in collection_info.items()
        ])

        console.print(ClaudeStatusDisplay.create_info_panel(
            "Collection Information",
            info_panel_text
        ))

        if verbose:
            # Show source patterns details
            console.print()
            console.print("[bold cyan]📋 Source Pattern Details:[/bold cyan]")
            console.print()

            for source_config in config.sources:
                pattern_text = "[dim]" + ", ".join(source_config.source_patterns) + "[/dim]"
                source_info = (
                    f"[bold cyan]{source_config.name}[/bold cyan]\n"
                    f"  Chunk Size: {source_config.chunk_size}\n"
                    f"  Overlap: {source_config.chunk_overlap}\n"
                    f"  Patterns: {pattern_text}"
                )
                console.print(Panel(source_info, border_style="blue", padding=(0, 1)))

    except Exception as e:
        logger.error(f"Error listing sources: {e}")
        console.print(ClaudeStatusDisplay.create_error_panel(
            "Error",
            f"Failed to list sources: {str(e)}"
        ))
        sys.exit(1)
