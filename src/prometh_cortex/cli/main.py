"""Main CLI entry point for pcortex commands."""

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel

from prometh_cortex.config import ConfigValidationError, load_config
from prometh_cortex.cli.commands import build, rebuild, query, serve, mcp, health, fields


console = Console()


def display_welcome():
    """Display welcome message with version info in Claude Code style."""
    from prometh_cortex import __version__
    from prometh_cortex.cli.animations import CLAUDE_COLORS
    from rich.text import Text
    from rich.align import Align
    
    # Create beautiful title
    title_text = Text()
    title_text.append("🔥 ", style="bold red")
    title_text.append("Prometh", style="bold cyan")
    title_text.append("Cortex", style="bold blue")
    title_text.append(" ⚡", style="bold yellow")
    
    subtitle_text = Text()
    subtitle_text.append("Multi-Datalake RAG Indexer", style="bold white")
    subtitle_text.append(f" v{__version__}", style="dim")
    
    description = Text()
    description.append("🚀 Local-first RAG system with ", style="dim")
    description.append("MCP integration", style="bold blue")
    description.append(" for Claude, VSCode, and other tools", style="dim")
    
    welcome_content = Text()
    welcome_content.append(title_text)
    welcome_content.append("\n")
    welcome_content.append(subtitle_text)
    welcome_content.append("\n\n")
    welcome_content.append(description)
    
    console.print(Panel(
        Align.center(welcome_content),
        expand=False, 
        border_style=CLAUDE_COLORS["primary"],
        padding=(1, 3)
    ))


@click.group(name="pcortex")
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file (config.toml)"
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose output"
)
@click.version_option(
    package_name="prometh-cortex",
    prog_name="pcortex"
)
@click.pass_context
def cli(ctx: click.Context, config: Optional[Path], verbose: bool):
    """
    Multi-Datalake RAG Indexer CLI.
    
    Index multiple datalake repositories containing Markdown files and expose 
    their content through a local MCP server for RAG workflows.
    """
    # Ensure context object exists
    ctx.ensure_object(dict)
    
    # Store global options in context
    ctx.obj["verbose"] = verbose
    ctx.obj["config_file"] = config

    if verbose:
        display_welcome()

    # Skip config loading for config management commands
    # These commands don't need a valid config to run
    config_commands = ["config"]
    if ctx.invoked_subcommand in config_commands:
        ctx.obj["config"] = None
        return

    # Load and validate configuration for other commands
    try:
        ctx.obj["config"] = load_config(config)
        if verbose:
            console.print(f"[green]✓[/green] Configuration loaded successfully")
            console.print(f"[dim]Datalake repos: {len(ctx.obj['config'].datalake_repos)} configured[/dim]")
    except ConfigValidationError as e:
        console.print(f"[red]✗[/red] Configuration error: {e}")
        console.print("\n[yellow]Tip:[/yellow] Run 'pcortex config --init' to create a config file")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] Unexpected error loading configuration: {e}")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        sys.exit(1)


@cli.command()
@click.option(
    "--sample",
    is_flag=True,
    help="Create sample config.toml file in current directory"
)
@click.option(
    "--init",
    is_flag=True,
    help="Initialize user config directory and create sample config"
)
@click.option(
    "--show-paths",
    is_flag=True,
    help="Show config file search paths"
)
def config(sample: bool, init: bool, show_paths: bool):
    """Manage configuration settings."""
    if init:
        import os
        from pathlib import Path

        # Create XDG config directory
        xdg_config_home = os.getenv("XDG_CONFIG_HOME", str(Path.home() / ".config"))
        config_dir = Path(xdg_config_home) / "prometh-cortex"
        config_file = config_dir / "config.toml"

        try:
            config_dir.mkdir(parents=True, exist_ok=True)
            console.print(f"[green]✓[/green] Created config directory: {config_dir}")

            if config_file.exists():
                console.print(f"[yellow]⚠[/yellow] Config file already exists: {config_file}")
                if not click.confirm("Overwrite existing config?"):
                    console.print("[yellow]Skipped[/yellow]")
                    return

            from prometh_cortex.config.settings import create_sample_config_file
            create_sample_config_file(config_file)
            console.print(f"[green]✓[/green] Created sample config: {config_file}")
            console.print("\n[cyan]Next steps:[/cyan]")
            console.print(f"1. Edit the config file: {config_file}")
            console.print("2. Set your datalake paths in the [datalake] section")
            console.print("3. Run: pcortex build")
        except Exception as e:
            console.print(f"[red]✗[/red] Failed to initialize config: {e}")
            sys.exit(1)
    elif sample:
        from prometh_cortex.config.settings import create_sample_config_file
        try:
            create_sample_config_file()
            console.print("[green]✓[/green] Sample config.toml file created in current directory")
        except Exception as e:
            console.print(f"[red]✗[/red] Failed to create sample config.toml file: {e}")
            sys.exit(1)
    elif show_paths:
        import os
        from pathlib import Path

        xdg_config_home = os.getenv("XDG_CONFIG_HOME", str(Path.home() / ".config"))

        console.print("\n[bold cyan]Config file search paths (in order):[/bold cyan]\n")
        paths = [
            (Path.cwd() / "config.toml", "Current directory (highest priority)"),
            (Path(xdg_config_home) / "prometh-cortex" / "config.toml", "XDG config directory"),
            (Path.home() / ".prometh-cortex" / "config.toml", "Hidden directory in home"),
        ]

        for path, description in paths:
            exists = "✓" if path.exists() else "✗"
            color = "green" if path.exists() else "dim"
            console.print(f"  [{color}]{exists}[/{color}] {path}")
            console.print(f"      {description}\n")

        console.print("[cyan]Tip:[/cyan] Use 'pcortex config --init' to create config in XDG directory")
    else:
        console.print("Manage prometh-cortex configuration\n")
        console.print("Options:")
        console.print("  --sample      Create sample config.toml in current directory")
        console.print("  --init        Initialize user config directory (recommended)")
        console.print("  --show-paths  Show config file search paths")


# Add command groups
cli.add_command(build.build)
cli.add_command(rebuild.rebuild) 
cli.add_command(query.query)
cli.add_command(serve.serve)
cli.add_command(mcp.mcp)
cli.add_command(health.health)
cli.add_command(fields.fields)


def main():
    """Main entry point for the CLI."""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[red]✗[/red] Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()