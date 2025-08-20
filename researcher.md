# Researcher CLI Tool

A command-line tool for managing research goals and Points of Interest (POIs) in bioacoustic analysis. This tool integrates with your existing AudioMoth database and configuration files to help you mark, annotate, and organize acoustic events of interest.

## Installation

The tool is ready to use with your existing Python environment:

```bash
# Ensure you have the required dependencies
source venv/bin/activate
python researcher.py --help
```

## Quick Start

### 1. Initialize Processing Scales
First, populate the processing scales from your configuration:

```bash
python researcher.py --config config_mac.yaml scales populate
```

### 2. Create a Research Goal
Organize your work with research objectives:

```bash
python researcher.py --config config_mac.yaml goals create \
    --title "Litoria aurea detection" \
    --description "Bell frog calls in wetland recordings"
```

### 3. Mark Points of Interest
Create POIs linked to specific time ranges in audio files:

```bash
python researcher.py --config config_mac.yaml poi create \
    --goal-id 1 \
    --label "Strong call sequence" \
    --file-path "/path/to/your/recording.WAV" \
    --start 450 \
    --end 465 \
    --confidence 0.9 \
    --notes "Clear bells, minimal background noise"
```

### 4. Review Your Work
List and explore your POIs:

```bash
# List all POIs
python researcher.py --config config_mac.yaml poi list

# Show detailed POI information
python researcher.py --config config_mac.yaml poi show 1

# Search POIs by confidence
python researcher.py --config config_mac.yaml poi search --confidence-min 0.8
```

## Command Reference

### Global Options

- `--config, -c`: YAML configuration file (required)
- `--dry-run`: Show what would be done without executing
- `--help`: Show help message

### Research Goals (`goals`)

Organize your research with goals that group related POIs.

#### `goals list`
Display all research goals in a formatted table.

```bash
python researcher.py --config config_mac.yaml goals list
```

#### `goals create`
Create a new research goal.

```bash
python researcher.py --config config_mac.yaml goals create \
    --title "Species detection study" \
    --description "Identifying calls from target species"
```

**Options:**
- `--title`: Goal title (required)
- `--description`: Detailed description (optional)

#### `goals show <goal_id>`
Display detailed information about a specific goal and its associated POIs.

```bash
python researcher.py --config config_mac.yaml goals show 1
```

#### `goals update <goal_id>`
Update an existing research goal.

```bash
python researcher.py --config config_mac.yaml goals update 1 \
    --title "Updated title" \
    --description "New description"
```

**Options:**
- `--title`: New title
- `--description`: New description

#### `goals delete <goal_id>`
Delete a research goal and all associated POIs.

```bash
python researcher.py --config config_mac.yaml goals delete 1 --force
```

**Options:**
- `--force`: Skip confirmation prompt

### Points of Interest (`poi`)

Mark and manage specific time ranges of interest in your audio recordings.

#### `poi list`
Display POIs in a formatted table.

```bash
# List all POIs
python researcher.py --config config_mac.yaml poi list

# Filter by research goal
python researcher.py --config config_mac.yaml poi list --goal-id 1

# Limit results
python researcher.py --config config_mac.yaml poi list --limit 10
```

**Options:**
- `--goal-id`: Filter by research goal ID
- `--limit`: Maximum number of results (default: 50)

#### `poi create`
Create a new point of interest with a time span.

```bash
python researcher.py --config config_mac.yaml poi create \
    --goal-id 1 \
    --label "Dawn chorus peak" \
    --file-path "/full/path/to/recording.WAV" \
    --start 300 \
    --end 360 \
    --confidence 0.8 \
    --notes "High activity period" \
    --anchor-index "standard_bai_500-2000"
```

**Options:**
- `--goal-id`: Research goal ID (required)
- `--label`: Descriptive label (required)
- `--file-path`: Full path to audio file (required)
- `--start`: Start time in seconds (required)
- `--end`: End time in seconds (required)
- `--notes`: Research notes (optional)
- `--confidence`: Confidence level 0-1 (optional)
- `--anchor-index`: Associated acoustic index (optional)

**Note:** The tool automatically calculates chunk indices based on your config's `chunk_duration_sec` settings.

#### `poi show <poi_id>`
Display detailed information about a POI including all its time spans.

```bash
python researcher.py --config config_mac.yaml poi show 1
```

#### `poi search`
Search POIs with various filters.

```bash
# Search by minimum confidence
python researcher.py --config config_mac.yaml poi search --confidence-min 0.7

# Search by date range
python researcher.py --config config_mac.yaml poi search \
    --date-from 2025-06-20 \
    --date-to 2025-07-01

# Combine filters
python researcher.py --config config_mac.yaml poi search \
    --confidence-min 0.8 \
    --limit 25
```

**Options:**
- `--confidence-min`: Minimum confidence level
- `--date-from`: Start date (YYYY-MM-DD)
- `--date-to`: End date (YYYY-MM-DD)
- `--limit`: Maximum results (default: 50)

### Database Statistics (`stats`)

Show overview of your database including POI counts.

```bash
python researcher.py --config config_mac.yaml stats
```

Displays:
- Audio file count
- Research goals count
- Points of interest count
- Total time spans
- Recording date range

### Processing Scales (`scales`)

Manage the processing scale registry used for chunk calculations.

#### `scales populate`
Extract chunk durations from your config file and register them.

```bash
python researcher.py --config config_mac.yaml scales populate
```

This reads your `acoustic_indices` config sections and registers the `chunk_duration_sec` values for temporal and spectral processing.

#### `scales list`
Display registered processing scales.

```bash
python researcher.py --config config_mac.yaml scales list
```

Shows the mapping of (config_name, processing_type) → chunk_duration_sec used for chunk calculations.

## File Path Resolution

The tool supports flexible file path specifications:

### Full Absolute Paths
```bash
--file-path "/Volumes/Extreme SSD/2025-6-20_to_7-31/20250620/recording.WAV"
```

### Relative Paths
Resolved against `input_directory` from your config:
```bash
--file-path "20250620/recording.WAV"
```

### Pattern Matching (Future)
Support for wildcards to match multiple files:
```bash
--file-path "**/20250620*.WAV"
```

## Configuration Integration

The tool uses your existing YAML configuration:

### Required Config Fields
- `database_path`: Path to your AudioMoth SQLite database
- `input_directory`: Base directory for relative file paths (optional)

### Used Config Fields
- `acoustic_indices.temporal.chunk_duration_sec`: For temporal chunk calculations
- `acoustic_indices.spectral.chunk_duration_sec`: For spectral chunk calculations

### Example Config Structure
```yaml
input_directory: "/Volumes/Extreme SSD/2025-6-20_to_7-31"
database_path: "/Volumes/Extreme SSD/2025-6-20_to_7-31/audiomoth.db"

acoustic_indices:
  temporal:
    chunk_duration_sec: 4.5
  spectral:
    chunk_duration_sec: 4.5
```

## Safety Features

### Dry Run Mode
Test commands without making changes:

```bash
python researcher.py --config config_mac.yaml --dry-run poi create \
    --goal-id 1 --label "Test POI" --file-path "recording.WAV" --start 100 --end 120
```

### Confirmation Prompts
Destructive operations require confirmation unless `--force` is used:

```bash
python researcher.py --config config_mac.yaml goals delete 1
# Prompts: Delete goal 'Title' and N associated POIs?
```

### Data Validation
- Time ranges must be valid (start < end)
- End time cannot exceed file duration
- Files must exist in the database
- Confidence values must be between 0 and 1

## Data Model

### Research Goals
- **Purpose**: Organize POIs by research objective
- **Fields**: ID, title, description, created_at
- **Relationships**: One goal → many POIs

### Points of Interest
- **Purpose**: Mark acoustic events of interest
- **Fields**: ID, goal_id, label, notes, confidence, anchor_index_name, created_at
- **Relationships**: One POI → many spans

### POI Spans
- **Purpose**: Define time ranges within audio files
- **Fields**: ID, poi_id, file_id, start_time_sec, end_time_sec, chunk_start, chunk_end, config_name, processing_type, created_at
- **Time Precision**: Integer seconds (appropriate for chunk-based analysis)

### Processing Scales
- **Purpose**: Registry for chunk duration calculations
- **Fields**: ID, config_name, processing_type, chunk_duration_sec, created_at
- **Usage**: Automatic chunk index calculation for POI spans

## Examples

### Typical Research Workflow

1. **Setup**
```bash
# Initialize processing scales
python researcher.py --config config_mac.yaml scales populate

# Create research objectives
python researcher.py --config config_mac.yaml goals create \
    --title "Dawn chorus analysis" \
    --description "Peak activity periods in morning recordings"

python researcher.py --config config_mac.yaml goals create \
    --title "Species identification" \
    --description "Confirmed species calls for training data"
```

2. **Mark Interesting Events**
```bash
# Mark a dawn chorus peak
python researcher.py --config config_mac.yaml poi create \
    --goal-id 1 \
    --label "Peak activity 5:30-6:00" \
    --file-path "/path/to/dawn_recording.WAV" \
    --start 300 \
    --end 480 \
    --confidence 0.9 \
    --notes "High species diversity, clear calls"

# Mark a specific species call
python researcher.py --config config_mac.yaml poi create \
    --goal-id 2 \
    --label "Litoria aurea - confirmed" \
    --file-path "/path/to/evening_recording.WAV" \
    --start 1205 \
    --end 1220 \
    --confidence 0.95 \
    --anchor-index "standard_bai_500-2000" \
    --notes "Clear bell sequence, no background interference"
```

3. **Review and Analysis**
```bash
# List all high-confidence detections
python researcher.py --config config_mac.yaml poi search --confidence-min 0.8

# Show detailed information for specific POI
python researcher.py --config config_mac.yaml poi show 2

# Get overview statistics
python researcher.py --config config_mac.yaml stats
```

### Working with Large Datasets

```bash
# Create goal for systematic review
python researcher.py --config config_mac.yaml goals create \
    --title "June 2025 Survey" \
    --description "Complete review of June recording period"

# Mark POIs during analysis sessions
python researcher.py --config config_mac.yaml poi create \
    --goal-id 3 \
    --label "Unusual call pattern" \
    --file-path "20250621_050000.WAV" \
    --start 450 \
    --end 480 \
    --confidence 0.6 \
    --notes "Requires further investigation - possible new species?"

# Regular progress checking
python researcher.py --config config_mac.yaml poi list --goal-id 3
```

## Integration with Existing Tools

### With scan_audio_database.py
The researcher tool works alongside your existing database scanner:

```bash
# Scan new files
python scan_audio_database.py --config config_mac.yaml --scan

# Mark POIs in new files
python researcher.py --config config_mac.yaml poi create ...
```

### With Acoustic Indices Processing
Processing scales are automatically registered when you run acoustic indices analysis, enabling proper chunk calculations for POIs.

### Future Webapp Integration
The webapp will be able to read and display POIs created via this CLI tool, providing visualization and deep-linking capabilities while keeping the core research workflow in the command line.

## Tips and Best practices

### Naming Conventions
- **Goals**: Use descriptive research objectives ("Species survey 2025", "Dawn chorus analysis")
- **POI Labels**: Include key details ("Litoria aurea - strong call", "Multi-species sequence")
- **Notes**: Record context that will be valuable later ("Weather conditions", "Background noise level", "Analysis confidence")

### File Organization
- Always use absolute paths for consistency
- Ensure files exist in your database before creating POIs
- Use the `--dry-run` flag to test commands before executing

### Confidence Scoring
- 0.9-1.0: Definitive identification, suitable for training data
- 0.7-0.9: High confidence, good for analysis
- 0.5-0.7: Moderate confidence, requires review
- 0.0-0.5: Low confidence, preliminary marking

### Research Workflow
- Create goals before POIs to organize your work
- Use descriptive labels and notes for future reference
- Regularly review POI statistics to track progress
- Consider exporting POIs for detailed analysis in specialized tools

## Troubleshooting

### "No files found matching"
- Verify the file exists in your database: `python researcher.py --config config_mac.yaml stats`
- Use absolute file paths
- Check that the file was scanned by `scan_audio_database.py`

### "Goal not found"
- List available goals: `python researcher.py --config config_mac.yaml goals list`
- Verify goal ID is correct

### "Database path not found"
- Check your config file has the correct `database_path`
- Ensure the database file exists and is accessible

### Time Validation Errors
- Start time must be less than end time
- End time cannot exceed file duration
- Times must be non-negative integers

## Future Enhancements

Planned features for future releases:
- Export POIs to Audacity label files
- Import POIs from external annotation tools
- Multi-file POI spans
- Pattern-based file matching
- POI templates for common research scenarios
- Integration with automated detection workflows