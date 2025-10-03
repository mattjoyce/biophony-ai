-- Migration Script: Rename Views with v_ prefix
-- Run this after adding the UNIQUE constraint to acoustic_indices_core

-- Drop existing views (they will be recreated with new names)
DROP VIEW IF EXISTS acoustic_indices;
DROP VIEW IF EXISTS indices_by_file;  
DROP VIEW IF EXISTS index_statistics;
DROP VIEW IF EXISTS bioacoustic_temporal;

-- Create v_acoustic_indices (enriched view for analysis/reporting)
CREATE VIEW v_acoustic_indices AS
SELECT 
    ai.id,
    ai.file_id,
    af.filepath as wav_filepath,
    af.npz_filepath,
    af.recording_datetime,
    af.time_since_last,
    af.time_to_next,
    ai.index_name,
    ai.chunk_index,
    ai.start_time_sec,
    ai.value,
    ai.processing_type,
    ai.computed_at,
    wd.temperature_2m,
    wd.relative_humidity_2m,
    wd.sunrise_time,
    wd.sunset_time
FROM acoustic_indices_core ai
JOIN audio_files af ON ai.file_id = af.id
LEFT JOIN weather_data wd ON af.weather_id = wd.id;

-- Create v_indices_by_file (file-centric view)
CREATE VIEW v_indices_by_file AS
SELECT 
    af.filename,
    af.filepath as wav_filepath,
    af.npz_filepath,
    af.recording_datetime,
    af.time_since_last,
    af.time_to_next,
    ai.index_name,
    ai.chunk_index,
    ai.start_time_sec,
    ai.value,
    ai.processing_type,
    ai.computed_at,
    wd.temperature_2m,
    wd.relative_humidity_2m,
    wd.sunrise_time,
    wd.sunset_time
FROM acoustic_indices_core ai
JOIN audio_files af ON ai.file_id = af.id
LEFT JOIN weather_data wd ON af.weather_id = wd.id
ORDER BY af.filepath, ai.index_name, ai.chunk_index;

-- Create v_index_statistics (stats view)
CREATE VIEW v_index_statistics AS
SELECT 
    ai.processing_type,
    ai.index_name,
    COUNT(*) as measurement_count,
    COUNT(DISTINCT ai.file_id) as file_count,
    MIN(ai.value) as min_value,
    MAX(ai.value) as max_value,
    AVG(ai.value) as avg_value,
    MIN(ai.computed_at) as first_computed,
    MAX(ai.computed_at) as last_computed
FROM acoustic_indices_core ai
GROUP BY ai.processing_type, ai.index_name;

-- Create v_bioacoustic_temporal (temporal analysis view)
CREATE VIEW v_bioacoustic_temporal AS
SELECT 
    af.id,
    af.filename,
    af.filepath,
    af.recording_datetime,
    af.time_since_last,
    af.time_to_next,
    af.audiomoth_id,
    wd.sunrise_time,
    wd.sunset_time,
    wd.temperature_2m,
    wd.relative_humidity_2m,
    wd.precipitation,
    wd.wind_speed_10m,
    ws.name as site_name,
    ws.latitude,
    ws.longitude,
    CASE 
        WHEN af.time_since_last LIKE 'SR+%' AND CAST(SUBSTR(af.time_since_last, 4, 2) AS INTEGER) <= 2 THEN 'Dawn'
        WHEN af.time_since_last LIKE 'SS+%' AND CAST(SUBSTR(af.time_since_last, 4, 2) AS INTEGER) <= 2 THEN 'Dusk'
        WHEN af.time_since_last LIKE 'SR+%' AND CAST(SUBSTR(af.time_since_last, 4, 2) AS INTEGER) BETWEEN 3 AND 12 THEN 'Day'
        WHEN af.time_since_last LIKE 'SS+%' AND CAST(SUBSTR(af.time_since_last, 4, 2) AS INTEGER) BETWEEN 3 AND 12 THEN 'Evening'
        ELSE 'Night'
    END as bioacoustic_period
FROM audio_files af
LEFT JOIN weather_data wd ON af.weather_id = wd.id
LEFT JOIN weather_sites ws ON af.site_id = ws.id
WHERE af.time_since_last IS NOT NULL
ORDER BY af.recording_datetime;