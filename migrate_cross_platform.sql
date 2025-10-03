-- Cross-Platform Database Migration
-- Adds volume_prefix and relative_path columns and populates them from existing filepaths

-- Step 1: Add cross-platform columns to audio_files table
ALTER TABLE audio_files ADD COLUMN volume_prefix TEXT;
ALTER TABLE audio_files ADD COLUMN relative_path TEXT;

-- Step 2: Populate cross-platform data from existing filepaths
-- For macOS paths (/Volumes/Extreme SSD/...)
UPDATE audio_files 
SET volume_prefix = '/Volumes/Extreme SSD',
    relative_path = SUBSTR(filepath, 21)  -- Remove "/Volumes/Extreme SSD/" (20 chars + 1)
WHERE filepath LIKE '/Volumes/Extreme SSD/%';

-- For WSL paths (/mnt/n/AudioWalks/H3-VC/...)  
UPDATE audio_files 
SET volume_prefix = '/mnt/n/AudioWalks/H3-VC',
    relative_path = SUBSTR(filepath, 25)  -- Remove "/mnt/n/AudioWalks/H3-VC/" (24 chars + 1)
WHERE filepath LIKE '/mnt/n/AudioWalks/H3-VC/%';

-- Step 3: Ensure acoustic_indices_core has unique constraint for safe concurrent processing
-- Check if unique index already exists, create if not
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_measurement 
ON acoustic_indices_core(file_id, index_name, chunk_index);

-- Step 4: Show migration results
SELECT 'Migration Summary:' as info;

SELECT 
  COUNT(*) as total_files,
  COUNT(volume_prefix) as files_with_volume,
  COUNT(relative_path) as files_with_relative_path,
  COUNT(CASE WHEN volume_prefix IS NOT NULL AND relative_path IS NOT NULL THEN 1 END) as cross_platform_ready
FROM audio_files;

SELECT DISTINCT volume_prefix, COUNT(*) as file_count
FROM audio_files 
WHERE volume_prefix IS NOT NULL
GROUP BY volume_prefix;

SELECT 'Cross-platform migration completed!' as status;