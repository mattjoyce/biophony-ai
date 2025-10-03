# AudioMoth Spectrogram Viewer - Setup Guide

## Prerequisites

- Python 3.11+ with venv
- NVIDIA GPU (for spectrogram generation)
- AudioMoth recordings in WAV format

## Complete Setup Workflow

### 1. Scan Audio Files

First, scan your AudioMoth recordings into the database:

```bash
source venv/bin/activate
python3 scan_audio_database.py --config <your-config.yaml>
```

This creates the database and populates the `audio_files` table.

### 2. Process Acoustic Indices

Process acoustic indices to populate the database with analysis data:

```bash
python3 process_acoustic_indices.py <your-config.yaml>
```

This will:
- Create `acoustic_indices_core` table
- Create `index_configurations` table
- Create `v_acoustic_indices` view (required for webapp)
- Process temporal and spectral indices

### 3. Generate Spectrogram Data (NPZ files)

Generate mel-spectrogram data files:

```bash
python3 generate_spectrograms_gpu_optimized.py --config <your-config.yaml> --target 0
```

**Note:** Use `--target 0` to process all files. For parallel processing on multi-GPU systems, use multiple targets (0, 1, 2, etc.)

### 4. Generate PNG Images

Generate PNG spectrogram images from NPZ data:

```bash
python3 generate_png_ultra_fast.py --config <your-config.yaml> --target 0
```

This creates `*_spec.png` files in the same directory as your WAV files.

### 5. (Optional) Add Weather Data

Weather data integration uses the free Open-Meteo API (no API key needed):

```bash
# Create weather config section in your config.yaml:
# weather:
#   enabled: true
#   sites:
#     - name: "Macquarie University"
#       latitude: -33.7747
#       longitude: 151.1135
#   date_range:
#     start_date: "2025-09-15"
#     end_date: "2025-10-03"

python3 weather_integration.py --config <your-config.yaml>
```

### 6. Start the Webapp

```bash
cd webapp/v2/backend
python3 app.py --config <your-config.yaml> --port 8001
```

Open browser to: http://127.0.0.1:8001

## Required Database Schema

The webapp requires these database components:

### Tables
- `audio_files` - Created by scan_audio_database.py
- `acoustic_indices_core` - Created by process_acoustic_indices.py
- `index_configurations` - Created by process_acoustic_indices.py
- `weather_data` (optional) - Created by weather_integration.py
- `weather_sites` (optional) - Created by weather_integration.py

### Views
- `v_acoustic_indices` - **AUTO-CREATED** by DatabaseManager in process_acoustic_indices.py

## Configuration Example

Create a config file (e.g., `config_project.yaml`):

```yaml
input_directory: "/path/to/your/audio/files"
database_path: "/path/to/your/audiomoth.db"

# Audio parameters
sample_rate: 48000
file_duration_sec: 600  # 10-minute files (or 900 for 15-minute)

# Spectrogram parameters
n_fft: 2048
hop_length: 256
n_mels: 128
width-px: 1000
height-px: 300
global_min: -40
global_max: 40

# Acoustic indices
acoustic_indices:
  temporal:
    chunk_duration_sec: 4.5
    temporal_entropy:
      processor: temporal_entropy
      params: {}
    temporal_activity:
      processor: temporal_activity
      params: {}

  spectral:
    chunk_duration_sec: 4.5
    acoustic_complexity_index:
      processor: acoustic_complexity_index
      params: {}
    lowfreq_frogs_200-800:
      processor: bioacoustics_index
      params:
        freq_min: 200
        freq_max: 800
```

## Troubleshooting

### "Failed to load available indices: HTTP 500"
- The `v_acoustic_indices` view is missing
- Run: `python3 process_acoustic_indices.py <config>` to auto-create it
- Or manually create it (see DATABASE_DEVELOPER_GUIDE.md)

### "Failed to load spectrogram: HTTP 404"
- PNG files haven't been generated
- Run steps 3 and 4 above to generate NPZ and PNG files

### "File duration outside tolerance"
- Your config `file_duration_sec` doesn't match actual file durations
- Check actual durations: `SELECT DISTINCT duration_seconds, COUNT(*) FROM audio_files GROUP BY duration_seconds`
- Update config to match most common duration
- **Note:** Files outside tolerance are automatically marked as `processing_status = 'skipped'` and shown as hollow circles on the timeline

### Weather data is NULL
- Weather integration is optional
- Run `weather_integration.py` with proper config to populate

## Processing Status Flags

Files can have a `processing_status` field to indicate their processing state:

- `NULL` - Normal file, fully processed
- `'skipped'` - File skipped during processing (e.g., duration out of tolerance)
- `'partial'` - File partially processed (future use)
- `'error'` - File encountered errors during processing (future use)

**Visual indicators on timeline:**
- **Filled blue circle** - Normal processed file
- **Hollow gray circle** - Skipped file (no spectrogram/indices)
- **Red circle** - Currently selected file

## File Locations

The webapp expects these file patterns:

```
/path/to/audio/
  ├── 20250915/
  │   ├── AudioMoth_20250915_094030.WAV          # Original audio
  │   ├── AudioMoth_20250915_094030_spec.npz     # Spectrogram data
  │   └── AudioMoth_20250915_094030_spec.png     # Spectrogram PNG
  └── audiomoth.db                                # SQLite database
```

## New Repository Clone Setup

For someone cloning this repository fresh:

1. Create virtual environment and install dependencies
2. Create a config file for your data
3. Follow steps 1-6 above in order
4. All database schema (tables, views, indices) will be created automatically

**No manual database setup required** - everything is created automatically by the processing scripts.

## Database Schema

The canonical database schema is defined in **`schema.sql`**. This file is the authoritative source of truth for the database structure.

### Creating a New Database

```bash
# Method 1: Let scan_audio_database.py create it automatically
python3 scan_audio_database.py --config <your-config.yaml>

# Method 2: Create from canonical schema
sqlite3 /path/to/audiomoth.db < schema.sql
```

### Verifying Existing Database

```bash
# Check schema version
sqlite3 /path/to/audiomoth.db "SELECT * FROM schema_version"

# Compare schema with canonical
sqlite3 /path/to/audiomoth.db .schema > current_schema.sql
diff schema.sql current_schema.sql
```

### Schema Migrations

If you have an existing database that pre-dates the `processing_status` column:

```bash
sqlite3 /path/to/audiomoth.db "ALTER TABLE audio_files ADD COLUMN processing_status TEXT DEFAULT NULL"
```

**Important:** Always update `schema.sql` when making schema changes. Never rely on emergent schema from scattered ALTER TABLE statements.
