#!/usr/bin/env python3
"""
Researcher CLI Tool
Manage research goals and points of interest for bioacoustic analysis
"""

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress
from rich.tree import Tree
from rich.prompt import Confirm
import yaml
import sys
from pathlib import Path
from audio_database import AudioDatabase

console = Console()

@click.group()
@click.option('--config', '-c', required=True, help='YAML configuration file')
@click.option('--dry-run', is_flag=True, help='Show what would be done without executing')
@click.pass_context
def cli(ctx, config, dry_run):
    """Manage research goals and points of interest for bioacoustic analysis"""
    ctx.ensure_object(dict)
    
    # Load config
    try:
        with open(config, 'r') as f:
            ctx.obj['config'] = yaml.safe_load(f)
    except FileNotFoundError:
        console.print(f"[red]❌ Config file not found: {config}[/red]")
        ctx.exit(1)
    except yaml.YAMLError as e:
        console.print(f"[red]❌ Invalid YAML config: {e}[/red]")
        ctx.exit(1)
    
    ctx.obj['config_path'] = config
    ctx.obj['dry_run'] = dry_run
    ctx.obj['db_path'] = ctx.obj['config'].get('database_path')
    
    if not ctx.obj['db_path']:
        console.print("[red]❌ No database_path specified in config file[/red]")
        ctx.exit(1)

@cli.group()
@click.pass_context
def goals(ctx):
    """Manage research goals"""
    if not ctx.obj['dry_run']:
        ctx.obj['db'] = AudioDatabase(ctx.obj['db_path'])

@goals.command('list')
@click.pass_context
def list_goals(ctx):
    """List all research goals"""
    if ctx.obj['dry_run']:
        console.print("[yellow]Would list all research goals[/yellow]")
        return
        
    db = ctx.obj['db']
    goals_data = db.get_goals()
    
    if not goals_data:
        console.print("[dim]No research goals found.[/dim]")
        return
    
    table = Table(title="Research Goals")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="magenta")
    table.add_column("Description", style="green")
    table.add_column("Created", style="dim")
    
    for goal in goals_data:
        table.add_row(
            str(goal['id']),
            goal['title'],
            goal['description'] or "",
            goal['created_at'][:10]
        )
    
    console.print(table)

@goals.command('create')
@click.option('--title', required=True, help='Goal title')
@click.option('--description', help='Goal description')
@click.pass_context
def create_goal(ctx, title, description):
    """Create a new research goal"""
    if ctx.obj['dry_run']:
        console.print(f"[yellow]Would create goal: {title}[/yellow]")
        if description:
            console.print(f"[yellow]  Description: {description}[/yellow]")
        return
    
    db = ctx.obj['db']
    goal_id = db.create_goal(title, description)
    
    console.print(f"[green]✓ Created research goal {goal_id}: {title}[/green]")

@goals.command('show')
@click.argument('goal_id', type=int)
@click.pass_context
def show_goal(ctx, goal_id):
    """Show details of a specific research goal"""
    if ctx.obj['dry_run']:
        console.print(f"[yellow]Would show goal {goal_id}[/yellow]")
        return
    
    db = ctx.obj['db']
    goal = db.get_goal(goal_id)
    
    if not goal:
        console.print(f"[red]❌ Goal {goal_id} not found[/red]")
        return
    
    table = Table(title=f"Research Goal {goal_id}")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    
    table.add_row("Title", goal['title'])
    table.add_row("Description", goal['description'] or "[dim]None[/dim]")
    table.add_row("Created", goal['created_at'])
    
    console.print(table)
    
    # Show associated POIs
    pois = db.get_pois(goal_id=goal_id)
    if pois:
        console.print(f"\n[dim]Associated POIs: {len(pois)}[/dim]")

@goals.command('update')
@click.argument('goal_id', type=int)
@click.option('--title', help='New title')
@click.option('--description', help='New description')
@click.pass_context
def update_goal(ctx, goal_id, title, description):
    """Update a research goal"""
    if not title and not description:
        console.print("[red]❌ Must specify --title or --description[/red]")
        return
    
    if ctx.obj['dry_run']:
        console.print(f"[yellow]Would update goal {goal_id}[/yellow]")
        if title:
            console.print(f"[yellow]  New title: {title}[/yellow]")
        if description:
            console.print(f"[yellow]  New description: {description}[/yellow]")
        return
    
    db = ctx.obj['db']
    success = db.update_goal(goal_id, title=title, description=description)
    
    if success:
        console.print(f"[green]✓ Updated goal {goal_id}[/green]")
    else:
        console.print(f"[red]❌ Goal {goal_id} not found[/red]")

@goals.command('delete')
@click.argument('goal_id', type=int)
@click.option('--force', is_flag=True, help='Skip confirmation prompt')
@click.pass_context
def delete_goal(ctx, goal_id, force):
    """Delete a research goal and all associated POIs"""
    if ctx.obj['dry_run']:
        console.print(f"[yellow]Would delete goal {goal_id} and all associated POIs[/yellow]")
        return
    
    db = ctx.obj['db']
    goal = db.get_goal(goal_id)
    
    if not goal:
        console.print(f"[red]❌ Goal {goal_id} not found[/red]")
        return
    
    # Check for associated POIs
    pois = db.get_pois(goal_id=goal_id)
    
    if not force:
        msg = f"Delete goal '{goal['title']}'"
        if pois:
            msg += f" and {len(pois)} associated POIs"
        msg += "?"
        
        if not Confirm.ask(msg):
            console.print("[dim]Cancelled.[/dim]")
            return
    
    success = db.delete_goal(goal_id)
    
    if success:
        console.print(f"[green]✓ Deleted goal {goal_id}[/green]")
        if pois:
            console.print(f"[green]✓ Deleted {len(pois)} associated POIs[/green]")
    else:
        console.print(f"[red]❌ Failed to delete goal {goal_id}[/red]")

@cli.group()
@click.pass_context  
def poi(ctx):
    """Manage points of interest"""
    if not ctx.obj['dry_run']:
        ctx.obj['db'] = AudioDatabase(ctx.obj['db_path'])

@poi.command('list')
@click.option('--goal-id', type=int, help='Filter by research goal')
@click.option('--limit', type=int, default=50, help='Maximum number of results')
@click.pass_context
def list_pois(ctx, goal_id, limit):
    """List points of interest"""
    if ctx.obj['dry_run']:
        console.print("[yellow]Would list POIs[/yellow]")
        if goal_id:
            console.print(f"[yellow]  Filtered by goal: {goal_id}[/yellow]")
        return
        
    db = ctx.obj['db']
    pois = db.get_pois(goal_id=goal_id, limit=limit)
    
    if not pois:
        console.print("[dim]No POIs found.[/dim]")
        return
    
    table = Table(title="Points of Interest")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Goal", style="blue")
    table.add_column("Label", style="magenta")
    table.add_column("Confidence", style="yellow")
    table.add_column("Created", style="dim")
    
    for poi in pois:
        confidence = f"{poi['confidence']:.1f}" if poi['confidence'] else ""
        table.add_row(
            str(poi['id']),
            poi['goal_title'] or f"Goal {poi['goal_id']}",
            poi['label'],
            confidence,
            poi['created_at'][:10]
        )
    
    console.print(table)

@poi.command('create')
@click.option('--goal-id', type=int, required=True, help='Research goal ID')
@click.option('--label', required=True, help='POI label')
@click.option('--file-path', required=True, help='Audio file path or pattern')
@click.option('--start', type=int, required=True, help='Start time (seconds)')
@click.option('--end', type=int, required=True, help='End time (seconds)')
@click.option('--notes', help='Notes')
@click.option('--confidence', type=float, help='Confidence (0-1)')
@click.option('--anchor-index', help='Anchor index name')
@click.pass_context
def create_poi(ctx, goal_id, label, file_path, start, end, notes, confidence, anchor_index):
    """Create a new point of interest"""
    if ctx.obj['dry_run']:
        console.print(f"[yellow]Would create POI '{label}' for goal {goal_id}[/yellow]")
        console.print(f"[yellow]  File: {file_path}, Time: {start}-{end}s[/yellow]")
        if notes:
            console.print(f"[yellow]  Notes: {notes}[/yellow]")
        if confidence:
            console.print(f"[yellow]  Confidence: {confidence}[/yellow]")
        return
    
    db = ctx.obj['db']
    config = ctx.obj['config']
    
    # Validate goal exists
    goal = db.get_goal(goal_id)
    if not goal:
        console.print(f"[red]❌ Goal {goal_id} not found[/red]")
        return
    
    # Resolve file path
    resolved_files = resolve_file_path(db, file_path, config)
    
    if not resolved_files:
        console.print(f"[red]❌ No files found matching: {file_path}[/red]")
        return
    
    if len(resolved_files) > 1:
        console.print(f"[red]❌ Pattern matches {len(resolved_files)} files. Use specific path.[/red]")
        # Show first few matches
        for i, f in enumerate(resolved_files[:3]):
            console.print(f"[dim]  {f['filename']}[/dim]")
        if len(resolved_files) > 3:
            console.print(f"[dim]  ... and {len(resolved_files) - 3} more[/dim]")
        return
    
    file_record = resolved_files[0]
    
    # Validate time range
    if start >= end:
        console.print("[red]❌ Start time must be less than end time[/red]")
        return
    
    if file_record.get('duration_seconds') and end > file_record['duration_seconds']:
        console.print(f"[red]❌ End time ({end}s) exceeds file duration ({file_record['duration_seconds']:.1f}s)[/red]")
        return
    
    # Create POI
    poi_id = db.create_poi(goal_id, label, notes, confidence, anchor_index)
    
    # Add span with chunk calculation
    config_name = Path(ctx.obj['config_path']).name
    chunk_start, chunk_end = db.calculate_chunks(start, end, config_name, 'spectral')
    
    span_id = db.add_poi_span(
        poi_id, file_record['id'], start, end,
        chunk_start, chunk_end,
        config_name, 'spectral'
    )
    
    console.print(f"[green]✓ Created POI {poi_id}: {label}[/green]")
    console.print(f"[green]  Added span {span_id}: {start}-{end}s in {file_record['filename']}[/green]")
    if chunk_start is not None:
        console.print(f"[dim]  Chunk range: {chunk_start}-{chunk_end}[/dim]")

@poi.command('show')
@click.argument('poi_id', type=int)
@click.pass_context
def show_poi(ctx, poi_id):
    """Show details of a specific POI"""
    if ctx.obj['dry_run']:
        console.print(f"[yellow]Would show POI {poi_id}[/yellow]")
        return
    
    db = ctx.obj['db']
    poi = db.get_poi(poi_id)
    
    if not poi:
        console.print(f"[red]❌ POI {poi_id} not found[/red]")
        return
    
    # POI details table
    table = Table(title=f"Point of Interest {poi_id}")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    
    table.add_row("Label", poi['label'])
    table.add_row("Goal", poi['goal_title'] or f"Goal {poi['goal_id']}")
    table.add_row("Notes", poi['notes'] or "[dim]None[/dim]")
    table.add_row("Confidence", str(poi['confidence']) if poi['confidence'] else "[dim]None[/dim]")
    table.add_row("Anchor Index", poi['anchor_index_name'] or "[dim]None[/dim]")
    table.add_row("Created", poi['created_at'])
    
    console.print(table)
    
    # Spans table
    if poi['spans']:
        console.print("\n[bold]Time Spans:[/bold]")
        spans_table = Table()
        spans_table.add_column("File", style="green")
        spans_table.add_column("Start", style="yellow")
        spans_table.add_column("End", style="yellow")
        spans_table.add_column("Duration", style="cyan")
        spans_table.add_column("Chunks", style="dim")
        
        for span in poi['spans']:
            duration = span['end_time_sec'] - span['start_time_sec']
            chunk_info = ""
            if span['chunk_start'] is not None and span['chunk_end'] is not None:
                chunk_info = f"{span['chunk_start']}-{span['chunk_end']}"
            
            spans_table.add_row(
                span['filename'] or "Unknown",
                f"{span['start_time_sec']}s",
                f"{span['end_time_sec']}s",
                f"{duration}s",
                chunk_info
            )
        
        console.print(spans_table)

@poi.command('search')
@click.option('--confidence-min', type=float, help='Minimum confidence level')
@click.option('--date-from', help='Search from date (YYYY-MM-DD)')
@click.option('--date-to', help='Search to date (YYYY-MM-DD)')
@click.option('--limit', type=int, default=50, help='Maximum results')
@click.pass_context
def search_pois(ctx, confidence_min, date_from, date_to, limit):
    """Search POIs with filters"""
    if ctx.obj['dry_run']:
        console.print("[yellow]Would search POIs with filters:[/yellow]")
        if confidence_min:
            console.print(f"[yellow]  Min confidence: {confidence_min}[/yellow]")
        if date_from:
            console.print(f"[yellow]  From date: {date_from}[/yellow]")
        if date_to:
            console.print(f"[yellow]  To date: {date_to}[/yellow]")
        return
    
    db = ctx.obj['db']
    pois = db.get_pois(date_from=date_from, date_to=date_to, limit=limit)
    
    # Filter by confidence if specified
    if confidence_min:
        pois = [p for p in pois if p['confidence'] and p['confidence'] >= confidence_min]
    
    if not pois:
        console.print("[dim]No POIs found matching criteria.[/dim]")
        return
    
    table = Table(title=f"Search Results ({len(pois)} POIs)")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Goal", style="blue")
    table.add_column("Label", style="magenta")
    table.add_column("Confidence", style="yellow")
    table.add_column("Created", style="dim")
    
    for poi in pois:
        confidence = f"{poi['confidence']:.1f}" if poi['confidence'] else ""
        table.add_row(
            str(poi['id']),
            poi['goal_title'] or f"Goal {poi['goal_id']}",
            poi['label'],
            confidence,
            poi['created_at'][:10]
        )
    
    console.print(table)

@cli.command('stats')
@click.pass_context
def show_stats(ctx):
    """Show database statistics including POI counts"""
    if ctx.obj['dry_run']:
        console.print("[yellow]Would show database statistics[/yellow]")
        return
    
    db = AudioDatabase(ctx.obj['db_path'])
    
    # Create rich statistics display
    table = Table(title="Database Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="magenta")
    
    file_count = db.get_file_count()
    table.add_row("Audio Files", str(file_count))
    
    # Add POI statistics
    goals = db.get_goals()
    table.add_row("Research Goals", str(len(goals)))
    
    all_pois = db.get_pois(limit=1000)  # Get more for accurate count
    table.add_row("Points of Interest", str(len(all_pois)))
    
    # Count total spans
    total_spans = 0
    for poi in all_pois:
        spans = db.get_poi_spans(poi['id'])
        total_spans += len(spans)
    
    table.add_row("Total Spans", str(total_spans))
    
    console.print(table)
    
    # Show date range if files exist
    if file_count > 0:
        date_range = db.get_date_range()
        if date_range and date_range[0]:
            console.print(f"\n[dim]Recording period: {date_range[0][:10]} to {date_range[1][:10]}[/dim]")

@cli.group()
@click.pass_context
def scales(ctx):
    """Manage processing scales"""
    if not ctx.obj['dry_run']:
        ctx.obj['db'] = AudioDatabase(ctx.obj['db_path'])

@scales.command('populate')
@click.pass_context
def populate_scales(ctx):
    """Populate processing scales from config file"""
    if ctx.obj['dry_run']:
        console.print("[yellow]Would populate processing scales from config[/yellow]")
        return
    
    db = ctx.obj['db']
    config = ctx.obj['config']
    config_name = Path(ctx.obj['config_path']).name
    
    db.populate_scales_from_config(config, config_name)
    console.print(f"[green]✓ Populated processing scales from {config_name}[/green]")

@scales.command('list')
@click.pass_context
def list_scales(ctx):
    """List registered processing scales"""
    if ctx.obj['dry_run']:
        console.print("[yellow]Would list processing scales[/yellow]")
        return
    
    db = ctx.obj['db']
    
    # Get all scales (simple query)
    conn = db.get_connection() if hasattr(db, 'get_connection') else None
    if not conn:
        import sqlite3
        conn = sqlite3.connect(db.db_path)
        conn.row_factory = sqlite3.Row
    
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM processing_scales ORDER BY config_name, processing_type")
    scales = cursor.fetchall()
    conn.close()
    
    if not scales:
        console.print("[dim]No processing scales found.[/dim]")
        return
    
    table = Table(title="Processing Scales")
    table.add_column("Config", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Chunk Duration", style="yellow")
    table.add_column("Created", style="dim")
    
    for scale in scales:
        table.add_row(
            scale['config_name'],
            scale['processing_type'],
            f"{scale['chunk_duration_sec']}s",
            scale['created_at'][:10]
        )
    
    console.print(table)

def resolve_file_path(db, file_pattern_or_path, config):
    """Resolve file patterns against database and filesystem"""
    if "*" in file_pattern_or_path:
        return db.search_files_by_path_pattern(file_pattern_or_path)
    else:
        # Direct path resolution
        if not Path(file_pattern_or_path).is_absolute():
            base_dir = config.get('input_directory', '.')
            file_pattern_or_path = str(Path(base_dir) / file_pattern_or_path)
        
        # Find in database
        files = db.search_files(limit=1000)
        return [f for f in files if f['filepath'] == file_pattern_or_path]

if __name__ == '__main__':
    cli()