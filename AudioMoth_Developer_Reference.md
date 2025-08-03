# 🔧 Developer Reference: AudioMoth Processing Pipeline

## 📁 Dataset Overview

- **Device**: AudioMoth H3-VC
- **Format**: WAV (uncompressed PCM_16)
- **Duration**: 15 minutes (900 seconds)
- **Sample Rate**: 48,000 Hz
- **Bit Depth**: 16-bit
- **Channels**: Mono (or converted)
- **Interval**: One 15-min recording every 30 minutes
- **Total Files**: 1,458 WAVs
- **Time Span**: June 20 – July 31, 2025
- **Filepath Root**: `/mnt/n/AudioWalks/H3-VC/2025-6-20_to_7-31/`

## 🧠 Metadata Handling

- Parsed via `metamoth` and stored in SQLite (`audiomoth.db`)
- Managed by: `audio_database.py`
- Fields include datetime, gain, battery voltage, etc.
- See: `AudioDatabase` class for scan and search utilities

---

## 🎨 Spectrogram Generation (GPU)

### 📐 Internal Geometry (Used for Index Calculation)

- **Output Shape**: `[128, ~169770]` → `(n_mels, time_steps)`
- **Transform**:
  - `n_fft = 2048`
  - `hop_length = 256` ⇒ `~5.33 ms` resolution
  - `sample_rate = 48000`
  - `n_mels = 128`
  - `power = 2.0` (spectral energy)
  - `AmplitudeToDB()` applied

- **Expected Duration Alignment**:
  ```
  900 sec / 0.00533 ≈ 169,770 frames
  ```

### 🖼️ PNG Spectrogram (Display Image)

- **Resolution**: `1000x300 px`
- **Pixel Scale**: `0.9 sec/px`
- **Contrast Normalization**: -40 to +40 dB (percentile-based from global stats)
- **Pipeline**: `generate_spectrograms_gpu_optimized.py`

---

## 💾 Spectrogram Storage Format

- **Format**: `.npz` (Compressed NumPy archive)
- **Filename**: `{basename}_spec.npz` (e.g., `example_spec.npz`)
- **Saved Alongside**: Corresponding WAV file

### Contents:
```python
{
  "spec": ndarray [128, ~169770],
  "fn": frequency vector (optional),
  "time_bins": center timestamps (optional),
  "params": {
    "n_fft": 2048,
    "hop_length": 256,
    "n_mels": 128,
    "sample_rate": 48000,
    "power": 2.0,
    "db_scale": True
  }
}
```

### Example Save:
```python
np.savez_compressed(
    "example_spec.npz",
    spec=spec_db,
    fn=fn,
    time_bins=time,
    params=config_dict
)
```

### ✅ PyTorch Integration:
```python
# Save from PyTorch
np.savez_compressed("example_spec.npz", spec=mel_spec.numpy(), params=params)

# Load into PyTorch
loaded = np.load("example_spec.npz")
mel_spec_tensor = torch.from_numpy(loaded["spec"])
```

---

## 📊 Acoustic Index Inventory

### ✅ Spectral Indices (require .npz spectrogram)

- `acoustic_complexity_index` (ACI)
- `acoustic_diversity_index` (ADI)
- `acoustic_eveness_index` (AEI)
- `bioacoustics_index` (BAI)
- `frequency_entropy`
- `spectral_entropy`
- `soundscape_index` (NDSI, derived)
- `spectral_activity`
- `number_of_peaks` (optional)
- `spectral_cover`, `spectral_events` (if chunked)

### 🔊 Temporal Indices (use raw waveform)

- `temporal_entropy`
- `temporal_activity`
- `temporal_median`
- `acoustic_richness_index` (if implemented)
- `temporal_events` (optional)
- `temporal_leq` (requires A-weighting and calibration)

---

## ⏱️ Chunking Scheme (Pixel-Aligned)

| Index | Chunk Duration | Spectrogram Width (px) | Chunks per File |
|-------|----------------|-------------------------|------------------|
| ACI   | 4.5 s          | 5 px                    | 200              |
| H     | 0.9 s          | 1 px                    | 1000             |
| AEI   | 9.0 s          | 10 px                   | 100              |
| ADI   | 13.5 s         | 15 px                   | 67               |
| NDSI  | 45.0 s         | 50 px                   | 20               |

---

## 🧰 Tools & Scripts

- **Spectrogram Generator**: `generate_spectrograms_gpu_optimized.py` (uses GPU, outputs PNGs)
- **Global Min/Max Calculation**: `calculate_global_minmax.py`
- **Web Interface**: `web_app.py` with `/api/files`, `/api/grid`, `/api/stats`
- **Database Interface**: `audio_database.py`
- **Labels/Annotations**: Supports Audacity label files

---

## 🔒 Parameter Logging (Required for Reproducibility)

Every `.npz` must include:
```yaml
spectrogram_parameters:
  sample_rate: 48000
  n_fft: 2048
  hop_length: 256
  n_mels: 128
  power: 2.0
  db_scale: true
  normalization: false
  chunk_duration_sec: 4.5
```
