"""Build command for creating RAG indexes with per-source chunking."""

import sys
import time
from pathlib import Path

import click
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.align import Align

from prometh_cortex.indexer import DocumentIndexer, IndexerError
from prometh_cortex.cli.animations import (
    ClaudeProgress,
    ClaudeStatusDisplay,
    ClaudeAnimator,
    CLAUDE_COLORS
)

console = Console()


@click.command()
@click.option(
    "--force",
    is_flag=True,
    help="Force complete rebuild ignoring incremental changes"
)
@click.option(
    "--incremental/--no-incremental",
    default=True,
    help="Use incremental indexing (default: enabled)"
)
@click.pass_context
def build(ctx: click.Context, force: bool, incremental: bool):
    """Build unified RAG index from datalake repositories with per-source chunking.

    By default, uses incremental indexing to only process changed files.
    Use --force to rebuild the entire index from scratch.

    Per-source chunking (v0.3.0+): Documents are automatically routed
    to sources based on configured source patterns. Each source has
    optimized chunking parameters, all indexed into a single unified collection.
    """
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]

    # Display beautiful header with source info
    if verbose:
        header_text = Text()
        header_text.append("🔨 ", style="bold yellow")
        header_text.append("Building Unified RAG Index", style="bold blue")

        # Show source configuration
        sources_info = []
        for source in config.sources:
            patterns_str = ", ".join(source.source_patterns[:2])
            if len(source.source_patterns) > 2:
                patterns_str += f", +{len(source.source_patterns)-2} more"
            sources_info.append(
                f"[cyan]{source.name}[/cyan]: chunk_size={source.chunk_size}, patterns=[{patterns_str}]"
            )

        config_content = (
            f"[bold cyan]Sources ({len(config.sources)})[/bold cyan]:\n" +
            "\n".join(f"  • {info}" for info in sources_info)
        )
        
        config_info = []
        config_info.append(f"Vector Store: [bold cyan]{config.vector_store_type.upper()}[/bold cyan]")

        if config.vector_store_type == 'faiss':
            config_info.append(f"Index Directory: [dim]{config.rag_index_dir}[/dim]")
        else:
            config_info.append(f"Qdrant: [dim]{config.qdrant_host}:{config.qdrant_port}[/dim]")

        config_info.append(f"Model: [dim]{config.embedding_model.split('/')[-1]}[/dim]")

        if force:
            config_info.append("[yellow]⚡ Force rebuild enabled[/yellow]")
        elif not incremental:
            config_info.append("[yellow]⚠ Incremental indexing disabled[/yellow]")

        header_panel = Panel(
            config_content + "\n\n" + "\n".join(config_info),
            title=header_text.plain,
            border_style=CLAUDE_COLORS["primary"],
            padding=(1, 2)
        )

        console.print(header_panel)
        console.print()  # Add spacing

    # For FAISS, create index directory if it doesn't exist
    if config.vector_store_type == 'faiss':
        config.rag_index_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Phase 1: Initialize indexer with Claude Code-style progress
        progress = ClaudeProgress.create_connection_progress()

        with Live(progress, console=console, refresh_per_second=10):
            init_task = progress.add_task(
                f"[bold blue]Initializing unified collection with {len(config.sources)} sources...[/bold blue]",
                total=None
            )

            indexer = DocumentIndexer(config)
            progress.update(init_task, description="[bold green]✓ Unified collection initialized[/bold green]")
            time.sleep(0.3)  # Let user see the success

        console.print(ClaudeStatusDisplay.create_success_panel(
            "Unified RAG Indexer Ready",
            f"Initialized {len(config.sources)} sources with {config.vector_store_type.upper()}"
        ))
        console.print()

        # Phase 2: Build index with beautiful multi-phase progress
        start_time = time.time()
        build_progress = ClaudeProgress.create_build_progress()

        # Dictionary to track per-source progress tasks
        source_tasks = {}

        def progress_callback(event_type: str, source_name: str, data: dict):
            """Callback to handle source-level progress updates."""
            if event_type == "start":
                # Create a new task for this source
                doc_count = data.get("doc_count", 0)
                task_id = build_progress.add_task(
                    f"[bold blue]Indexing: {source_name}[/bold blue] ({doc_count} docs)",
                    total=None,
                    status="🚀 Processing"
                )
                source_tasks[source_name] = task_id

            elif event_type == "complete":
                # Update task to show completion
                if source_name in source_tasks:
                    documents = data.get("documents", 0)
                    chunks = data.get("chunks", 0)
                    status_str = f"✓ {chunks} chunks" if chunks > 0 else "✓"
                    build_progress.update(
                        source_tasks[source_name],
                        description=f"[bold green]✓ {source_name}[/bold green] ({documents} docs)",
                        status=f"✅ {status_str}"
                    )

            elif event_type == "error":
                # Update task to show error
                if source_name in source_tasks:
                    error_msg = data.get("error", "Unknown error")
                    build_progress.update(
                        source_tasks[source_name],
                        description=f"[bold red]✗ {source_name}[/bold red]",
                        status=f"❌ {error_msg[:30]}..."
                    )

        with Live(build_progress, console=console, refresh_per_second=10):
            # Override incremental setting if force is specified
            force_rebuild = force or (not incremental)

            # Build all collections with progress callback
            stats = indexer.build_index(
                force_rebuild=force_rebuild,
                progress_callback=progress_callback
            )

        # Phase 3: Beautiful results display with per-collection statistics
        console.print()
        build_time = time.time() - start_time

        if stats.get('message') == 'No documents found':
            # No documents found
            console.print(ClaudeStatusDisplay.create_info_panel(
                "No Documents Found",
                "No markdown files found in datalake repositories\nCheck your DATALAKE_REPOS paths"
            ))
        elif all(
            stats.get("sources", {}).get(s, {}).get("documents", 0) == 0
            for s in stats.get("sources", {})
        ):
            # No changes detected in any source
            console.print(ClaudeStatusDisplay.create_info_panel(
                "Index Already Up to Date",
                f"No changes detected in any source\nCompleted in {build_time:.1f}s"
            ))
        else:
            # Build completed - show success with celebration
            ClaudeAnimator.celebration_effect(console, "Index Build Complete!")

            # Create per-source statistics table
            if len(config.sources) > 1 or verbose:
                console.print()
                console.print("[bold cyan]📊 Per-Source Statistics:[/bold cyan]")
                console.print()

                table = Table(show_header=True, header_style="bold blue", border_style="blue")
                table.add_column("Source", style="cyan")
                table.add_column("Documents", style="green")
                table.add_column("Chunks", style="yellow")
                table.add_column("Status", style="yellow")

                for source_name, source_stats in stats.get("sources", {}).items():
                    documents = source_stats.get("documents", 0)
                    chunks = source_stats.get("chunks", 0)
                    status = "✓" if documents > 0 else "—"

                    table.add_row(source_name, str(documents), str(chunks), status)

                console.print(table)
                console.print()

            # Overall statistics
            total_documents = stats.get("total_documents", 0)
            total_chunks = stats.get("total_chunks", 0)

            build_stats = {
                "Total Documents Indexed": total_documents,
                "Total Chunks Created": total_chunks,
                "Build Time": f"{build_time:.1f}s",
            }

            console.print(ClaudeStatusDisplay.create_success_panel(
                "Build Successful",
                f"Successfully indexed documents from {len(config.sources)} sources into unified collection",
                build_stats
            ))

            # Show errors if any (only if there are actual errors in stats)
            if verbose and stats.get("errors"):
                error_list = []
                for error in stats["errors"][:5]:  # Show first 5 errors
                    error_list.append(error.split(":")[0] if ":" in error else error)
                if len(stats["errors"]) > 5:
                    error_list.append(f"... and {len(stats['errors']) - 5} more")

                console.print(ClaudeStatusDisplay.create_error_panel(
                    "Processing Errors",
                    f"{len(stats.get('errors', []))} errors occurred during indexing",
                    error_list
                ))

        # Storage information panel
        storage_info = {}
        if config.vector_store_type == 'faiss':
            storage_info["Storage"] = f"Local FAISS ({config.rag_index_dir})"
        else:
            storage_info["Storage"] = f"Qdrant ({config.qdrant_host}:{config.qdrant_port})"

        storage_info["Collection"] = config.collection.name
        storage_info["Sources"] = len(config.sources)
        storage_info["Embedding Model"] = config.embedding_model.split("/")[-1]

        # Get final statistics
        if verbose:
            index_stats = indexer.get_stats()
            storage_info["Vector Store"] = config.vector_store_type.upper()

        console.print(ClaudeStatusDisplay.create_info_panel(
            "Index Statistics",
            "\n".join([f"{k}: [bold white]{v}[/bold white]" for k, v in storage_info.items()])
        ))

        if verbose:
            console.print()
            next_steps = Text()
            next_steps.append("🚀 Ready for queries! ", style="bold green")
            next_steps.append("Try: ", style="dim")
            next_steps.append("pcortex query 'your search'", style="bold cyan")
            next_steps.append(" or ", style="dim")
            next_steps.append("pcortex sources", style="bold cyan")
            console.print(next_steps)
    
    except KeyboardInterrupt:
        console.print()
        cancel_panel = Panel(
            "[yellow]Build cancelled by user[/yellow]\nYou can resume with 'pcortex build' for incremental updates",
            title="[yellow]⚠[/yellow] Cancelled",
            border_style="yellow",
            padding=(1, 2)
        )
        console.print(cancel_panel)
        sys.exit(130)
    except IndexerError as e:
        suggestions = [
            "Check your Qdrant connection if using Qdrant",
            "Verify datalake paths exist and are readable", 
            "Try 'pcortex build --force' for a clean rebuild",
            "Check disk space for FAISS index storage"
        ]
        console.print(ClaudeStatusDisplay.create_error_panel(
            "Index Build Failed",
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
            "Check your .env configuration file",
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