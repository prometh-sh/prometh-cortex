"""Rebuild command for recreating the entire RAG index."""

import shutil
import sys

import click
from rich.console import Console

from prometh_cortex.cli.commands.build import build as build_command
from prometh_cortex.indexer import DocumentIndexer, IndexerError


console = Console()


@click.command()
@click.option(
    "--confirm", 
    is_flag=True,
    help="Skip confirmation prompt"
)
@click.pass_context
def rebuild(ctx: click.Context, confirm: bool):
    """Rebuild the entire RAG index from scratch."""
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]
    
    if verbose:
        console.print("[bold red]Rebuilding RAG index...[/bold red]")
        console.print(f"Vector store type: {config.vector_store_type}")
    
    # Check if index exists (handle both FAISS and Qdrant)
    index_exists = False
    if config.vector_store_type == 'faiss':
        index_exists = config.rag_index_dir.exists() and any(config.rag_index_dir.iterdir())
    else:
        # For Qdrant, we need to check if there's existing data
        try:
            indexer = DocumentIndexer(config)
            stats = indexer.get_stats()
            index_exists = stats.get('total_vectors', 0) > 0 or stats.get('total_points', 0) > 0
        except Exception:
            index_exists = False
    
    if not index_exists:
        console.print("[yellow]No existing index found. Running initial build instead.[/yellow]")
        ctx.invoke(build_command, force=False, incremental=True)
        return
    
    # Confirm rebuild unless --confirm flag is used
    if not confirm:
        if config.vector_store_type == 'faiss':
            console.print(f"[yellow]This will delete the existing index at:[/yellow] {config.rag_index_dir}")
        else:
            console.print(f"[yellow]This will delete the existing index in Qdrant:[/yellow] {config.qdrant_host}:{config.qdrant_port}")
        if not click.confirm("Are you sure you want to rebuild the index?"):
            console.print("Rebuild cancelled")
            return
    
    try:
        # Remove existing index using the indexer
        if verbose:
            console.print("[yellow]Removing existing index...[/yellow]")
        
        indexer = DocumentIndexer(config)
        indexer.delete_index()
        
        # For FAISS, also remove the directory
        if config.vector_store_type == 'faiss' and config.rag_index_dir.exists():
            shutil.rmtree(config.rag_index_dir)
        
        console.print("[green]✓[/green] Existing index removed")
        
        # Build new index with force rebuild
        ctx.invoke(build_command, force=True, incremental=True)
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Rebuild cancelled by user[/yellow]")
        sys.exit(130)
    except IndexerError as e:
        console.print(f"[red]✗[/red] Rebuild failed: {e}")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] Unexpected error during rebuild: {e}")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        sys.exit(1)