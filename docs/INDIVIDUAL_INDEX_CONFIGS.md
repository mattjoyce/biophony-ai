# Individual Index Configuration Files

I've created minimal configuration files for each acoustic index available in your `./indices` directory. Each config focuses on calculating just one specific index.

## Temporal Indices (Process with --TEMPORAL)

| Config File | Index | Description |
|-------------|--------|-------------|
| `config_temporal_entropy.yaml` | `temporal_entropy` | Temporal entropy of audio signal |
| `config_temporal_activity.yaml` | `temporal_activity` | Temporal activity level |
| `config_temporal_median.yaml` | `temporal_median` | Temporal median value |
| `config_maad_temporal_activity.yaml` | `maad_temporal_activity` | MAAD Temporal Activity (AAI temporal component) |

## Spectral Indices (Process with --SPECTRAL)

| Config File | Index | Description |
|-------------|--------|-------------|
| `config_acoustic_complexity_index.yaml` | `acoustic_complexity_index` | ACI - Acoustic Complexity Index |
| `config_acoustic_diversity_index.yaml` | `acoustic_diversity_index` | ADI - Acoustic Diversity Index |
| `config_acoustic_eveness_index.yaml` | `acoustic_eveness_index` | AEI - Acoustic Eveness Index |
| `config_bioacoustics_index.yaml` | `bioacoustics_index` | BAI - Bioacoustics Index (2-8kHz) |
| `config_frequency_entropy.yaml` | `frequency_entropy` | Frequency domain entropy |
| `config_spectral_entropy.yaml` | `spectral_entropy` | Spectral entropy |
| `config_number_of_peaks.yaml` | `number_of_peaks` | Number of spectral peaks |
| `config_spectral_activity.yaml` | `spectral_activity` | Spectral activity level |
| `config_spectral_events.yaml` | `spectral_events` | Spectral events detection |
| `config_spectral_cover.yaml` | `spectral_cover` | Spectral coverage |
| `config_soundscape_index.yaml` | `soundscape_index` | NDSI - Normalized Difference Soundscape Index |
| `config_acoustic_gradient_index.yaml` | `acoustic_gradient_index` | AGI - Acoustic Gradient Index |
| `config_spectral_leq.yaml` | `spectral_leq` | Spectral equivalent sound level |
| `config_maad_spectral_activity.yaml` | `maad_spectral_activity` | MAAD Spectral Activity (AAI spectral component) |

## Usage Examples

### Calculate individual temporal indices:
```bash
python3 process_acoustic_indices.py --config config_temporal_entropy.yaml --TEMPORAL --target 1 2
python3 process_acoustic_indices.py --config config_maad_temporal_activity.yaml --TEMPORAL --target 1 2
```

### Calculate individual spectral indices:
```bash
python3 process_acoustic_indices.py --config config_acoustic_complexity_index.yaml --SPECTRAL --target 1 2
python3 process_acoustic_indices.py --config config_maad_spectral_activity.yaml --SPECTRAL --target 1 2
```

### Calculate frequency-specific indices:
```bash
python3 process_acoustic_indices.py --config config_bioacoustics_index.yaml --SPECTRAL --target 1 2
python3 process_acoustic_indices.py --config config_soundscape_index.yaml --SPECTRAL --target 1 2
```

## Notes

- **All configs use WSL paths** (`/mnt/n/AudioWalks/H3-VC/...`)
- **Chunk duration**: 4.5 seconds for all indices
- **Frequency-dependent indices** have configurable frequency ranges:
  - `bioacoustics_index`: 2000-8000 Hz (customizable)
  - `soundscape_index`: Bio 2000-8000 Hz, Anthro 0-2000 Hz (customizable)
- **AAI Components**: 
  - Temporal: `config_maad_temporal_activity.yaml`
  - Spectral: `config_maad_spectral_activity.yaml`
- **ACI**: `config_acoustic_complexity_index.yaml`

These minimal configs make it easy to calculate and test individual indices without processing everything at once!