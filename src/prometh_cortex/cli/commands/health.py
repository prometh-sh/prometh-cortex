"""Health command for checking system status with Claude Code-style dashboard."""

import sys
import time
from pathlib import Path

import click
from rich.console import Console
from rich.live import Live
from rich.text import Text
from rich.columns import Columns
from rich.panel import Panel

from prometh_cortex.indexer import DocumentIndexer, IndexerError
from prometh_cortex.cli.animations import (
    ClaudeProgress,
    ClaudeStatusDisplay,
    ClaudeResultsTable,
    CLAUDE_COLORS
)

console = Console()


@click.command()
@click.option(
    "--detailed",
    "-d",
    is_flag=True,
    help="Show detailed system metrics and diagnostics"
)
@click.pass_context
def health(ctx: click.Context, detailed: bool):
    """Check system health and display beautiful dashboard."""
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]
    
    # Beautiful header
    header_text = Text()
    header_text.append("🏥 ", style="bold green")
    header_text.append("System Health Check", style="bold green")
    
    console.print(Panel(
        header_text,
        border_style=CLAUDE_COLORS["success"],
        padding=(1, 2)
    ))
    console.print()
    
    # Phase 1: Connection check with animation
    progress = ClaudeProgress.create_connection_progress()
    health_data = {}
    
    with Live(progress, console=console, refresh_per_second=10):
        check_task = progress.add_task(
            "[bold blue]Checking connections...[/bold blue]",
            total=None
        )
        
        start_time = time.time()
        
        try:
            # Test indexer initialization
            progress.update(check_task, description="[bold blue]Testing indexer...[/bold blue]")
            indexer = DocumentIndexer(config)
            
            progress.update(check_task, description="[bold blue]Loading index...[/bold blue]")
            indexer.load_index()
            
            # Get comprehensive stats
            progress.update(check_task, description="[bold blue]Gathering metrics...[/bold blue]")
            stats = indexer.get_stats()
            health_data.update(stats)
            
            progress.update(check_task, description="[bold green]✓ All systems operational[/bold green]")
            time.sleep(0.3)
            
        except Exception as e:
            progress.update(check_task, description="[bold red]✗ Health check failed[/bold red]")
            health_data["error"] = str(e)
            time.sleep(0.5)
    
    console.print()
    health_check_time = (time.time() - start_time) * 1000
    
    # Phase 2: Display beautiful dashboard
    if "error" in health_data:
        # Error state
        suggestions = [
            "Check your vector store connection",
            "Verify your .env configuration",
            "Run 'pcortex build' if no index exists",
            "Check network connectivity for Qdrant"
        ]
        console.print(ClaudeStatusDisplay.create_error_panel(
            "System Unhealthy",
            health_data["error"],
            suggestions
        ))
        sys.exit(1)
    else:
        # Healthy state - show beautiful dashboard
        health_data["health_check_time_ms"] = health_check_time
        health_table = ClaudeResultsTable.create_health_dashboard(health_data)
        console.print(health_table)
        console.print()
        
        # Performance metrics
        perf_color = "green" if health_check_time < 100 else "yellow" if health_check_time < 500 else "red"
        perf_emoji = "⚡" if health_check_time < 100 else "🚀" if health_check_time < 500 else "🐌"
        
        perf_text = Text()
        perf_text.append(f"{perf_emoji} ", style=perf_color)
        perf_text.append(f"Health check completed in {health_check_time:.1f}ms", style=f"bold {perf_color}")
        console.print(perf_text)
        
        # Show detailed metrics if requested
        if detailed:
            console.print()
            console.print(ClaudeStatusDisplay.create_info_panel(
                "Detailed Diagnostics",
                _create_detailed_diagnostics(config, health_data, health_check_time)
            ))
        
        # System status celebration
        if health_check_time < 100 and health_data.get("total_documents", 0) > 0:
            from prometh_cortex.cli.animations import ClaudeAnimator
            ClaudeAnimator.celebration_effect(console, "System Running Perfectly!")


def _create_detailed_diagnostics(config, health_data, check_time):
    """Create detailed diagnostic information."""
    details = []
    
    # Configuration details
    details.append("[bold blue]📋 Configuration:[/bold blue]")
    details.append(f"  Vector Store: {config.vector_store_type.upper()}")
    details.append(f"  Embedding Model: {config.embedding_model}")
    details.append(f"  Chunk Size: {config.chunk_size}")
    details.append(f"  Max Results: {config.max_query_results}")
    
    if config.vector_store_type == 'faiss':
        details.append(f"  Index Directory: {config.rag_index_dir}")
    else:
        details.append(f"  Qdrant Host: {config.qdrant_host}:{config.qdrant_port}")
        details.append(f"  Collection: {config.qdrant_collection_name}")
        details.append(f"  HTTPS: {config.qdrant_use_https}")
    
    details.append("")
    
    # Performance metrics
    details.append("[bold green]🚀 Performance:[/bold green]")
    details.append(f"  Health Check: {check_time:.1f}ms")
    if "query_time" in health_data:
        details.append(f"  Last Query Time: {health_data['query_time']:.1f}ms")
    
    details.append("")
    
    # Storage metrics
    details.append("[bold cyan]💾 Storage:[/bold cyan]")
    if "total_documents" in health_data:
        details.append(f"  Documents: {health_data['total_documents']:,}")
    if "total_vectors" in health_data:
        details.append(f"  Vectors: {health_data['total_vectors']:,}")
    if "index_size" in health_data:
        details.append(f"  Index Size: {health_data['index_size']}")
    
    # Datalake info
    details.append("")
    details.append("[bold yellow]📂 Datalakes:[/bold yellow]")
    for i, repo in enumerate(config.datalake_repos, 1):
        details.append(f"  {i}. {repo}")
        if repo.exists():
            try:
                md_files = len(list(repo.rglob("*.md")))
                details.append(f"     └── {md_files} markdown files")
            except:
                details.append(f"     └── (access error)")
        else:
            details.append(f"     └── [red](path not found)[/red]")
    
    return "\n".join(details)


if __name__ == "__main__":
    health()