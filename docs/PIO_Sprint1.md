# PIO CLI Implementation Plan (Sprint 1)

## Overview
Create a CLI-first approach for managing research goals and Points of Interest (POIs) by extending the existing Python database infrastructure with a `researcher.py` tool. This approach keeps POI management in the core research toolkit alongside `audio_database.py` and `scan_audio_database.py`.

**Dependencies Added**: Rich (beautiful CLI output) and Click (command-line parsing)

## Phase 1: Extend AudioDatabase Class

### Database Schema Extensions
Extend `audio_database.py` to include POI tables in the `init_database()` method:

```sql
-- Add to existing init_database() method:
CREATE TABLE IF NOT EXISTS research_goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS points_of_interest (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id INTEGER REFERENCES research_goals(id),
    label TEXT NOT NULL,
    notes TEXT,
    confidence REAL CHECK (confidence >= 0 AND confidence <= 1),
    anchor_index_name TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS poi_spans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    poi_id INTEGER NOT NULL REFERENCES points_of_interest(id) ON DELETE CASCADE,
    file_id INTEGER NOT NULL REFERENCES audio_files(id),
    start_time_sec INTEGER NOT NULL,
    end_time_sec INTEGER NOT NULL,
    chunk_start INTEGER,
    chunk_end INTEGER,
    config_name TEXT,
    processing_type TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CHECK (start_time_sec < end_time_sec)
);

CREATE TABLE IF NOT EXISTS processing_scales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_name TEXT NOT NULL,
    processing_type TEXT NOT NULL,
    chunk_duration_sec REAL NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(config_name, processing_type)
);

-- Add config_name to existing tables
ALTER TABLE audio_files ADD COLUMN config_name TEXT;
ALTER TABLE acoustic_indices_core ADD COLUMN config_name TEXT;

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_poi_spans_file_time ON poi_spans(file_id, start_time_sec, end_time_sec);
CREATE INDEX IF NOT EXISTS idx_poi_spans_poi ON poi_spans(poi_id);
CREATE INDEX IF NOT EXISTS idx_points_of_interest_goal ON points_of_interest(goal_id);
```

### AudioDatabase Method Extensions
Add POI management methods to the existing `AudioDatabase` class:

```python
# Research Goals
def create_goal(self, title, description=None):
    """Create a new research goal"""
    
def get_goals(self):
    """Get all research goals"""
    
def get_goal(self, goal_id):
    """Get a specific research goal by ID"""
    
def update_goal(self, goal_id, title=None, description=None):
    """Update a research goal"""
    
def delete_goal(self, goal_id):
    """Delete a research goal and all associated POIs"""

# Points of Interest  
def create_poi(self, goal_id, label, notes=None, confidence=None, anchor_index_name=None):
    """Create a new point of interest"""
    
def get_pois(self, goal_id=None, file_id=None, date_from=None, date_to=None, limit=100):
    """Get POIs with optional filtering"""
    
def get_poi(self, poi_id):
    """Get a specific POI with its spans"""
    
def update_poi(self, poi_id, **kwargs):
    """Update POI properties"""
    
def delete_poi(self, poi_id):
    """Delete a POI and all its spans"""

# POI Spans
def add_poi_span(self, poi_id, file_id, start_time_sec, end_time_sec, 
                 chunk_start=None, chunk_end=None, config_name=None, processing_type=None):
    """Add a time span to an existing POI"""
    
def get_poi_spans(self, poi_id):
    """Get all spans for a POI"""
    
def delete_poi_span(self, span_id):
    """Delete a specific POI span"""

# Processing Scales
def register_scale(self, config_name, processing_type, chunk_duration_sec):
    """Register a processing scale from config"""
    
def get_scale(self, config_name, processing_type):
    """Get chunk duration for a config/processing type"""
    
def populate_scales_from_config(self, config_data):
    """Parse config YAML and register all processing scales"""

# Utility Methods
def get_indices_for_span(self, file_id, start_time_sec, end_time_sec):
    """Get acoustic indices that intersect with a time span"""
    
def search_files_by_path_pattern(self, pattern):
    """Find files matching a pattern"""
    
def calculate_chunks(self, start_sec, end_sec, config_name, processing_type):
    """Calculate chunk indices for a time span"""
```

## Phase 2: Create researcher.py CLI Tool

### Command Structure
Using Click for argument parsing and Rich for beautiful output:

```bash
# Research Goals with Rich tables
python researcher.py --config config_mac.yaml goals list
python researcher.py --config config_mac.yaml goals create --title "Litoria aurea calls" --description "Bell frog detection"
python researcher.py --config config_mac.yaml goals show 1
python researcher.py --config config_mac.yaml goals update 1 --title "Updated title"
python researcher.py --config config_mac.yaml goals delete 1 --force

# Points of Interest with progress bars
python researcher.py --config config_mac.yaml poi list --goal-id 1
python researcher.py --config config_mac.yaml poi create --goal-id 1 --label "Strong call" --file-path "/path/to/file.WAV" --start 120 --end 135
python researcher.py --config config_mac.yaml poi show 1
python researcher.py --config config_mac.yaml poi update 1 --confidence 0.8 --notes "Clean recording"
python researcher.py --config config_mac.yaml poi delete 1 --force

# Spans Management
python researcher.py --config config_mac.yaml poi add-span 1 --file-path "/path/to/other.WAV" --start 200 --end 220
python researcher.py --config config_mac.yaml poi list-spans 1

# Search and Discovery
python researcher.py --config config_mac.yaml poi search --date-from 2025-06-20 --confidence-min 0.7
python researcher.py --config config_mac.yaml poi export --goal-id 1 --format audacity

# Database Operations
python researcher.py --config config_mac.yaml scales populate
python researcher.py --config config_mac.yaml stats
```

### Core Features

#### Dry Run Support
```bash
python researcher.py --config config_mac.yaml --dry-run poi create --goal-id 1 --label "Test" --file-path "/path/file.WAV" --start 100 --end 120
# Rich output: [yellow]Would create POI "Test" for goal 1, span 100-120s in file "/path/file.WAV"[/yellow]
```

#### File Path Resolution
- Accept file patterns: `--file-pattern "**/20250620*.WAV"`
- Auto-resolve relative paths against config `input_directory`
- Validate files exist in database before creating POIs

#### Rich UI Features
- **Progress bars** for batch operations
- **Tables** for listing goals and POIs
- **Tree views** for showing POI hierarchies
- **Colored output** for status messages
- **Interactive prompts** for confirmations

#### Configuration Integration
- Parse YAML config for chunk durations
- Auto-populate processing_scales table
- Use config database_path for operations

### CLI Structure (researcher.py)

```python
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
    ctx.obj['config'] = load_config(config)
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

@cli.group()
@click.pass_context  
def poi(ctx):
    """Manage points of interest"""
    if not ctx.obj['dry_run']:
        ctx.obj['db'] = AudioDatabase(ctx.obj['db_path'])

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
        return
    
    db = ctx.obj['db']
    config = ctx.obj['config']
    
    # Resolve file path
    resolved_files = resolve_file_path(db, file_path, config)
    
    if not resolved_files:
        console.print(f"[red]❌ No files found matching: {file_path}[/red]")
        return
    
    if len(resolved_files) > 1:
        console.print(f"[red]❌ Pattern matches multiple files. Use specific path.[/red]")
        return
    
    file_record = resolved_files[0]
    
    # Create POI
    poi_id = db.create_poi(goal_id, label, notes, confidence, anchor_index)
    
    # Add span with chunk calculation
    chunk_start, chunk_end = db.calculate_chunks(
        start, end, 
        config.get('config_name', 'config_mac.yaml'),
        'spectral'
    )
    
    span_id = db.add_poi_span(
        poi_id, file_record['id'], start, end,
        chunk_start, chunk_end,
        config.get('config_name', 'config_mac.yaml'),
        'spectral'
    )
    
    console.print(f"[green]✓ Created POI {poi_id}: {label}[/green]")
    console.print(f"[green]  Added span {span_id}: {start}-{end}s in {file_record['filename']}[/green]")

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
    
    all_pois = db.get_pois()
    table.add_row("Points of Interest", str(len(all_pois)))
    
    console.print(table)

def load_config(config_path):
    """Load configuration from YAML file"""
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)

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
```

## Phase 3: Integration with Existing Tools

### Config Integration
Modify existing processing scripts to populate processing_scales:

```python
# In acoustic index processing scripts:
def process_with_config(config_path):
    config = load_config(config_path)
    db = AudioDatabase(config['database_path'])
    
    # Register processing scales from config
    db.populate_scales_from_config(config)
    
    # Continue with existing processing...
```

### Configuration Parsing
Parse chunk durations from YAML structure:

```python
def populate_scales_from_config(self, config_data):
    """Parse acoustic indices config and register scales"""
    acoustic_indices = config_data.get('acoustic_indices', {})
    config_name = Path(config_file).name if hasattr(self, 'config_file') else 'config_mac.yaml'
    
    # Register temporal scale
    temporal_config = acoustic_indices.get('temporal', {})
    if 'chunk_duration_sec' in temporal_config:
        self.register_scale(config_name, 'temporal', temporal_config['chunk_duration_sec'])
    
    # Register spectral scale  
    spectral_config = acoustic_indices.get('spectral', {})
    if 'chunk_duration_sec' in spectral_config:
        self.register_scale(config_name, 'spectral', spectral_config['chunk_duration_sec'])
```

## Key Design Principles

### 1. Consistency with Existing Tools
- Same argument patterns (`--config`, `--dry-run`, `--force`)
- Rich output formatting with progress bars and tables
- Reuse existing database connection patterns from `audio_database.py`

### 2. Rich UI Experience
- **Beautiful tables** for listing goals and POIs
- **Progress bars** for batch operations  
- **Colored output** for status and errors
- **Interactive confirmations** for destructive operations

### 3. Config-Driven Operation
- All timing values from YAML config (no hardcoded 4.5s)
- Database path from config
- Processing scales auto-populated from acoustic_indices config

### 4. File System Integration
- Work with existing file paths and patterns
- Validate files exist in database before creating POIs
- Support relative paths resolved against config input_directory

### 5. Research Workflow Support
- List/search operations for discovering existing POIs
- Export capabilities (Audacity labels, CSV)
- Statistics and reporting with Rich formatting

## Export Capabilities

### Audacity Labels Export
```python
def export_poi_audacity_labels(self, poi_id, output_path):
    """Export POI spans as Audacity label file"""
    poi = self.get_poi(poi_id)
    spans = self.get_poi_spans(poi_id)
    
    with open(output_path, 'w') as f:
        for span in spans:
            f.write(f"{span['start_time_sec']}\t{span['end_time_sec']}\t{poi['label']}\n")
```

### CSV Export  
```python
def export_pois_csv(self, goal_id, output_path):
    """Export POIs and spans to CSV for analysis"""
    # Implementation with pandas-like output
```

## Migration Strategy

### Database Schema Migration
The `init_database()` method in `AudioDatabase` uses `CREATE TABLE IF NOT EXISTS`, making it safe to run against existing databases. New POI tables will be created without affecting existing data.

### Backward Compatibility
- Existing `audio_files` and `acoustic_indices_core` tables get new `config_name` columns
- All existing data remains functional
- POI features are additive, not replacing existing functionality

## Success Criteria
- [ ] Researchers can manage goals and POIs via beautiful CLI interface
- [ ] Integration with existing config and database patterns  
- [ ] No dependency on webapp backend
- [ ] Dry-run mode for all operations with Rich styling
- [ ] File path resolution works with existing directory structures
- [ ] Processing scales auto-populated from YAML configs
- [ ] Export capabilities for external tools (Audacity, CSV)
- [ ] Rich UI with progress bars, tables, and colored output

## Future Integration
- Webapp becomes read-only viewer consuming same database
- Deep linking routes (`/#/poi/:pid`) read from CLI-created data
- Visualization tools work with POI data created via researcher.py
- Automated processing can reference POI annotations

## Example Usage Session

```bash
# Initialize and populate processing scales
python researcher.py --config config_mac.yaml scales populate

# Create a research goal
python researcher.py --config config_mac.yaml goals create --title "Litoria aurea detection" --description "Bell frog calls in wetland recordings"

# List goals (shows Rich table)
python researcher.py --config config_mac.yaml goals list

# Create POI with dry-run first
python researcher.py --config config_mac.yaml --dry-run poi create --goal-id 1 --label "Strong call sequence" --file-path "20250620_120000.WAV" --start 450 --end 465

# Actually create the POI  
python researcher.py --config config_mac.yaml poi create --goal-id 1 --label "Strong call sequence" --file-path "20250620_120000.WAV" --start 450 --end 465 --confidence 0.9 --notes "Clear bells, minimal background"

# Search POIs (Rich table output)
python researcher.py --config config_mac.yaml poi search --confidence-min 0.8

# Export for Audacity
python researcher.py --config config_mac.yaml poi export --goal-id 1 --format audacity --output labels.txt
```