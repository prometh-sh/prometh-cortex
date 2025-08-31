"""Build command for creating initial RAG index with Claude Code-style animations."""

import sys
import time
from pathlib import Path

import click
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
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
    """Build RAG index from configured datalake repositories.
    
    By default, uses incremental indexing to only process changed files.
    Use --force to rebuild the entire index from scratch.
    """
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]
    
    # Display beautiful header
    if verbose:
        header_text = Text()
        header_text.append("🔨 ", style="bold yellow")
        header_text.append("Building RAG Index", style="bold blue")
        
        config_info = []
        config_info.append(f"Vector Store: [bold cyan]{config.vector_store_type.upper()}[/bold cyan]")
        
        if config.vector_store_type == 'faiss':
            config_info.append(f"Index Directory: [dim]{config.rag_index_dir}[/dim]")
        else:
            config_info.append(f"Qdrant: [dim]{config.qdrant_host}:{config.qdrant_port}[/dim]")
            config_info.append(f"Collection: [dim]{config.qdrant_collection_name}[/dim]")
        
        config_info.append(f"Model: [dim]{config.embedding_model.split('/')[-1]}[/dim]")
        
        if force:
            config_info.append("[yellow]⚡ Force rebuild enabled[/yellow]")
        elif not incremental:
            config_info.append("[yellow]⚠ Incremental indexing disabled[/yellow]")
        
        header_panel = Panel(
            "\n".join(config_info),
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
                f"[bold blue]Connecting to {config.vector_store_type.upper()}...[/bold blue]",
                total=None
            )
            
            indexer = DocumentIndexer(config)
            progress.update(init_task, description="[bold green]✓ Connection established[/bold green]")
            time.sleep(0.3)  # Let user see the success
        
        console.print(ClaudeStatusDisplay.create_success_panel(
            "Indexer Ready",
            f"Connected to {config.vector_store_type.upper()} vector store"
        ))
        console.print()
        
        # Phase 2: Build index with beautiful multi-phase progress
        start_time = time.time()
        build_progress = ClaudeProgress.create_build_progress()
        
        with Live(build_progress, console=console, refresh_per_second=10):
            build_task = build_progress.add_task(
                "[bold blue]Analyzing documents...[/bold blue]",
                total=None,
                status="🔍 Scanning"
            )
            
            # Override incremental setting if force is specified
            force_rebuild = force or (not incremental)
            
            # Simulate multi-phase build process
            build_progress.update(build_task, description="[bold blue]Building vector index...[/bold blue]", status="🚀 Processing")
            
            # Use the new build_index method
            stats = indexer.build_index(force_rebuild=force_rebuild)
            
            build_progress.update(build_task, description="[bold green]✓ Index build complete[/bold green]", status="✅ Done")
        
        # Phase 3: Beautiful results display
        console.print()
        build_time = time.time() - start_time
        
        if stats.get('message') == 'No changes detected':
            # No changes - show info panel
            console.print(ClaudeStatusDisplay.create_info_panel(
                "Index Up to Date",
                f"No changes detected in datalake repositories\nCompleted in {build_time:.1f}s"
            ))
        else:
            # Build completed - show success with celebration
            ClaudeAnimator.celebration_effect(console, "Index Build Complete!")
            
            # Prepare detailed stats
            build_stats = {
                "Build Time": f"{build_time:.1f}s",
                "Added": stats.get('added', 0),
                "Updated": stats.get('updated', 0),
                "Deleted": stats.get('deleted', 0)
            }
            
            if stats.get('failed', 0) > 0:
                build_stats["Failed"] = stats['failed']
            
            console.print(ClaudeStatusDisplay.create_success_panel(
                "Build Successful",
                "Vector index has been updated with your documents",
                build_stats
            ))
            
            # Show errors if any
            if verbose and stats.get('failed', 0) > 0 and 'errors' in stats:
                error_list = []
                for error in stats['errors'][:3]:  # Show first 3 errors
                    error_list.append(error.split(':')[0])  # Just the file name
                if len(stats['errors']) > 3:
                    error_list.append(f"... and {len(stats['errors']) - 3} more")
                
                console.print(ClaudeStatusDisplay.create_error_panel(
                    "Processing Errors",
                    f"{stats['failed']} files failed to process",
                    error_list
                ))
        
        # Storage information panel
        storage_info = {}
        if config.vector_store_type == 'faiss':
            storage_info["Storage"] = f"Local FAISS ({config.rag_index_dir})"
        else:
            storage_info["Storage"] = f"Qdrant ({config.qdrant_host}:{config.qdrant_port})"
        
        # Get final statistics
        if verbose:
            index_stats = indexer.get_stats()
            storage_info.update({
                "Total Documents": index_stats.get('total_documents', index_stats.get('total_vectors', 'Unknown')),
                "Embedding Model": config.embedding_model.split('/')[-1],
                "Vector Store": config.vector_store_type.upper()
            })
        
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
            next_steps.append("pcortex serve", style="bold cyan")
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