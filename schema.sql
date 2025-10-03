-- AudioMoth Bioacoustic Analysis System - Canonical Database Schema
-- Version: 2.0
-- Last Updated: 2025-10-03
--
-- This is the authoritative schema definition for the system.
-- Use this file to create new databases or verify existing ones.

-- =============================================================================
-- Core Audio Files Table
-- =============================================================================

CREATE TABLE IF NOT EXISTS audio_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    filepath TEXT NOT NULL UNIQUE,

    -- Cross-platform path support
    volume_prefix TEXT,
    relative_path TEXT,
    npz_filepath TEXT,

    -- File metadata
    file_size INTEGER,
    recording_datetime DATETIME,
    timezone TEXT,

    -- AudioMoth device information
    audiomoth_id TEXT,
    firmware_version TEXT,
    deployment_id TEXT,
    external_microphone BOOLEAN,

    -- Audio technical details
    duration_seconds REAL,
    samplerate_hz INTEGER,
    channels INTEGER,
    samples INTEGER,
    gain TEXT,
    battery_voltage REAL,
    low_battery BOOLEAN,
    temperature_c REAL,
    recording_state TEXT,

    -- Analysis metadata
    comment TEXT,
    spectrogram_min REAL,
    spectrogram_max REAL,
    spectrogram_min_abs REAL,
    spectrogram_max_abs REAL,
    spectrogram_min_p2 REAL,
    spectrogram_max_p98 REAL,
    aci_min REAL,
    aci_max REAL,
    aci_mean REAL,

    -- Processing status tracking
    processing_status TEXT DEFAULT NULL,  -- NULL, 'skipped', 'partial', 'error'

    -- External references
    weather_id INTEGER,
    site_id INTEGER,

    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Audio files indexes for performance
CREATE INDEX IF NOT EXISTS idx_recording_datetime ON audio_files(recording_datetime);
CREATE INDEX IF NOT EXISTS idx_audiomoth_id ON audio_files(audiomoth_id);
CREATE INDEX IF NOT EXISTS idx_filepath ON audio_files(filepath);
CREATE INDEX IF NOT EXISTS idx_processing_status ON audio_files(processing_status);

-- =============================================================================
-- Annotations Table (Audacity labels/manual annotations)
-- =============================================================================

CREATE TABLE IF NOT EXISTS annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    audio_file_id INTEGER,
    start_time REAL,
    end_time REAL,
    label TEXT,
    annotation_type TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (audio_file_id) REFERENCES audio_files (id)
);

CREATE INDEX IF NOT EXISTS idx_annotations_file ON annotations(audio_file_id);

-- =============================================================================
-- Research Goals & Points of Interest
-- =============================================================================

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

CREATE INDEX IF NOT EXISTS idx_points_of_interest_goal ON points_of_interest(goal_id);

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

CREATE INDEX IF NOT EXISTS idx_poi_spans_file_time ON poi_spans(file_id, start_time_sec, end_time_sec);
CREATE INDEX IF NOT EXISTS idx_poi_spans_poi ON poi_spans(poi_id);

-- =============================================================================
-- Acoustic Indices Storage
-- =============================================================================

CREATE TABLE IF NOT EXISTS acoustic_indices_core (
    id INTEGER PRIMARY KEY,
    file_id INTEGER NOT NULL REFERENCES audio_files(id),
    index_name TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    start_time_sec REAL NOT NULL,
    value REAL,
    processing_type TEXT NOT NULL,
    computed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(file_id, index_name, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_core_file_id ON acoustic_indices_core(file_id);
CREATE INDEX IF NOT EXISTS idx_core_file_index ON acoustic_indices_core(file_id, index_name);
CREATE INDEX IF NOT EXISTS idx_core_type ON acoustic_indices_core(processing_type);
CREATE INDEX IF NOT EXISTS idx_core_name ON acoustic_indices_core(index_name);

CREATE TABLE IF NOT EXISTS index_configurations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_name TEXT NOT NULL,
    index_name TEXT NOT NULL,
    processor_name TEXT NOT NULL,
    config_fragment TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(config_name, index_name, config_hash)
);

CREATE INDEX IF NOT EXISTS idx_config_index_name ON index_configurations(config_name, index_name);

CREATE TABLE IF NOT EXISTS processing_scales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_name TEXT NOT NULL,
    processing_type TEXT NOT NULL,
    chunk_duration_sec REAL NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(config_name, processing_type)
);

-- =============================================================================
-- Weather Data (Optional)
-- =============================================================================

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

-- =============================================================================
-- Views
-- =============================================================================

-- Primary view for acoustic indices with file metadata
CREATE VIEW IF NOT EXISTS v_acoustic_indices AS
SELECT
    ai.id,
    ai.file_id,
    af.filepath as wav_filepath,
    af.recording_datetime,
    ai.index_name,
    ai.chunk_index,
    ai.start_time_sec,
    ai.value,
    ai.processing_type,
    ai.computed_at
FROM acoustic_indices_core ai
JOIN audio_files af ON ai.file_id = af.id;

-- =============================================================================
-- Schema Version Tracking
-- =============================================================================

CREATE TABLE IF NOT EXISTS schema_version (
    version TEXT PRIMARY KEY,
    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

INSERT OR IGNORE INTO schema_version (version, description)
VALUES ('2.0', 'Canonical schema with processing_status tracking');
