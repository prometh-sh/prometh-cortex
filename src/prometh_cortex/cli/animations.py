"""Claude Code-style animations and progress indicators for pcortex CLI."""

import time
from typing import Any, Dict, List, Optional, Union
from rich.progress import (
    Progress, 
    SpinnerColumn, 
    TextColumn, 
    BarColumn, 
    TaskProgressColumn,
    TimeElapsedColumn,
    MofNCompleteColumn,
    TimeRemainingColumn
)
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich.columns import Columns
from rich.spinner import Spinner
from rich.style import Style

# Claude Code-inspired color palette
CLAUDE_COLORS = {
    "primary": "#FF8C42",      # Claude's signature orange
    "success": "#10B981",      # Green for success states
    "info": "#3B82F6",         # Blue for info
    "warning": "#F59E0B",      # Amber for warnings
    "error": "#EF4444",        # Red for errors
    "muted": "#6B7280",        # Gray for secondary text
    "accent": "#8B5CF6",       # Purple for highlights
    "background": "#1F2937",   # Dark background
    "surface": "#374151",      # Card/panel background
}

class ClaudeSpinner:
    """Claude Code-style spinner with smooth animations."""
    
    SPINNERS = {
        "dots": "dots",
        "line": "line", 
        "bouncingBall": "bouncingBall",
        "clock": "clock",
        "earth": "earth"
    }
    
    @staticmethod
    def create(
        text: str = "Processing...", 
        spinner: str = "dots",
        style: str = CLAUDE_COLORS["primary"]
    ) -> SpinnerColumn:
        """Create a Claude Code-style spinner."""
        return SpinnerColumn(
            style=style
        )

class ClaudeProgress:
    """Claude Code-style progress bars and displays."""
    
    @staticmethod
    def create_build_progress() -> Progress:
        """Create a multi-phase build progress display."""
        return Progress(
            SpinnerColumn(
                style=CLAUDE_COLORS["primary"]
            ),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(
                bar_width=40,
                style=CLAUDE_COLORS["primary"],
                complete_style=CLAUDE_COLORS["success"],
                finished_style=CLAUDE_COLORS["success"]
            ),
            MofNCompleteColumn(),
            "•",
            TimeElapsedColumn(),
            "•", 
            TextColumn("[dim]{task.fields[status]}", justify="right"),
            console=Console(),
            expand=True
        )
    
    @staticmethod
    def create_file_progress() -> Progress:
        """Create file-by-file processing progress."""
        return Progress(
            SpinnerColumn(
                style=CLAUDE_COLORS["accent"]
            ),
            TextColumn("[dim]Processing:"),
            TextColumn("[bold white]{task.fields[filename]}", justify="left"),
            BarColumn(bar_width=20, style=CLAUDE_COLORS["info"]),
            TaskProgressColumn(),
            "•",
            TextColumn("[dim cyan]{task.fields[rate]}/s"),
            console=Console(),
            expand=True
        )
    
    @staticmethod
    def create_connection_progress() -> Progress:
        """Create Qdrant/server connection progress."""
        return Progress(
            SpinnerColumn(
                style=CLAUDE_COLORS["info"]
            ),
            TextColumn("[bold]{task.description}"),
            TimeElapsedColumn(),
            console=Console()
        )

class ClaudeStatusDisplay:
    """Claude Code-style status displays and dashboards."""
    
    @staticmethod
    def create_success_panel(title: str, content: str, stats: Optional[Dict[str, Any]] = None) -> Panel:
        """Create a success panel with stats."""
        content_text = Text(content)
        
        if stats:
            stats_table = Table.grid(padding=(0, 2))
            for key, value in stats.items():
                stats_table.add_row(
                    Text(f"{key}:", style="dim"),
                    Text(str(value), style="bold white")
                )
            content_text = Columns([content_text, stats_table])
        
        return Panel(
            content_text,
            title=f"[green]✓[/green] {title}",
            border_style="green",
            padding=(1, 2)
        )
    
    @staticmethod
    def create_info_panel(title: str, content: Union[str, Table]) -> Panel:
        """Create an info panel."""
        return Panel(
            content,
            title=f"[blue]ℹ[/blue] {title}",
            border_style="blue",
            padding=(1, 2)
        )
    
    @staticmethod
    def create_error_panel(title: str, error: str, suggestions: Optional[List[str]] = None) -> Panel:
        """Create an error panel with suggestions."""
        content = Text(error, style="red")
        
        if suggestions:
            content.append("\n\n")
            content.append("Suggestions:", style="bold yellow")
            for suggestion in suggestions:
                content.append(f"\n• {suggestion}", style="dim yellow")
        
        return Panel(
            content,
            title=f"[red]✗[/red] {title}",
            border_style="red",
            padding=(1, 2)
        )

class ClaudeResultsTable:
    """Claude Code-style results tables with highlighting."""
    
    @staticmethod
    def create_query_results(results: List[Dict[str, Any]], query: str) -> Table:
        """Create a beautiful query results table."""
        table = Table(
            title=f"Search Results for: [bold cyan]'{query}'[/bold cyan]",
            show_header=True,
            header_style="bold blue",
            border_style="blue"
        )
        
        table.add_column("Score", style="green", width=8)
        table.add_column("Source", style="cyan", width=30)
        table.add_column("Content Preview", style="white", width=60)
        
        for result in results:
            # Create similarity score bar
            score = result.get("similarity_score", 0)
            score_bar = "█" * int(score * 10) + "░" * (10 - int(score * 10))
            score_text = f"{score:.2f}\n[dim]{score_bar}[/dim]"
            
            # Format source file
            source = result.get("source_file", "Unknown")
            source_text = source.split("/")[-1] if "/" in source else source
            
            # Format content preview with highlighting
            content = result.get("content", "")[:150]
            if len(content) > 147:
                content = content + "..."
            
            table.add_row(
                score_text,
                source_text,
                content
            )
        
        return table
    
    @staticmethod
    def create_health_dashboard(stats: Dict[str, Any]) -> Table:
        """Create a health dashboard table."""
        table = Table(
            title="[bold green]System Health Dashboard[/bold green]",
            show_header=False,
            border_style="green",
            box=None
        )
        
        table.add_column("Metric", style="bold blue", width=25)
        table.add_column("Value", style="white", width=30)
        table.add_column("Status", style="green", width=15)
        
        # Vector store info
        store_type = stats.get("vector_store_type", "unknown")
        table.add_row("Vector Store", store_type.upper(), "✓ Active")
        
        # Index statistics
        total_docs = stats.get("total_documents", stats.get("total_vectors", 0))
        table.add_row("Documents Indexed", str(total_docs), "✓ Ready")
        
        # Performance metrics
        health_time = stats.get("health_check_time_ms", 0)
        perf_status = "✓ Fast" if health_time < 100 else "⚠ Slow"
        table.add_row("Health Check Time", f"{health_time:.1f}ms", perf_status)
        
        # Embedding model
        model = stats.get("embedding_model", "Unknown")
        model_short = model.split("/")[-1] if "/" in model else model
        table.add_row("Embedding Model", model_short, "✓ Loaded")
        
        return table

class ClaudeAnimator:
    """Claude Code-style animation effects."""
    
    @staticmethod
    def typewriter_effect(console: Console, text: str, delay: float = 0.03) -> None:
        """Typewriter effect like Claude Code's responses."""
        with console.capture() as capture:
            for char in text:
                console.print(char, end="", style="white")
                time.sleep(delay)
        
    @staticmethod
    def fade_in_panel(console: Console, panel: Panel, steps: int = 10) -> None:
        """Fade in effect for panels."""
        for i in range(steps + 1):
            opacity = i / steps
            style = Style(color="white", bgcolor=None, dim=(opacity < 1.0))
            with Live(panel, console=console, refresh_per_second=20):
                time.sleep(0.05)
    
    @staticmethod
    def celebration_effect(console: Console, message: str) -> None:
        """Celebration animation for successful operations."""
        celebration_text = Text()
        celebration_text.append("🎉 ", style="bold yellow")
        celebration_text.append(message, style="bold green")
        celebration_text.append(" 🎉", style="bold yellow")
        
        panel = Panel(
            Align.center(celebration_text),
            border_style="green",
            padding=(1, 4)
        )
        
        console.print(panel)
        time.sleep(0.5)