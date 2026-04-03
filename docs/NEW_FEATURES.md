# New Features & Improvements

## Auto-detect Audio File Duration

**Problem:** Config files require manual `file_duration_sec` parameter, but this varies between deployments (e.g., 10-minute vs 15-minute recording cycles). Mismatch causes processing failures.

**Proposed Solution:** On initial config instantiation, automatically detect the most common file duration from the database:
- Query `SELECT duration_seconds, COUNT(*) FROM audio_files GROUP BY duration_seconds ORDER BY COUNT(*) DESC LIMIT 1`
- Use this as the default `file_duration_sec`
- Allow manual override in config for edge cases
- Log a warning if files have mixed durations

**Benefits:**
- Reduces configuration errors
- Adapts to different AudioMoth recording schedules automatically
- Still allows manual override when needed

**Implementation notes:**
- Add `auto_detect_file_duration()` function in config loader
- Only auto-detect if `file_duration_sec` not explicitly set
- Store detected value in logs for transparency
