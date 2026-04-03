# Spectral Analysis Capabilities Guide

This guide documents the comprehensive spectral analysis capabilities of the bioacoustic research platform, covering spectrogram generation, acoustic indices computation, and advanced frequency domain analysis methods.

## Overview

The platform provides GPU-accelerated spectral analysis designed for ecological acoustic research, supporting:
- **High-resolution spectrogram generation** with customizable parameters
- **Standardized acoustic indices** computation and validation
- **Mel-scale frequency analysis** for perceptually-relevant processing
- **Multi-dimensional visualization** through RGB index mapping
- **Temporal-spectral correlation** with weather and solar events

---

## Spectrogram Generation

### Technical Specifications

**Core Parameters (from config_mac.yaml):**
```yaml
# Spectrogram parameters
n_fft: 2048           # FFT window size (42.67ms at 48kHz)
hop_length: 256       # Hop size (5.33ms at 48kHz) 
n_mels: 128          # Mel frequency bins
sample_rate: 48000    # AudioMoth standard sample rate

# Display parameters  
width_px: 1000       # Output image width
height_px: 300       # Output image height
dpi: 100             # Resolution for publication quality

# Global contrast normalization
global_min: -40      # dB minimum for visualization
global_max: 40       # dB maximum for visualization
```

**Frequency Resolution:**
- **Linear scale:** 23.4 Hz per bin (48000 Hz / 2048 FFT)
- **Mel scale:** Perceptually uniform spacing optimized for biological audio
- **Temporal resolution:** 5.33ms per frame (256 samples / 48000 Hz)
- **Analysis window:** 42.67ms (2048 samples / 48000 Hz)

### Advanced Processing Features

**Colormap Support:**
- Full matplotlib colormap library integration
- Scientific colormaps: viridis, plasma, inferno, magma, cividis
- Grayscale option for publication requirements
- Custom gamma correction (0.1-10.0) for dynamic range adjustment

**GPU Acceleration:**
- CUDA-accelerated FFT computation
- Batch processing for efficient large dataset analysis
- Memory-optimized for 15-minute AudioMoth recordings

### API Integration

**Endpoint:** `GET /api/spectrogram/<date>/<time>`

**Parameters:**
- `colormap`: Matplotlib colormap selection
- `gamma`: Gamma correction factor for visualization enhancement

**Research Applications:**
- Species identification through spectral signature analysis
- Temporal activity pattern visualization
- Frequency band usage assessment
- Publication-quality figure generation

---

## Acoustic Indices Computation

### Standardized Indices Implementation

The platform implements scientifically validated acoustic indices following established methodologies:

#### Temporal Domain Indices

**Temporal Entropy (Ht):**
- Measures temporal predictability of acoustic signals
- Range: 0 (completely predictable) to 1 (maximum entropy)
- Ecological interpretation: Higher values indicate more complex temporal patterns
- Chunk duration: 4.5 seconds for optimal resolution

**Temporal Activity:**
- Quantifies overall acoustic activity levels
- Normalized to recording duration and amplitude
- Useful for identifying periods of high/low biological activity

**Temporal Median:**
- Robust measure of central tendency in temporal domain
- Less sensitive to outliers than mean-based measures
- Effective for comparing activity levels across recordings

#### Spectral Domain Indices

**Acoustic Complexity Index (ACI):**
- Measures spectral complexity based on intensity variations
- Sensitive to bird vocalizations and natural sounds
- Higher values typically indicate greater biological diversity
- Processing: 4.5-second chunks with frequency bin analysis

**Bioacoustic Index (BI):**
- **Standard configuration:** 500-2000 Hz frequency range
- Targets bird vocalization frequencies
- Normalized by total acoustic energy
- Ecological significance: Correlates with avian species richness

**Soundscape Index:**
- **Bioacoustic component:** 500-2000 Hz (biological sounds)
- **Anthropogenic component:** 0-500 Hz (human-generated noise)
- Ratio provides measure of soundscape "naturalness"
- Critical for human impact assessment studies

**Spectral Entropy (Hf):**
- Measures frequency domain complexity
- Range: 0 (single frequency) to 1 (white noise)
- Ecological interpretation: Higher values suggest greater frequency diversity

**Frequency Entropy:**
- Alternative spectral entropy calculation
- Optimized for bioacoustic signal characteristics
- Complementary measure to standard spectral entropy

### Index Validation and Quality Control

**Scientific Standards:**
- All indices implemented following peer-reviewed methodologies
- Parameter selection based on ecological acoustics literature
- Validation against reference implementations (scikit-maad)

**Computational Verification:**
- Reproducible results across processing runs
- Consistent temporal chunking (4.5-second segments)
- Standardized frequency band definitions

**Database Integration:**
- All computed indices stored with processing metadata
- Temporal alignment with AudioMoth recordings
- Cross-referencing with weather and solar event data

---

## Mel-Scale Analysis

### Perceptual Frequency Mapping

**Configuration Parameters:**
- **Default n_mels:** 128 bins
- **Frequency range:** 0 Hz to Nyquist (24 kHz at 48 kHz sampling)
- **Customizable ranges:** fmin/fmax for targeted analysis

**Ecological Relevance:**
- Mel scale approximates auditory perception across species
- Particularly relevant for bird vocalization analysis
- Better resolution in lower frequencies where many animal calls occur

**API Access:**
`GET /api/mel_scale?sample_rate=48000&n_mels=128&fmin=500&fmax=8000`

**Research Applications:**
- Cross-species acoustic comparison
- Perceptually-uniform frequency analysis
- Species-specific frequency band optimization

---

## Multi-Dimensional Visualization

### RGB Index Mapping

**Concept:**
Map three acoustic indices to RGB color channels for simultaneous visualization of multiple soundscape dimensions.

**Example Ecological Interpretation:**
```
Red Channel:   Acoustic Complexity Index (structural complexity)
Green Channel: Temporal Entropy (temporal predictability)
Blue Channel:  Spectral Entropy (frequency diversity)
```

**Technical Implementation:**
- Automatic normalization to 0-255 RGB range
- Per-recording or dataset-wide normalization options
- Raw values preserved alongside RGB mapping

**API Endpoint:**
`GET /api/indices/<date>/<time>/rgb?red=acoustic_complexity_index&green=temporal_entropy&blue=spectral_entropy`

**Research Applications:**
- Soundscape pattern recognition
- Multi-dimensional habitat characterization  
- Visual identification of acoustic anomalies
- Temporal pattern visualization across index space

---

## Integration with Temporal Analysis

### Solar Event Correlation

**Temporal Labels:**
All spectral analysis results are linked to sunrise/sunset temporal labels:
- Dawn recordings: SR+HH:MM (time after sunrise)
- Dusk recordings: SS+HH:MM (time after sunset)
- Night recordings: Time between sunset and sunrise

**Database Views:**
- `acoustic_indices`: Includes temporal labels and weather data
- `bioacoustic_temporal`: Classified by ecological time periods
- Cross-correlation ready for statistical analysis

### Weather Integration

**Environmental Context:**
Spectral analysis results include synchronized weather data:
- Temperature (affects insect/amphibian activity)
- Humidity (influences sound propagation)
- Wind speed (impacts recording quality)
- Precipitation (masks acoustic signals)

**Research Applications:**
- Weather-acoustic correlation studies
- Environmental impact assessment
- Seasonal pattern analysis
- Climate change impact on soundscapes

---

## Advanced Analysis Workflows

### Dawn Chorus Spectral Analysis

```python
# Systematic analysis of dawn chorus spectral patterns
dawn_analysis = {
    'temporal_filter': 'SR+00:00 to SR+02:00',  # Within 2 hours of sunrise
    'indices': ['acoustic_complexity_index', 'spectral_entropy', 'standard_bai_500-2000'],
    'frequency_focus': '500-8000 Hz',  # Bird vocalization range
    'seasonal_comparison': True
}
```

**Ecological Questions:**
- How does spectral complexity change during dawn chorus progression?
- Which frequency bands show greatest seasonal variation?
- How do weather conditions affect dawn chorus spectral characteristics?

### Anthropogenic Impact Assessment

```python
# Compare natural vs. human-impacted soundscapes
impact_analysis = {
    'natural_sites': {'anthropogenic_threshold': 0.1},  # Low human noise
    'impacted_sites': {'anthropogenic_threshold': 0.5}, # High human noise
    'comparison_indices': ['soundscape_index', 'acoustic_complexity_index'],
    'frequency_analysis': {'low': '0-500 Hz', 'bio': '500-2000 Hz', 'high': '2000+ Hz'}
}
```

### Seasonal Spectral Patterns

```python
# Long-term spectral pattern analysis
seasonal_analysis = {
    'time_scale': 'monthly_aggregation',
    'indices': ['spectral_entropy', 'frequency_entropy'],
    'correlation_variables': ['temperature', 'precipitation', 'day_length'],
    'statistical_methods': ['correlation_analysis', 'time_series_decomposition']
}
```

---

## Quality Assurance and Best Practices

### Spectrogram Quality Control

**Pre-processing Checks:**
- Audio file integrity validation
- Sample rate consistency verification
- Dynamic range assessment
- Clipping detection

**Processing Standards:**
- Consistent windowing functions (Hann window default)
- Overlap percentage optimization (87.5% for 256 hop length)
- Frequency resolution sufficient for target species

### Index Computation Validation

**Reproducibility Requirements:**
- Identical results across processing runs
- Version-controlled parameter configurations
- Processing metadata preservation

**Ecological Validation:**
- Ground-truth comparison with manual analysis
- Cross-validation with established studies
- Species-specific index performance assessment

### Performance Optimization

**Computational Efficiency:**
- GPU acceleration for large datasets
- Batch processing optimization
- Memory management for 15-minute recordings
- Parallel processing for multiple files

**Storage Efficiency:**
- Compressed spectrogram caching
- Selective index computation
- Database indexing for fast retrieval

---

## Research Integration Examples

### Publication-Quality Workflows

**Spectrogram Figure Generation:**
```python
# Generate publication-ready spectrograms
publication_specs = {
    'colormap': 'viridis',
    'gamma': 1.2,
    'dpi': 300,
    'frequency_range': '0-12000 Hz',
    'time_annotations': True,
    'scale_bars': True
}
```

**Statistical Analysis Integration:**
```python
# Export acoustic indices for R/Python statistical analysis
analysis_export = {
    'format': 'CSV',
    'variables': ['all_indices', 'weather_data', 'temporal_labels'],
    'temporal_resolution': 'chunk_level',
    'metadata': 'full_deployment_info'
}
```

### Automated Monitoring Workflows

**Real-time Analysis Pipeline:**
- Automated spectrogram generation upon file import
- Index computation with quality flags
- Anomaly detection based on historical patterns
- Alert generation for unusual acoustic events

**Long-term Monitoring:**
- Temporal trend analysis
- Baseline establishment
- Change point detection
- Ecosystem health indicators

This spectral analysis platform provides comprehensive tools for ecological acoustic research, from basic spectrogram visualization to advanced multi-dimensional index analysis, all integrated with temporal and environmental context for robust scientific investigation.