# BiophonyAI - Comprehensive Bioacoustic Analysis Platform

## Project Evolution

BiophonyAI has evolved from a focused AudioMoth analysis tool into a comprehensive, production-ready bioacoustic analysis platform for ecological research. The system now processes large-scale acoustic datasets with GPU acceleration, weather integration, and a sophisticated web interface for interactive scientific analysis.

## Current Capabilities

### Core Platform Features
1. **Advanced Database Management**: Normalized SQLite schema with optimized views, weather integration, and configuration tracking
2. **GPU-Accelerated Processing**: PyTorch-based spectrogram generation with 3-5x performance improvement
3. **Comprehensive Acoustic Indices**: Modular processor architecture supporting 8+ acoustic indices (ACI, BAI, NDSI, entropy measures)
4. **Interactive Web Interface**: Flask application with timeline navigation, audio playback, and weather correlation
5. **Production-Scale Processing**: Sharded processing system with file locking for distributed analysis

### Enhanced Architecture

#### Database Layer (Production-Ready)
- **Normalized Schema**: `acoustic_indices_core`, `index_configurations`, `weather_data` tables
- **Optimized Views**: `acoustic_indices`, `indices_by_file`, `index_statistics` for efficient queries
- **Weather Integration**: Temperature, humidity, wind, precipitation correlation with acoustic patterns
- **Configuration Tracking**: Reproducible analysis with parameter versioning

#### Processing Pipeline (Scalable)
- **GPU Spectrogram Engine**: PyTorch/CUDA acceleration with NPZ storage format
- **Modular Indices System**: Separates temporal (WAV-based) and spectral (NPZ-based) processing
- **Parallel Processing**: File-level sharding (modulo 10) with distributed processing support
- **Scientific Reproducibility**: Fixed seeds, deterministic processing, configuration hash tracking

#### Web Interface (Interactive)
- **Time Grid Navigation**: 30-minute slot browsing with visual status indicators
- **Spectrogram Viewer**: Interactive pan/zoom with frequency tracking and position display
- **Weather Overlay**: Real-time environmental data correlation (temp: 8.5°C, humidity: 93.4%)
- **Audio Playback**: Direct WAV playback with gamma adjustment controls
- **Statistics Dashboard**: Processing status, index summaries, and data export

## Dataset Specifications (Expanded)

- **Current Dataset**: AudioMoth H3-VC recordings (June-July 2025, 42 days)
- **Supported Formats**: All AudioMoth variants via metamoth library
- **Processing Capacity**: Unlimited dataset size with sharded processing
- **Analysis Granularity**: 0.9s to 45s temporal chunks with pixel-perfect alignment

## Research Applications (Advanced)

### Multi-Species Monitoring
- **Frog Population Dynamics**: Species-specific frequency band analysis (Eastern Froglet: 2500-3500 Hz)
- **Bird Chorus Patterns**: Dawn/dusk activity correlation with weather conditions
- **Anthropogenic Impact**: Urban noise separation using NDSI analysis

### Environmental Correlation
- **Weather Integration**: Open-Meteo API for temperature, humidity, wind, precipitation data
- **Temporal Patterns**: Long-term soundscape change detection with environmental drivers
- **Habitat Assessment**: Acoustic complexity correlation with biodiversity metrics

### Scientific Workflow
- **Reproducible Analysis**: Configuration-based processing with version control
- **Data Export**: CSV, JSON formats for integration with R, MATLAB, Python analysis
- **Publication Ready**: Scientific citations, parameter documentation, methodology tracking

## Technical Stack (Production)

### Core Infrastructure
- **Backend**: Python 3.8+, SQLite with WAL mode, Flask with RESTful API
- **Processing**: PyTorch/CUDA, scikit-maad, metamoth, NumPy/librosa
- **Storage**: NPZ spectrograms, PNG visualizations, optimized database indexes
- **Web Interface**: Modern HTML5 with responsive design, audio playback support

### Performance Optimizations
- **GPU Acceleration**: 3-5x speedup for spectrogram generation
- **Memory Management**: Aggressive cleanup, chunked processing, efficient NPZ format
- **Database Optimization**: Bulk operations, optimized indexes, WAL mode
- **Parallel Processing**: Multi-core and multi-machine distribution

## Deployment Status

### Completed Features ✅
- ✅ **Database Schema**: Complete normalized schema with views and optimization
- ✅ **GPU Processing**: PyTorch-based spectrogram generation with statistics
- ✅ **Acoustic Indices**: Temporal and spectral processors with modular architecture  
- ✅ **Web Interface**: Interactive viewer with navigation and audio playback
- ✅ **Weather Integration**: Open-Meteo API with correlation analysis
- ✅ **Configuration System**: YAML-based analysis setups with reproducibility
- ✅ **Documentation**: Comprehensive guides (CLAUDE.md, DATABASE_DEVELOPER_GUIDE.md)

### Active Research Applications 🔬
- 🐸 **Frog Species Monitoring**: Multi-species population dynamics analysis
- 🌧️ **Weather Correlation**: Environmental impact on acoustic patterns  
- 📊 **Long-term Datasets**: Continuous monitoring analysis (months to years)
- 🔊 **Soundscape Ecology**: Anthropogenic vs biophonic sound separation

## Open Source Release

**GitHub Repository**: https://github.com/mattjoyce/biophony-ai

BiophonyAI is now available as a comprehensive open-source platform for the bioacoustic research community, with:
- Professional documentation and installation guides
- Example configurations for common research scenarios
- Community support through GitHub issues and discussions
- Scientific citation format for research publications

## Future Roadmap

1. **Machine Learning Integration**: Species classification and automated annotation
2. **Cloud Processing**: AWS/Azure integration for large-scale analysis
3. **Real-time Monitoring**: Live AudioMoth feed processing and alerts
4. **Community Features**: Shared datasets, collaborative annotation, research networks