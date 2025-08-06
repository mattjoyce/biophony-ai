# Database Developer Guide

## Overview

This guide covers the database schema and usage patterns for the bioacoustic analysis system. The database uses SQLite with a normalized schema designed for efficient storage and retrieval of AudioMoth recordings, acoustic indices, and associated metadata.

## Schema Overview

The database consists of 7 core tables and 3 views optimized for different query patterns:

### Core Tables

#### `audio_files`
Primary table storing AudioMoth recording metadata and file references.

**Key Fields:**
- `id`: Primary key (auto-increment)
- `filepath`: Unique path to WAV file
- `npz_filepath`: Path to corresponding spectrogram data
- `recording_datetime`: Timestamp of recording start
- `audiomoth_id`: Device identifier
- `duration_seconds`, `samplerate_hz`: Audio properties
- `spectrogram_min/max`, `aci_min/max/mean`: Cached analysis results
- `weather_id`, `site_id`: Foreign keys to weather data

**Indexes:**
- `idx_recording_datetime`: Time-based queries
- `idx_audiomoth_id`: Device-based filtering
- `idx_filepath`: File lookups

#### `acoustic_indices_core`
Central table for all acoustic index measurements.

**Key Fields:**
- `file_id`: References `audio_files(id)`
- `index_name`: Type of acoustic index (ACI, BAI, NDSI, etc.)
- `chunk_index`: Sequential chunk number within file
- `start_time_sec`: Temporal position within recording
- `value`: Computed index value
- `processing_type`: TEMPORAL or SPECTRAL processing method

**Indexes:**
- `idx_core_file_id`: File-based queries
- `idx_core_file_index`: File + index type queries
- `idx_core_type`: Processing type filtering
- `idx_core_name`: Index name filtering

#### `annotations`
User-generated labels and annotations for specific time ranges.

**Key Fields:**
- `audio_file_id`: References `audio_files(id)`
- `start_time`, `end_time`: Time range in seconds
- `label`: Human-readable annotation
- `annotation_type`: Category of annotation

#### `weather_sites` & `weather_data`
Weather information linked to recording locations.

**Key Fields:**
- `weather_sites`: Location coordinates and timezone
- `weather_data`: Hourly weather measurements per site

#### `index_configurations`
Tracks processing configurations for reproducibility.

**Key Fields:**
- `config_name`: Configuration file identifier
- `index_name`: Specific index within config
- `config_hash`: Hash of configuration parameters

#### `global_stats`
System-wide statistics for normalization and visualization.

**Key Fields:**
- `stat_name`: Statistic identifier (e.g., "global_spectrogram_min")
- `stat_value`: Computed value

### Views

#### `acoustic_indices`
Denormalized view joining indices with file paths.
```sql
SELECT ai.*, af.filepath as wav_filepath, af.npz_filepath
FROM acoustic_indices_core ai
JOIN audio_files af ON ai.file_id = af.id
```

#### `indices_by_file`
File-centric view ordered by filepath and chunk sequence.
```sql
SELECT af.filename, ai.index_name, ai.chunk_index, ai.value, ...
FROM acoustic_indices_core ai
JOIN audio_files af ON ai.file_id = af.id
ORDER BY af.filepath, ai.index_name, ai.chunk_index
```

#### `index_statistics`
Aggregate statistics per index type.
```sql
SELECT processing_type, index_name, 
       COUNT(*) as measurement_count,
       MIN/MAX/AVG(value) as statistics
FROM acoustic_indices_core ai
GROUP BY processing_type, index_name
```

## DatabaseManager API

The `indices/database_manager.py` module provides a high-level interface for database operations:

### Core Storage Methods

#### `store_indices(filepath, processing_type, indices_data, chunk_timestamps, npz_filepath=None)`
Primary method for storing acoustic indices data.
- **filepath**: Source file path (WAV for temporal, NPZ for spectral)
- **processing_type**: "temporal" or "spectral"  
- **indices_data**: Dict mapping index_name → values array
- **chunk_timestamps**: Array of start times for each chunk
- **npz_filepath**: Optional NPZ file path for temporal processing

```python
db = DatabaseManager("audiomoth.db")
db.store_indices(
    filepath="/data/20240706_120000.WAV",
    processing_type="temporal", 
    indices_data={"activity": activity_values, "entropy": entropy_values},
    chunk_timestamps=np.array([0, 30, 60, 90])  # 30-sec chunks
)
```

#### `get_indices_for_file(filepath, processing_type=None, index_names=None)`
Retrieve stored indices for a single file with optional filtering.
- Returns: `Dict[str, np.ndarray]` mapping index_name → values array

```python
# Get all temporal indices for a file
temporal_data = db.get_indices_for_file("/data/file.WAV", processing_type="temporal")

# Get specific indices only
aci_data = db.get_indices_for_file("/data/file.WAV", index_names=["ACI", "BAI"])
```

#### `get_indices_for_files_bulk(file_paths, processing_type, index_names=None)`
Efficient bulk retrieval for multiple files (shard-friendly).
- Returns: `Dict[str, Dict[str, np.ndarray]]` mapping filepath → {index_name → values}

```python
# Process a shard of files efficiently
shard_files = [f"/data/shard_{i}.WAV" for i in range(100)]
bulk_data = db.get_indices_for_files_bulk(shard_files, "spectral", ["ACI", "NDSI"])
```

### Query and Management Methods

#### `get_files_with_indices(processing_type=None)`
List all files that have stored indices.
```python
temporal_files = db.get_files_with_indices("temporal")
all_files = db.get_files_with_indices()
```

#### `get_index_statistics()`
Get comprehensive statistics about stored indices.
```python
stats = db.get_index_statistics()
# Returns: {'by_type_and_index': [...], 'total_files': 1500, 'total_values': 45000}
```

#### `clear_indices(filepath=None, processing_type=None)`
Clear indices with optional filtering (useful for reprocessing).
```python
# Clear all indices for a file
db.clear_indices("/data/problematic_file.WAV")

# Clear all spectral indices
db.clear_indices(processing_type="spectral")

# Clear everything (dangerous!)
db.clear_indices()
```

### Configuration Management

#### `store_index_configuration(config_name, config_data)`
Store acoustic index configurations for reproducibility.
```python
with open('config.yaml') as f:
    config_data = yaml.safe_load(f)
db.store_index_configuration("config_multi_species_frogs.yaml", config_data)
```

#### `get_index_configuration(index_name, config_name=None)`
Retrieve configuration for a specific index.
```python
config = db.get_index_configuration("eastern_froglet_bai_2500-3500")
# Returns processor, parameters, and metadata
```

#### `get_all_configurations(config_name=None)`
List all stored configurations with optional filtering.

### Weather Integration

#### `get_weather_for_filename(filename)`
Get weather data linked to AudioMoth recordings.
```python
weather = db.get_weather_for_filename("20250706_013000.WAV")
# Returns temperature, humidity, wind, precipitation data
```

## Usage Patterns

### File Processing Workflow

1. **Ingestion** (`scan_audio_database.py`)
   ```sql
   INSERT INTO audio_files (filepath, filename, recording_datetime, ...)
   VALUES (?, ?, ?, ...)
   ```

2. **Spectrogram Generation** (`generate_spectrograms_gpu_optimized.py`)
   ```sql
   UPDATE audio_files 
   SET npz_filepath = ?, spectrogram_min = ?, spectrogram_max = ?
   WHERE id = ?
   ```

3. **Index Processing** (`process_acoustic_indices.py`)
   ```python
   db.store_indices(wav_path, "temporal", temporal_indices, timestamps)
   db.store_indices(npz_path, "spectral", spectral_indices, timestamps)
   ```

### Common Query Patterns

#### Time Range Queries
```sql
SELECT * FROM acoustic_indices 
WHERE wav_filepath LIKE '%/2024-06-%'
AND index_name = 'ACI'
ORDER BY start_time_sec
```

#### Device Analysis
```sql
SELECT af.audiomoth_id, ai.index_name, AVG(ai.value)
FROM acoustic_indices_core ai
JOIN audio_files af ON ai.file_id = af.id
GROUP BY af.audiomoth_id, ai.index_name
```

#### Processing Status
```sql
SELECT af.filepath, 
       COUNT(DISTINCT ai.index_name) as indices_computed
FROM audio_files af
LEFT JOIN acoustic_indices_core ai ON af.id = ai.file_id
GROUP BY af.id
HAVING indices_computed < 5  -- Expected number of indices
```

### Bulk Operations with DatabaseManager

#### Shard Processing Pattern
```python
db = DatabaseManager("audiomoth.db")

# Get list of files to process for this shard
shard_files = [f for i, f in enumerate(all_files) if i % 10 == shard_id]

# Check which files already have indices
existing_files = db.get_files_with_indices("spectral")
files_to_process = [f for f in shard_files if f not in existing_files]

# Process files and store indices
for filepath in files_to_process:
    indices = compute_spectral_indices(filepath)
    timestamps = compute_timestamps(filepath)
    db.store_indices(filepath, "spectral", indices, timestamps)
```

#### Statistics and Monitoring
```python
# Monitor processing progress
stats = db.get_index_statistics()
for processing_type, index_name, count, files in stats['by_type_and_index']:
    print(f"{processing_type} {index_name}: {count} values across {files} files")

# Check for incomplete processing
all_files = db.get_files_with_indices()
temporal_files = db.get_files_with_indices("temporal")
spectral_files = db.get_files_with_indices("spectral")

missing_temporal = set(all_files) - set(temporal_files)
missing_spectral = set(all_files) - set(spectral_files)
```

## Performance Considerations

### Database Settings
DatabaseManager automatically configures optimal SQLite settings:
- WAL mode for concurrent access during sharded processing
- 30-second busy timeout for locked database handling
- Bulk insert operations using `executemany()`

### Index Strategy
- **Primary indexes**: Optimized for file-based queries
- **Composite indexes**: Support multi-column filters  
- **Time-based indexes**: Enable efficient temporal queries

### Memory Management
- Connection pooling for multi-threaded access
- Regular VACUUM for storage optimization
- Statistics updates for query planner

## Data Integrity

### Constraints
- Foreign key relationships enforced
- Unique constraints on file paths and coordinates
- NOT NULL constraints on critical fields

### Validation Patterns
```python
# DatabaseManager automatically handles validation
try:
    db.store_indices(filepath, "temporal", indices_data, timestamps)
except ValueError as e:
    print(f"Data validation failed: {e}")
```

## Migration and Maintenance

### Schema Updates
- DatabaseManager handles schema migration automatically
- Detects old schema and provides migration guidance
- Backup recommendations before major changes

### Monitoring Queries
```python
# Use DatabaseManager for monitoring
stats = db.get_index_statistics()
print(f"Total files: {stats['total_files']}")
print(f"Total measurements: {stats['total_values']}")

# Check for processing gaps
all_configs = db.get_all_configurations()
for config in all_configs:
    print(f"Config: {config['config_name']} - {config['index_name']}")
```

### Backup Strategy
```bash
# Regular backup with compression
sqlite3 audiomoth.db ".backup audiomoth_backup_$(date +%Y%m%d_%H%M%S).db"
gzip audiomoth_backup_*.db
```

## Integration Points

### Python Applications
- `audio_database.py`: Core database operations
- `indices/database_manager.py`: High-level bulk operations
- `web_app.py`: Read-only web interface queries

### File System Integration
- WAV files referenced by absolute paths
- NPZ spectrograms co-located with source files
- PNG visualizations generated on-demand

### Processing Coordination
- File locking prevents concurrent processing
- Sharding system enables parallel operations
- Configuration tracking ensures reproducibility