# Database Schema Migrations

This document tracks all schema changes and provides migration paths for existing databases.

## Version 3.0 (2025-10-04)

**Added:**
- `weather_sites` table - Recording site weather metadata
- `weather_data` table - Hourly weather observations with sunrise/sunset
- `audio_files.weather_id` column - Links to weather_data
- `audio_files.site_id` column - Links to weather_sites
- `audio_files.time_since_last` column - Sunrise/sunset temporal labels (e.g., "SR+02:30")
- `audio_files.time_to_next` column - Temporal labels to next event (e.g., "SS−01:15")

**Migration from 2.0:**

```sql
-- Create weather tables
CREATE TABLE IF NOT EXISTS weather_sites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    elevation REAL,
    timezone TEXT,
    timezone_abbreviation TEXT,
    UNIQUE(latitude, longitude)
);

CREATE TABLE IF NOT EXISTS weather_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER REFERENCES weather_sites(id),
    datetime TEXT NOT NULL,
    temperature_2m REAL,
    relative_humidity_2m REAL,
    precipitation REAL,
    wind_speed_10m REAL,
    weather_code INTEGER,
    cloud_cover REAL,
    pressure_msl REAL,
    sunrise_time TEXT,
    sunset_time TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(site_id, datetime)
);

-- Add weather columns to audio_files
ALTER TABLE audio_files ADD COLUMN weather_id INTEGER REFERENCES weather_data(id);
ALTER TABLE audio_files ADD COLUMN site_id INTEGER REFERENCES weather_sites(id);
ALTER TABLE audio_files ADD COLUMN time_since_last TEXT;
ALTER TABLE audio_files ADD COLUMN time_to_next TEXT;

-- Update schema version
INSERT INTO schema_version (version, description)
VALUES ('3.0', 'Added weather integration with sunrise/sunset temporal labels');
```

**Setup Weather Integration:**

1. Add weather configuration to your config YAML (see `config_macquarie.yaml` for example):
```yaml
weather:
  enabled: true
  sites:
    - name: "Your Site Name"
      latitude: -33.7747
      longitude: 151.1122
  date_range:
    start_date: "2025-09-15"
    end_date: "2025-10-03"
```

2. Run weather integration:
```bash
python3 weather_integration.py --config config_macquarie.yaml
```

This will:
- Create weather tables
- Fetch historical weather from Open-Meteo API (free)
- Link audio files to weather records
- Calculate sunrise/sunset temporal labels

**Data Sources:**
- Weather: [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api) (free, no API key required)
- Sunrise/sunset automatically included in weather data

---

## Version 2.0 (2025-10-03)

**Added:**
- `audio_files.processing_status` column (TEXT, DEFAULT NULL)
- `schema_version` table for version tracking
- Index on `audio_files.processing_status`

**Migration from pre-2.0:**

```sql
-- Add processing_status column
ALTER TABLE audio_files ADD COLUMN processing_status TEXT DEFAULT NULL;

-- Add index for performance
CREATE INDEX IF NOT EXISTS idx_processing_status ON audio_files(processing_status);

-- Create schema_version table
CREATE TABLE IF NOT EXISTS schema_version (
    version TEXT PRIMARY KEY,
    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

-- Record migration
INSERT INTO schema_version (version, description)
VALUES ('2.0', 'Added processing_status tracking');
```

**Changes:**
- `v_acoustic_indices` view now automatically created by `DatabaseManager.setup_database()`
- Processing scripts now mark skipped files with `processing_status = 'skipped'`

**Backwards Compatibility:**
- Existing code will work with NULL `processing_status` (treated as normal files)
- Webapp gracefully handles missing `processing_status` field

---

## Version 1.0 (Initial)

**Tables:**
- `audio_files` - Core audio file metadata
- `annotations` - Manual annotations/labels
- `research_goals` - Research objectives
- `points_of_interest` - POI definitions
- `poi_spans` - POI time spans
- `processing_scales` - Processing configuration tracking
- `acoustic_indices_core` - Indices storage
- `index_configurations` - Index configuration tracking
- `weather_sites` (optional) - Weather location data
- `weather_data` (optional) - Weather measurements

**Views:**
- `v_acoustic_indices` - Join of indices with file metadata

---

## Migration Best Practices

1. **Always backup before migrating:**
   ```bash
   cp audiomoth.db audiomoth.db.backup-$(date +%Y%m%d)
   ```

2. **Test migrations on a copy first:**
   ```bash
   cp audiomoth.db test_migration.db
   sqlite3 test_migration.db < migration.sql
   ```

3. **Verify migration success:**
   ```bash
   sqlite3 audiomoth.db "SELECT * FROM schema_version ORDER BY applied_at DESC"
   ```

4. **Update schema.sql** after making any schema changes

5. **Document all changes** in this file with:
   - Date
   - Description
   - Migration SQL
   - Affected components

---

## Future Migrations

When adding new schema changes:

1. Update `schema.sql` with the new canonical schema
2. Add migration SQL to this file
3. Update `schema_version` table insert
4. Update documentation (WEBAPP_SETUP.md, DATABASE_DEVELOPER_GUIDE.md)
5. Test on a fresh database AND a migrated database
