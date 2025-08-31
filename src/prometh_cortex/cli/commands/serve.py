"""Serve command for starting the MCP server."""

import sys
import signal
import subprocess
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

console = Console()


@click.command()
@click.option(
    "--port", 
    "-p",
    type=int,
    help="Port to run MCP server on"
)
@click.option(
    "--host",
    type=str,
    help="Host to bind MCP server to"
)
@click.option(
    "--reload", 
    is_flag=True,
    help="Enable auto-reload for development"
)
@click.option(
    "--access-log", 
    is_flag=True,
    help="Enable access logging"
)
@click.pass_context
def serve(ctx: click.Context, port: int, host: str, reload: bool, access_log: bool):
    """Start the MCP server for RAG queries."""
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]
    
    # Use config defaults if not specified
    if port is None:
        port = config.mcp_port
    if host is None:
        host = config.mcp_host
    
    if verbose:
        console.print("[bold blue]Starting MCP server...[/bold blue]")
    
    # Check if index exists (different for FAISS vs Qdrant)
    if config.vector_store_type == "qdrant":
        # For Qdrant, check if we can connect and if collection exists
        try:
            from prometh_cortex.indexer import DocumentIndexer
            indexer = DocumentIndexer(config)
            # Try to get stats to verify index exists
            indexer.get_stats()
        except Exception as e:
            console.print(f"[red]✗[/red] No Qdrant index found. Run 'pcortex build' first. ({e})")
            sys.exit(1)
    else:
        # For FAISS, check file system
        if not config.rag_index_dir.exists() or not any(config.rag_index_dir.iterdir()):
            console.print("[red]✗[/red] No index found. Run 'pcortex build' first.")
            sys.exit(1)
    
    # Display server information
    server_info = f"""[bold cyan]MCP Server Configuration[/bold cyan]

[bold]URL:[/bold] http://{host}:{port}
[bold]Endpoints:[/bold]
  • POST /prometh_cortex_query - Query the RAG index
  • GET  /prometh_cortex_health - Health check
  
[bold]Authentication:[/bold] Bearer {config.mcp_auth_token[:8]}...
[bold]Max Results:[/bold] {config.max_query_results}

[dim]Press Ctrl+C to stop the server[/dim]"""
    
    console.print(Panel(server_info, expand=False, border_style="cyan"))
    
    try:
        # Import and start the server
        from prometh_cortex.server.app import create_app
        
        # Create FastAPI app with config
        app = create_app(config)
        
        # Build uvicorn command
        cmd = [
            "uvicorn",
            "prometh_cortex.server.app:app",
            "--host", host,
            "--port", str(port),
        ]
        
        if reload:
            cmd.append("--reload")
        
        if access_log:
            cmd.append("--access-log")
        else:
            cmd.extend(["--access-log", "--no-access-log"])
        
        if verbose:
            console.print(f"[dim]Starting server with command: {' '.join(cmd)}[/dim]")
        
        # Set environment variable for config
        import os
        os.environ["PROMETH_CORTEX_CONFIG"] = str(config.model_dump_json())
        
        # Start server process
        process = subprocess.Popen(cmd)
        
        # Handle graceful shutdown
        def signal_handler(signum, frame):
            console.print("\n[yellow]Shutting down server...[/yellow]")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Wait for process to complete
        process.wait()
    
    except ImportError as e:
        console.print(f"[red]✗[/red] Failed to import server components: {e}")
        console.print("[yellow]Make sure all dependencies are installed[/yellow]")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[red]✗[/red] Server failed to start: {e}")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        sys.exit(1)