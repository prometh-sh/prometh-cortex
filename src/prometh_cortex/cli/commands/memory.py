"""Memory command group for managing session memories."""

import sys
import click
import json
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from prometh_cortex.vector_store import create_vector_store
from prometh_cortex.indexer import DocumentIndexer
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
@click.option(
    "--dreaming",
    "filter_dreaming",
    type=click.Choice(["true", "false", "all"]),
    default="false",
    help="Filter by consolidation status: true=consolidated, false=active (default), all=both",
)
@click.pass_context
def memory_list(ctx: click.Context, since: str, project: str, tag: str, filter_dreaming: str):
    """List memory documents.

    Examples:
      pcortex memory list                              # All active memories
      pcortex memory list --dreaming true              # Consolidated-away memories
      pcortex memory list --dreaming all               # All memories
      pcortex memory list --since 7d                   # Last 7 days (active)
      pcortex memory list --since 2026-03-01           # Since specific date
      pcortex memory list --project myproject          # By project (active)
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
                sys.exit(1)

        # Determine dreaming filter
        dreaming_filter = None
        if filter_dreaming == "true":
            dreaming_filter = True
        elif filter_dreaming == "false":
            dreaming_filter = False
        # elif filter_dreaming == "all": dreaming_filter stays None

        # List memories directly from vector store
        memories = vector_store.list_memory_documents(
            since=since_ts, project=project, tag=tag, dreaming=dreaming_filter
        )

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
        table.add_column("Detail", style="yellow", min_width=25)

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

            # Build Detail column with memory consolidation info
            detail_lines = []
            
            # Line 1: type and dreaming status
            memory_type = memory.get("memory_type", "episodic")
            dreaming = memory.get("dreaming", False)
            dreaming_str = "✓" if dreaming else "-"
            detail_lines.append(f"type={memory_type}  dream={dreaming_str}")
            
            # Line 2: consolidation version and ID (if present)
            cons_version = memory.get("consolidation_version")
            cons_id = memory.get("consolidation_id")
            if cons_version is not None or cons_id:
                line2 = ""
                if cons_version is not None:
                    line2 += f"v{cons_version}"
                if cons_id:
                    # Show last 8 chars of ID
                    cons_id_short = cons_id[-8:] if len(cons_id) > 8 else cons_id
                    if line2:
                        line2 += f"  cons={cons_id_short}"
                    else:
                        line2 = f"cons={cons_id_short}"
                if line2:
                    detail_lines.append(line2)
            
            # Line 3: source memories (if any)
            source_mems = memory.get("source_memories", [])
            if source_mems:
                src_display = ", ".join([m[-6:] if len(m) > 6 else m for m in source_mems[:2]])
                if len(source_mems) > 2:
                    src_display += f" (+{len(source_mems) - 2})"
                detail_lines.append(f"src={src_display}")
            
            # Line 4: supersedes (if any)
            supersedes = memory.get("supersedes", [])
            if supersedes:
                sup_display = ", ".join([m[-6:] if len(m) > 6 else m for m in supersedes[:2]])
                if len(supersedes) > 2:
                    sup_display += f" (+{len(supersedes) - 2})"
                detail_lines.append(f"sup={sup_display}")
            
            detail_str = "\n".join(detail_lines)

            table.add_row(doc_id, title, created, tags_str, project_val, detail_str)

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
        sys.exit(1)


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
    "--dreaming",
    "filter_dreaming",
    type=click.Choice(["true", "false"]),
    help="Delete only consolidated (true) or only active (false) memories",
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
    filter_dreaming: str,
    confirm: bool,
    dry_run: bool,
):
    """Forget memory documents.

    At least one filter option is required (--all, --expiry, --project, --id, or --dreaming).

    Examples:
      pcortex memory forget --all                          # Delete all
      pcortex memory forget --dreaming true                # Delete all consolidated memories
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
    if not (forget_all or expiry or project or doc_id or filter_dreaming):
        console.print(
            Panel(
                "[red]At least one filter option is required:[/red]\n"
                "  --all              Delete all memories\n"
                "  --expiry <time>    Delete older than N days/date\n"
                "  --project <name>   Delete by project\n"
                "  --id <id>          Delete specific memory\n"
                "  --dreaming true    Delete consolidated memories",
                title="Error: No Filters",
                expand=False,
            )
        )
        sys.exit(1)

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
                sys.exit(1)

        # Parse dreaming filter
        dreaming_filter = None
        if filter_dreaming:
            dreaming_filter = filter_dreaming == "true"

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
            # For expiry/project/dreaming: apply filters to get matching memories
            all_memories = vector_store.list_memory_documents(
                project=project, dreaming=dreaming_filter
            )
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
        sys.exit(1)


@memory.command("dream")
@click.option(
    "--project",
    type=str,
    required=True,
    help="Project name to consolidate memories for",
)
@click.option(
    "--revert",
    "consolidation_id",
    type=str,
    help="Revert a consolidation by consolidated memory ID",
)
@click.option(
    "--keep-consolidated",
    is_flag=True,
    help="When reverting, keep the consolidated memory (don't delete it)",
)
@click.option(
    "--confirm",
    is_flag=True,
    help="Skip confirmation prompt",
)
@click.pass_context
def memory_dream(
    ctx: click.Context,
    project: str,
    consolidation_id: str,
    keep_consolidated: bool,
    confirm: bool,
):
    """Manage memory consolidation (dreaming).

    Consolidation workflow: retrieve episodic memories, synthesize them with LLM,
    commit consolidated semantic memory, optionally revert if needed.

    For consolidation (multi-step): Use MCP tools directly from your agent:
      1. prometh_cortex_memory_dream_prepare(project) → episodic + prior semantic
      2. (LLM synthesis step)
      3. prometh_cortex_memory_dream_commit(project, ...) → new consolidated memory

    Examples:
      pcortex memory dream --project myproject              # Show prepare data
      pcortex memory dream --project myproject --revert ID  # Revert consolidation
      pcortex memory dream --project myproject --revert ID --keep-consolidated
    """
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]

    try:
        # Create indexer (no initialize needed)
        indexer = DocumentIndexer(config)

        if consolidation_id:
            # REVERT MODE
            vector_store = create_vector_store(config)
            vector_store.initialize()

            # Fetch the consolidated memory
            consolidated_mems = vector_store.list_memory_documents(dreaming=None)
            consolidated_mems = [
                m for m in consolidated_mems if m.get("document_id") == consolidation_id
            ]

            if not consolidated_mems:
                console.print(
                    Panel(
                        f"[red]Consolidated memory not found: {consolidation_id}[/red]",
                        title="Error",
                        expand=False,
                    )
                )
                sys.exit(1)

            consolidated_mem = consolidated_mems[0]
            source_ids = consolidated_mem.get("source_memories", [])
            supersede_ids = consolidated_mem.get("supersedes", [])

            preview_text = (
                f"Consolidation ID: [bold cyan]{consolidation_id[-8:]}...[/bold cyan]\n"
                f"Title: {consolidated_mem.get('title', 'N/A')}\n\n"
                f"Will restore:\n"
                f"  • {len(source_ids)} source episodic memories\n"
                f"  • {len(supersede_ids)} superseded semantic memories\n"
            )
            if keep_consolidated:
                preview_text += "\nConsolidated memory will [yellow]NOT be deleted[/yellow]"
            else:
                preview_text += "\nConsolidated memory will be [red]DELETED[/red]"

            console.print(Panel(preview_text, title="Revert Preview", expand=False))

            if not confirm:
                if not click.confirm("\nProceed with revert?", default=False):
                    console.print("[yellow]Cancelled.[/yellow]")
                    return

            # Perform revert
            console.print("[bold]Reverting consolidation...[/bold]")

            restored_count = 0
            for mem_id in source_ids + supersede_ids:
                try:
                    indexer.update_memory_metadata(mem_id, {"dreaming": False})
                    restored_count += 1
                except Exception as e:
                    console.print(f"[yellow]Warning: Failed to restore {mem_id}: {e}[/yellow]")

            if not keep_consolidated:
                try:
                    indexer.delete_memories([consolidation_id])
                except Exception as e:
                    console.print(f"[yellow]Warning: Failed to delete consolidated memory: {e}[/yellow]")

            console.print(
                Panel(
                    f"[green]✓ Revert successful[/green]\n"
                    f"Restored {restored_count} memories\n"
                    f"Consolidated memory: {'kept' if keep_consolidated else 'deleted'}",
                    title="Success",
                    expand=False,
                )
            )

        else:
            # PREPARE MODE: Show memories ready for consolidation
            episodic_mems = indexer.list_memories(
                project=project, dreaming=False
            )
            episodic_mems = [
                m for m in episodic_mems if m.get("memory_type") == "episodic"
            ]

            prior_semantic = indexer.list_memories(project=project, dreaming=False)
            prior_semantic = [
                m for m in prior_semantic if m.get("memory_type") == "semantic"
            ]

            if not episodic_mems and not prior_semantic:
                console.print(
                    Panel(
                        "[yellow]No memories found for consolidation[/yellow]",
                        title="Dream Prepare",
                    )
                )
                return

            # Display prepare results in table
            table = Table(
                title=f"Dream Prepare for '{project}'",
                show_header=True,
                header_style="bold cyan",
                expand=True,
            )
            table.add_column("ID", style="dim", no_wrap=True)
            table.add_column("Type", style="blue", no_wrap=True)
            table.add_column("Title", style="white", min_width=40)
            table.add_column("Created", style="green", no_wrap=True)

            for mem in episodic_mems:
                doc_id = mem.get("document_id", "N/A")
                title = mem.get("title", "N/A")
                created = mem.get("created", "N/A")
                if created and "T" in created:
                    created = created.split("T")[0]
                table.add_row(doc_id, "[blue]episodic[/blue]", title, created)

            for mem in prior_semantic:
                doc_id = mem.get("document_id", "N/A")
                title = mem.get("title", "N/A")
                created = mem.get("created", "N/A")
                if created and "T" in created:
                    created = created.split("T")[0]
                table.add_row(doc_id, "[magenta]semantic[/magenta]", title, created)

            console.print(table)

            # Print next steps
            console.print(
                Panel(
                    "[cyan]Next steps:[/cyan]\n"
                    "1. Review memories above\n"
                    "2. Use MCP tool [bold]prometh_cortex_memory_dream_prepare[/bold](project) to fetch full content\n"
                    "3. Synthesize memories with LLM\n"
                    "4. Use MCP tool [bold]prometh_cortex_memory_dream_commit[/bold] to save consolidated memory\n\n"
                    f"[dim]To revert later: pcortex memory dream --project {project} --revert <consolidated_id>[/dim]",
                    title="Instructions",
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
        sys.exit(1)
