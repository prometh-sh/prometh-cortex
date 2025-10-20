"""Build command for creating RAG indexes with multi-collection support."""

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
    """Build RAG indexes for all collections from datalake repositories.

    By default, uses incremental indexing to only process changed files.
    Use --force to rebuild the entire index from scratch.

    Multi-collection support (v0.2.0+): Documents are automatically routed
    to collections based on configured source patterns. Each collection
    maintains independent indexes with optimized chunking parameters.
    """
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]

    # Display beautiful header with collection info
    if verbose:
        header_text = Text()
        header_text.append("🔨 ", style="bold yellow")
        header_text.append("Building RAG Indexes", style="bold blue")

        # Show collection configuration
        collections_info = []
        for coll in config.collections:
            patterns_str = ", ".join(coll.source_patterns[:2])
            if len(coll.source_patterns) > 2:
                patterns_str += f", +{len(coll.source_patterns)-2} more"
            collections_info.append(
                f"[cyan]{coll.name}[/cyan]: chunk_size={coll.chunk_size}, patterns=[{patterns_str}]"
            )

        config_content = (
            f"[bold cyan]Collections ({len(config.collections)})[/bold cyan]:\n" +
            "\n".join(f"  • {info}" for info in collections_info)
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
                f"[bold blue]Initializing {len(config.collections)} collections...[/bold blue]",
                total=None
            )

            indexer = DocumentIndexer(config)
            progress.update(init_task, description="[bold green]✓ Collections initialized[/bold green]")
            time.sleep(0.3)  # Let user see the success

        console.print(ClaudeStatusDisplay.create_success_panel(
            "Multi-Collection Indexer Ready",
            f"Initialized {len(config.collections)} collections with {config.vector_store_type.upper()}"
        ))
        console.print()

        # Phase 2: Build indexes with beautiful multi-phase progress
        start_time = time.time()
        build_progress = ClaudeProgress.create_build_progress()

        with Live(build_progress, console=console, refresh_per_second=10):
            build_task = build_progress.add_task(
                "[bold blue]Analyzing documents and routing to collections...[/bold blue]",
                total=None,
                status="🔍 Scanning"
            )

            # Override incremental setting if force is specified
            force_rebuild = force or (not incremental)

            # Simulate multi-phase build process
            build_progress.update(
                build_task,
                description="[bold blue]Building collection indexes...[/bold blue]",
                status="🚀 Processing"
            )

            # Build all collections
            stats = indexer.build_index(force_rebuild=force_rebuild)

            build_progress.update(
                build_task,
                description="[bold green]✓ Index build complete[/bold green]",
                status="✅ Done"
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
            stats.get("collections", {}).get(c, {}).get("added", 0) == 0
            and stats.get("collections", {}).get(c, {}).get("failed", 0) == 0
            for c in stats.get("collections", {})
        ):
            # No changes detected in any collection
            console.print(ClaudeStatusDisplay.create_info_panel(
                "All Collections Up to Date",
                f"No changes detected in any collection\nCompleted in {build_time:.1f}s"
            ))
        else:
            # Build completed - show success with celebration
            ClaudeAnimator.celebration_effect(console, "Index Build Complete!")

            # Create per-collection statistics table
            if len(config.collections) > 1 or verbose:
                console.print()
                console.print("[bold cyan]📊 Per-Collection Statistics:[/bold cyan]")
                console.print()

                table = Table(show_header=True, header_style="bold blue", border_style="blue")
                table.add_column("Collection", style="cyan")
                table.add_column("Added", style="green")
                table.add_column("Failed", style="red")
                table.add_column("Status", style="yellow")

                for coll_name, coll_stats in stats.get("collections", {}).items():
                    added = coll_stats.get("added", 0)
                    failed = coll_stats.get("failed", 0)
                    status = "✓" if failed == 0 else f"⚠ {failed} failed"

                    table.add_row(coll_name, str(added), str(failed), status)

                console.print(table)
                console.print()

            # Overall statistics
            total_added = stats.get("total_added", 0)
            total_failed = stats.get("total_failed", 0)

            build_stats = {
                "Total Documents Indexed": total_added,
                "Build Time": f"{build_time:.1f}s",
            }

            if total_failed > 0:
                build_stats["Failed Documents"] = total_failed

            console.print(ClaudeStatusDisplay.create_success_panel(
                "Build Successful",
                f"Successfully indexed documents across {len(config.collections)} collections",
                build_stats
            ))

            # Show errors if any
            if verbose and total_failed > 0 and stats.get("errors"):
                error_list = []
                for error in stats["errors"][:5]:  # Show first 5 errors
                    error_list.append(error.split(":")[0] if ":" in error else error)
                if len(stats["errors"]) > 5:
                    error_list.append(f"... and {len(stats['errors']) - 5} more")

                console.print(ClaudeStatusDisplay.create_error_panel(
                    "Processing Errors",
                    f"{total_failed} documents failed to process",
                    error_list
                ))

        # Storage information panel
        storage_info = {}
        if config.vector_store_type == 'faiss':
            storage_info["Storage"] = f"Local FAISS ({config.rag_index_dir}/collections/)"
        else:
            storage_info["Storage"] = f"Qdrant ({config.qdrant_host}:{config.qdrant_port})"

        storage_info["Collections"] = len(config.collections)
        storage_info["Embedding Model"] = config.embedding_model.split("/")[-1]

        # Get final statistics
        if verbose:
            index_stats = indexer.get_stats()
            storage_info["Vector Store"] = config.vector_store_type.upper()
            storage_info["Total Collections"] = index_stats.get("total_collections", len(config.collections))

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
            next_steps.append("pcortex collections", style="bold cyan")
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