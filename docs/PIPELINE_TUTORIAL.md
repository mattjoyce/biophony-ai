# biophony-ai Pipeline Tutorial

End-to-end guide for processing AudioMoth recordings into acoustic indices and visualising them in the webapp. Verified 2026-04-03.

---

## Prerequisites

- Python 3.11+ with required packages (`pip install -r requirements.txt`)
- AudioMoth WAV recordings
- A config file for your dataset (see [Config Reference](#config-reference))

GPU is not required. CPU processing works fine — spectrogram generation just takes longer.

---

## Overview

```
WAV files → DB (scan) → NPZ (spectrograms) → Indices → PNG → Webapp
```

All steps are driven by a single config file and the `--target 0 1 2 3 4 5 6 7 8 9` flag. Targets are shards for parallel processing on multi-machine deployments; on a single machine always pass all 10.

---

## Step 1: Write a Config File

Create a YAML config for your dataset. Use `config-test.yaml` as a template.

```yaml
input_directory : "~/Documents/myproject/audio"
database_path   : "~/Documents/myproject/audiomoth.db"

# AudioMoth recording parameters
sample_rate: 48000
file_duration_sec: 600        # seconds — must match actual recording duration

# Spectrogram display
width-px : 1000
height-px : 300
border-px : 0
dpi : 100

# Spectrogram computation
n_fft : 2048
hop_length : 256
n_mels : 128
global_min : -40
global_max : 40

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
    temporal_median:
      processor: temporal_median
      params: {}

  spectral:
    chunk_duration_sec: 4.5
    acoustic_complexity_index:
      processor: acoustic_complexity_index
      params: {}
    spectral_entropy:
      processor: spectral_entropy
      params: {}
```

Paths support `~` expansion. See `config-test.yaml` for a full example including species-specific indices.

**Important:** `file_duration_sec` must match the recording duration set in AudioMoth firmware. The pipeline tolerates files that are *shorter* than this (first/last recordings of a deployment) but will skip files that are *longer* (config mismatch).

---

## Step 2: Initialise the Database

```bash
cd ~/Projects/biophony-ai
python3 scan_audio_database.py --config config-test.yaml --init
```

Creates an empty SQLite database at `database_path`. Safe to run on an existing database (no data lost).

---

## Step 3: Scan WAV Files

```bash
python3 scan_audio_database.py --config config-test.yaml --scan
```

Walks `input_directory` recursively, reads AudioMoth metadata from each WAV header, and registers all files in the database. Subsequent scans only add new files.

```
Found 43 WAV files to process...
[  1/43] 243B1F0663FAA6CC_20250915_094030.WAV... ✓
...
New files added: 43
Total files in database: 43
```

Other scan modes:
- `--rescan --force` — re-read metadata for all files (use after moving files)
- `--stats` — show database summary without modifying anything
- `--dry-run` — preview what would happen

---

## Step 4: Generate Spectrograms

```bash
python3 generate_spectrograms_gpu_optimized.py \
  --config config-test.yaml \
  --target 0 1 2 3 4 5 6 7 8 9
```

Reads each WAV file, computes a linear-scale mel spectrogram, and saves it as a `.npz` file alongside the WAV. Also stores per-file statistics (min/max/percentiles) in the database for contrast normalisation.

Output: one `*_spec.npz` per WAV file.

---

## Step 5: Generate Acoustic Indices

Run temporal and spectral indices as separate passes:

```bash
# Temporal indices (from WAV files)
python3 process_acoustic_indices.py \
  --config config-test.yaml \
  --TEMPORAL \
  --target 0 1 2 3 4 5 6 7 8 9

# Spectral indices (from NPZ files)
python3 process_acoustic_indices.py \
  --config config-test.yaml \
  --SPECTRAL \
  --target 0 1 2 3 4 5 6 7 8 9
```

Results are stored in the `acoustic_indices_core` table. Each index is stored as a time-series array (one value per chunk within the recording).

The `--TEMPORAL` pass must complete before `--SPECTRAL` is meaningful, but both can run after spectrograms are generated.

---

## Step 6: Generate PNGs

```bash
python3 generate_png_ultra_fast.py \
  --config config-test.yaml \
  --target 0 1 2 3 4 5 6 7 8 9
```

Converts each `.npz` spectrogram to a `.png` image for the webapp. Uses the global contrast range from `global_min`/`global_max` in config.

Output: one `*_spec.png` per WAV file.

---

## Step 7: Launch the Webapp

```bash
cd webapp/v2/backend
python3 app.py --config ../../../config-test.yaml --port 8001
```

Open **http://localhost:8001** in a browser.

The interface shows:
- Timeline of all recordings for the selected date
- Spectrogram image for the selected recording
- Acoustic index overlays (select from dropdown)
- GGBF and other species-specific detection indices if configured

---

## Complete Pipeline (copy-paste)

```bash
cd ~/Projects/biophony-ai

python3 scan_audio_database.py  --config config-test.yaml --init
python3 scan_audio_database.py  --config config-test.yaml --scan
python3 generate_spectrograms_gpu_optimized.py --config config-test.yaml --target 0 1 2 3 4 5 6 7 8 9
python3 process_acoustic_indices.py --config config-test.yaml --TEMPORAL --target 0 1 2 3 4 5 6 7 8 9
python3 process_acoustic_indices.py --config config-test.yaml --SPECTRAL --target 0 1 2 3 4 5 6 7 8 9
python3 generate_png_ultra_fast.py  --config config-test.yaml --target 0 1 2 3 4 5 6 7 8 9

cd webapp/v2/backend
python3 app.py --config ../../../config-test.yaml --port 8001
```

---

## Config Reference

| Key | Required | Description |
|-----|----------|-------------|
| `input_directory` | yes | Path to folder containing dated subdirectories of WAV files |
| `database_path` | yes | Path to SQLite database (created automatically) |
| `sample_rate` | yes | AudioMoth sample rate in Hz (typically 48000) |
| `file_duration_sec` | yes | Recording duration set in firmware (e.g. 600) |
| `n_fft` | yes | FFT window size for spectrogram |
| `hop_length` | yes | Hop length for spectrogram |
| `n_mels` | yes | Number of mel bins |
| `global_min` | yes | dB floor for spectrogram display |
| `global_max` | yes | dB ceiling for spectrogram display |
| `acoustic_indices` | yes | Index definitions (see config-test.yaml) |
| `width-px` | no | Spectrogram image width in pixels |
| `height-px` | no | Spectrogram image height in pixels |

Paths are expanded via `loaden` — `~` and `${ENV_VAR}` are supported.

---

## Troubleshooting

**`ModuleNotFoundError`** — Install missing packages: `pip install -r requirements.txt`

**`--target is required`** — Always pass `--target 0 1 2 3 4 5 6 7 8 9` for single-machine runs.

**First recording skipped or uses fewer chunks** — Expected. First/last recordings in a deployment are legitimately shorter. The pipeline accepts them.

**Empty webapp on load** — Webapp now auto-selects the first available date. If the grid is empty, check that PNGs were generated in the same directory as the WAVs.

**`File duration outside tolerance`** — Config `file_duration_sec` is longer than actual files. The pipeline now only rejects files *longer* than expected, so this should only appear for genuine config mismatches.
