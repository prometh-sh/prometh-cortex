"""Command to discover available metadata fields in the index."""

import sys

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from prometh_cortex.indexer import DocumentIndexer, IndexerError

console = Console()


@click.command()
@click.option(
    "--sample-size",
    "-s",
    type=int,
    default=20,
    help="Number of documents to sample for field discovery"
)
@click.pass_context
def fields(ctx: click.Context, sample_size: int):
    """Discover available metadata fields in your indexed documents.
    
    This command analyzes a sample of your indexed documents to show what
    metadata fields are available for filtering, along with recommendations
    for the best filtering strategies.
    
    Examples:
      pcortex fields                    # Discover fields from 20 documents
      pcortex fields --sample-size 50   # Sample more documents
    """
    config = ctx.obj["config"]
    
    try:
        # Initialize indexer
        indexer = DocumentIndexer(config)
        indexer.load_index()
        
        # Discover available fields
        console.print(f"🔍 Analyzing {sample_size} documents to discover available fields...\n")
        field_info = indexer.discover_available_fields(sample_size)
        
        # Display results
        total_docs = field_info['total_documents_sampled']
        fields_data = field_info['fields']
        recommendations = field_info['recommendations']
        
        console.print(f"📊 Analysis complete! Sampled {total_docs} documents.\n")
        
        # Create fields table
        fields_table = Table(
            title="🏷️ Available Metadata Fields",
            show_header=True,
            header_style="bold blue",
            border_style="blue"
        )
        
        fields_table.add_column("Field Name", style="cyan", width=20)
        fields_table.add_column("Type", style="green", width=10)
        fields_table.add_column("Count", style="yellow", width=8)
        fields_table.add_column("Sample Values", style="white", width=40)
        
        # Sort fields by count (most common first)
        sorted_fields = sorted(fields_data.items(), key=lambda x: x[1]['count'], reverse=True)
        
        for field_name, field_data in sorted_fields:
            sample_values = ", ".join(field_data['sample_values'][:3])
            if len(field_data['sample_values']) > 3:
                sample_values += "..."
            
            fields_table.add_row(
                field_name,
                field_data['type'],
                str(field_data['count']),
                sample_values
            )
        
        console.print(fields_table)
        console.print()
        
        # Display hybrid configuration status
        query_config = field_info.get('query_parser_config', {})
        if query_config:
            config_table = Table(
                title="⚙️ Query Parser Configuration (Hybrid Auto-Discovery)",
                show_header=True,
                header_style="bold magenta",
                border_style="magenta"
            )
            config_table.add_column("Field Type", style="cyan", width=20)
            config_table.add_column("Fields", style="white", width=60)
            
            if query_config.get('core_fields'):
                config_table.add_row(
                    "Core Fields", 
                    ", ".join(query_config['core_fields']) + " (always enabled)"
                )
            
            if query_config.get('extended_fields'):
                config_table.add_row(
                    "Extended Fields", 
                    ", ".join(query_config['extended_fields']) + " (user configurable)"
                )
            
            if query_config.get('auto_discovered_fields'):
                config_table.add_row(
                    "Auto-Discovered", 
                    ", ".join(query_config['auto_discovered_fields']) + " (found in documents)"
                )
            
            config_table.add_row(
                "Status",
                f"Auto-discovery: {'✅ Enabled' if query_config.get('auto_discovery_enabled') else '❌ Disabled'} | "
                f"Total available: {len(query_config.get('all_available_fields', []))}"
            )
            
            console.print(config_table)
            console.print()
        
        # Display recommendations
        if recommendations['recommended_for_tags']:
            tag_panel = Panel(
                ", ".join(recommendations['recommended_for_tags']),
                title="🏷️ Best for Tag-Based Filtering",
                title_align="left",
                border_style="green",
                padding=(0, 1)
            )
            console.print(tag_panel)
        
        if recommendations['recommended_for_filtering']:
            filter_panel = Panel(
                ", ".join(recommendations['recommended_for_filtering']),
                title="🔍 Good for Exact Filtering",
                title_align="left",
                border_style="blue",
                padding=(0, 1)
            )
            console.print(filter_panel)
        
        if recommendations['recommended_for_semantic']:
            semantic_panel = Panel(
                ", ".join(recommendations['recommended_for_semantic']),
                title="💭 Better for Semantic Search",
                title_align="left",
                border_style="purple",
                padding=(0, 1)
            )
            console.print(semantic_panel)
        
        # Usage examples
        console.print()
        examples = []
        
        if recommendations['recommended_for_tags']:
            tag_field = recommendations['recommended_for_tags'][0]
            examples.append(f'pcortex query "tags:work,meetings discussion"')
        
        if recommendations['recommended_for_filtering']:
            filter_field = recommendations['recommended_for_filtering'][0]
            if filter_field != 'tags':
                sample_value = fields_data[filter_field]['sample_values'][0].split()[0] if fields_data[filter_field]['sample_values'] else 'value'
                examples.append(f'pcortex query "{filter_field}:{sample_value} project update"')
        
        examples.append('pcortex query "created:2024-12-08 meeting notes"')
        
        if examples:
            examples_text = "\n".join(f"  {ex}" for ex in examples)
            examples_panel = Panel(
                examples_text,
                title="💡 Usage Examples",
                title_align="left",
                border_style="yellow",
                padding=(1, 2)
            )
            console.print(examples_panel)
    
    except IndexerError as e:
        console.print(Panel(
            f"[red]Field discovery failed:[/red] {e}",
            title="❌ Error",
            border_style="red"
        ))
        sys.exit(1)
    except Exception as e:
        console.print(Panel(
            f"[red]Unexpected error:[/red] {e}",
            title="❌ Error", 
            border_style="red"
        ))
        sys.exit(1)