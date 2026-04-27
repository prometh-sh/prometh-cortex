"""Memory command group for managing session memories."""

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from prometh_cortex.vector_store import create_vector_store
from prometh_cortex.utils.time_parser import (
    parse_time_filter,
    format_timestamp,
)

console = Console()


@click.group()
def memory():
    """Manage session memories (prmth_memory source).

    Memories are stored separately from indexed documents and survive
    force rebuilds. Use these commands to list and clear them.
    """
    pass


@memory.command("list")
@click.option(
    "--since",
    type=str,
    help="Filter by creation time: relative (7d, 2w) or absolute (2026-03-01)",
)
@click.option(
    "--project",
    type=str,
    help="Filter by project (metadata.project field)",
)
@click.option(
    "--tag",
    type=str,
    help="Filter by tag",
)
@click.pass_context
def memory_list(ctx: click.Context, since: str, project: str, tag: str):
    """List memory documents.

    Examples:
      pcortex memory list                              # All memories
      pcortex memory list --since 7d                   # Last 7 days
      pcortex memory list --since 2026-03-01           # Since specific date
      pcortex memory list --project myproject          # By project
      pcortex memory list --since 7d --project test    # Combined filters
    """
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]

    try:
        # Create vector store directly (faster than full indexer)
        vector_store = create_vector_store(config)
        vector_store.initialize()

        # Parse time filter
        since_ts = None
        if since:
            since_ts = parse_time_filter(since)
            if since_ts is None:
                console.print(
                    Panel(
                        f"[red]Invalid time format: '{since}'[/red]\n\n"
                        "Use relative format (7d, 2w, 24h) or absolute (2026-03-01)",
                        title="Error",
                        expand=False,
                    )
                )
                raise click.Exit(1)

        # List memories directly from vector store
        memories = vector_store.list_memory_documents(since=since_ts, project=project, tag=tag)

        if not memories:
            console.print(
                Panel(
                    "[yellow]No memories found matching the filters[/yellow]",
                    title="Memory List",
                )
            )
            return

        # Create results table
        table = Table(
            title=f"Memory Documents ({len(memories)} total)",
            show_header=True,
            header_style="bold cyan",
            expand=True,
        )
        table.add_column("ID", style="dim", no_wrap=True)
        table.add_column("Title", style="white", min_width=50)
        table.add_column("Created", style="green", no_wrap=True)
        table.add_column("Tags", style="blue")
        table.add_column("Project", style="magenta")

        for memory in memories:
            doc_id = memory.get("document_id", "N/A")
            # No truncation - full ID needed for memory forget --id

            title = memory.get("title", "N/A")
            # Title will wrap naturally in Rich table with ratio=2

            created = memory.get("created", "N/A")
            if created and "T" in created:
                created = created.split("T")[0]

            tags = memory.get("tags", [])
            tags_str = ", ".join(tags[:3])
            if len(tags) > 3:
                tags_str += f" (+{len(tags) - 3})"

            project_val = memory.get("project", "-")
            if project_val:
                if len(project_val) > 20:
                    project_val = project_val[:17] + "..."

            table.add_row(doc_id, title, created, tags_str, project_val)

        console.print(table)

    except Exception as e:
        console.print(
            Panel(
                f"[red]Error: {e}[/red]",
                title="Error",
                expand=False,
            )
        )
        if verbose:
            raise
        raise click.Exit(1)


@memory.command("forget")
@click.option(
    "--all",
    "forget_all",
    is_flag=True,
    help="Delete all memory documents",
)
@click.option(
    "--expiry",
    type=str,
    help="Delete memories older than N days or before date (7d or 2026-03-01)",
)
@click.option(
    "--project",
    type=str,
    help="Delete memories from specific project",
)
@click.option(
    "--id",
    "doc_id",
    type=str,
    help="Delete specific memory by document_id",
)
@click.option(
    "--confirm",
    is_flag=True,
    help="Skip confirmation prompt",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview what would be deleted without actually deleting",
)
@click.pass_context
def memory_forget(
    ctx: click.Context,
    forget_all: bool,
    expiry: str,
    project: str,
    doc_id: str,
    confirm: bool,
    dry_run: bool,
):
    """Forget memory documents.

    At least one filter option is required (--all, --expiry, --project, or --id).

    Examples:
      pcortex memory forget --all                          # Delete all
      pcortex memory forget --expiry 30d                   # Older than 30 days
      pcortex memory forget --expiry 2026-03-01            # Before date
      pcortex memory forget --project archive              # By project
      pcortex memory forget --id memory_abc123             # Specific memory
      pcortex memory forget --expiry 7d --project test     # Combined filters
      pcortex memory forget --expiry 30d --dry-run         # Preview only
      pcortex memory forget --all --confirm                # No prompt
    """
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]

    # Validate that at least one filter is provided
    if not (forget_all or expiry or project or doc_id):
        console.print(
            Panel(
                "[red]At least one filter option is required:[/red]\n"
                "  --all              Delete all memories\n"
                "  --expiry <time>    Delete older than N days/date\n"
                "  --project <name>   Delete by project\n"
                "  --id <doc_id>      Delete specific memory",
                title="Error: No Filters",
                expand=False,
            )
        )
        raise click.Exit(1)

    try:
        # Create vector store directly
        vector_store = create_vector_store(config)
        vector_store.initialize()

        # Parse expiry filter if provided
        expiry_ts = None
        if expiry:
            expiry_ts = parse_time_filter(expiry)
            if expiry_ts is None:
                console.print(
                    Panel(
                        f"[red]Invalid time format: '{expiry}'[/red]\n\n"
                        "Use relative format (7d, 2w, 24h) or absolute (2026-03-01)",
                        title="Error",
                        expand=False,
                    )
                )
                raise click.Exit(1)

        # Preview what will be deleted
        if forget_all:
            memories = vector_store.list_memory_documents()
            preview_text = f"[red]About to delete ALL {len(memories)} memory documents![/red]\n\n"
            preview_text += "[yellow]This cannot be undone.[/yellow]"
            doc_ids_to_delete = [m.get("document_id") for m in memories if m.get("document_id")]
        elif doc_id:
            preview_text = f"Memory: [bold cyan]{doc_id}[/bold cyan]"
            doc_ids_to_delete = [doc_id]
        else:
            # For expiry: filter OUT documents newer than expiry_ts (keep only older ones)
            all_memories = vector_store.list_memory_documents(project=project)
            memories = []
            if expiry_ts:
                # Only include documents created BEFORE expiry_ts (i.e., older than expiry)
                from datetime import datetime
                for mem in all_memories:
                    created_str = mem.get("created")
                    if created_str:
                        try:
                            created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                            created_ts = created_dt.timestamp()
                            if created_ts < expiry_ts:
                                memories.append(mem)
                        except Exception:
                            pass
            else:
                memories = all_memories
            
            preview_text = f"Found {len(memories)} memory document(s) to delete:\n\n"
            for mem in memories[:5]:
                title = mem.get("title", "N/A")
                if len(title) > 50:
                    title = title[:47] + "..."
                preview_text += f"  • {title}\n"
            if len(memories) > 5:
                preview_text += f"\n  ... and {len(memories) - 5} more\n"
            doc_ids_to_delete = [m.get("document_id") for m in memories if m.get("document_id")]

        console.print(Panel(preview_text, title="Preview", expand=False))

        # If dry-run, stop here
        if dry_run:
            console.print("[yellow]Dry-run mode: no changes made[/yellow]")
            return

        # Prompt for confirmation if not using --confirm
        if not confirm:
            if not click.confirm("\nProceed with deletion?", default=False):
                console.print("[yellow]Cancelled.[/yellow]")
                return

        # Perform deletion
        console.print("[bold]Deleting memories...[/bold]")
        deleted_count = vector_store.delete_memory_documents(doc_ids_to_delete)

        console.print(
            Panel(
                f"[green]✓ Successfully deleted {deleted_count} memory document(s)[/green]",
                title="Success",
                expand=False,
            )
        )

    except Exception as e:
        console.print(
            Panel(
                f"[red]Error: {e}[/red]",
                title="Error",
                expand=False,
            )
        )
        if verbose:
            raise
        raise click.Exit(1)
