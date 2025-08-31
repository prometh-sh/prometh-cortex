"""MCP command group for MCP server operations and configuration generation."""

import sys

import click
from rich.console import Console

# Create console that outputs to stderr for MCP server (stdout is used for MCP protocol)
console = Console(file=sys.stderr)


@click.group()
@click.pass_context
def mcp(ctx: click.Context):
    """MCP server operations and configuration management.
    
    This command group provides:
    - start: Start the MCP server for Claude Desktop integration
    - init: Generate configuration files for various MCP clients
    """
    pass


@mcp.command()
@click.pass_context
def start(ctx: click.Context):
    """Start the MCP server for Claude Desktop integration.
    
    This starts a stdio-based MCP server that implements the Model Context Protocol
    for integration with Claude Desktop and other MCP-compatible clients.
    
    The server provides two tools:
    - prometh_cortex_query: Search indexed documents
    - prometh_cortex_health: Get system health status
    """
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]
    
    if verbose:
        console.print("[bold blue]Starting MCP server for Claude Desktop...[/bold blue]")
    
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
    
    try:
        from prometh_cortex.mcp.server import run_mcp_server
        
        # Run the MCP server (this will block and handle stdio communication)
        run_mcp_server()
        
    except ImportError as e:
        console.print(f"[red]✗[/red] Failed to import MCP server: {e}")
        console.print("[yellow]Make sure fastmcp is installed: pip install fastmcp[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] MCP server failed: {e}")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        sys.exit(1)


@mcp.command()
@click.argument("target", type=click.Choice(["claude", "vscode", "codex", "perplexity"]))
@click.option(
    "--output", "-o",
    type=click.Path(),
    help="Output file path (default: print to console)"
)
@click.option(
    "--write", "-w",
    is_flag=True,
    help="Write to standard configuration location"
)
@click.pass_context
def init(ctx: click.Context, target: str, output: str, write: bool):
    """Generate MCP configuration for various clients.
    
    TARGET: Configuration target (claude, vscode, codex, perplexity)
    
    Examples:
    \b
    pcortex mcp init claude                      # Print Claude config
    pcortex mcp init claude --write              # Write to Claude config file  
    pcortex mcp init vscode -o settings.json    # Save VSCode config
    pcortex mcp init codex --write               # Write to Codex config file
    pcortex mcp init perplexity --write          # Write to Perplexity config file
    """
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]
    
    if verbose:
        console.print(f"[bold blue]Generating MCP configuration for {target}...[/bold blue]")
    
    try:
        from .mcp_generators import generate_config
        
        # Generate configuration for the target
        config_data, default_path = generate_config(target, config)
        
        if write:
            # Write to standard location
            import json
            from pathlib import Path
            
            output_path = Path(default_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Handle merging with existing config if needed
            if output_path.exists() and target in ["claude", "vscode", "codex", "perplexity"]:
                try:
                    with open(output_path, 'r') as f:
                        content = f.read()
                        if target == "codex":
                            # For TOML files, parse using tomllib/tomli
                            try:
                                import tomllib
                            except ImportError:
                                import tomli as tomllib
                            existing = tomllib.loads(content)
                        else:
                            # Try to fix common JSON issues (trailing commas)
                            if target in ["vscode", "perplexity"]:
                                import re
                                # Remove trailing commas before closing braces/brackets
                                content = re.sub(r',(\s*[}\]])', r'\1', content)
                            existing = json.loads(content)
                except (json.JSONDecodeError, Exception) as e:
                    console.print(f"[yellow]Warning: Could not parse existing config file ({e}). Creating backup and overwriting.[/yellow]")
                    # Create backup
                    backup_path = output_path.with_suffix(f"{output_path.suffix}.backup")
                    output_path.rename(backup_path)
                    existing = {}
                
                if target == "claude":
                    if "mcpServers" not in existing:
                        existing["mcpServers"] = {}
                    existing["mcpServers"].update(config_data["mcpServers"])
                    config_data = existing
                elif target == "vscode":
                    # VSCode uses "servers" not "mcp.servers"
                    if "servers" not in existing:
                        existing["servers"] = {}
                    existing["servers"].update(config_data["servers"])
                    # Preserve other VSCode MCP config sections like "inputs"
                    config_data = existing
                elif target == "codex":
                    # Codex uses "mcp_servers" in TOML format
                    if "mcp_servers" not in existing:
                        existing["mcp_servers"] = {}
                    existing["mcp_servers"].update(config_data["mcp_servers"])
                    config_data = existing
                elif target == "perplexity":
                    # Perplexity uses simple JSON format, just overwrite
                    pass  # config_data already contains the new configuration
            
            with open(output_path, 'w') as f:
                if target == "codex":
                    # Check if we need custom TOML formatting for inline env table
                    needs_custom_format = any(
                        "_env_inline" in server_config 
                        for server_config in config_data.get("mcp_servers", {}).values()
                    )
                    
                    if needs_custom_format:
                        from .mcp_generators import _format_codex_toml
                        f.write(_format_codex_toml(config_data))
                    else:
                        import tomli_w
                        f.write(tomli_w.dumps(config_data))
                else:
                    json.dump(config_data, f, indent=2)
            
            console.print(f"[green]✓[/green] Configuration written to: {output_path}")
            
        elif output:
            # Write to specified file
            import json
            from pathlib import Path
            
            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w') as f:
                if target == "codex":
                    # Check if we need custom TOML formatting for inline env table
                    needs_custom_format = any(
                        "_env_inline" in server_config 
                        for server_config in config_data.get("mcp_servers", {}).values()
                    )
                    
                    if needs_custom_format:
                        from .mcp_generators import _format_codex_toml
                        f.write(_format_codex_toml(config_data))
                    else:
                        import tomli_w
                        f.write(tomli_w.dumps(config_data))
                else:
                    json.dump(config_data, f, indent=2)
            
            console.print(f"[green]✓[/green] Configuration written to: {output_path}")
            
        else:
            # Print to console
            if target == "codex":
                # Check if we need custom TOML formatting for inline env table
                needs_custom_format = any(
                    "_env_inline" in server_config 
                    for server_config in config_data.get("mcp_servers", {}).values()
                )
                
                if needs_custom_format:
                    from .mcp_generators import _format_codex_toml
                    print(_format_codex_toml(config_data))
                else:
                    import tomli_w
                    print(tomli_w.dumps(config_data))
            else:
                import json
                print(json.dumps(config_data, indent=2))
            
    except ImportError as e:
        console.print(f"[red]✗[/red] Failed to import generator: {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] Configuration generation failed: {e}")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        sys.exit(1)