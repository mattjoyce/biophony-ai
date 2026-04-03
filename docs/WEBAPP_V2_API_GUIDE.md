# WebApp v2 API Guide for Research Analysts

This guide documents the comprehensive REST API available in the webapp v2 backend for bioacoustic research analysis. The API provides access to audio files, spectrograms, acoustic indices, weather data, and temporal analysis capabilities.

## Overview

The webapp v2 API is built with Flask and provides RESTful endpoints for:
- **Audio file streaming and metadata access**
- **Spectrogram generation with advanced processing**
- **Acoustic indices analysis and RGB visualization**
- **Weather data correlation**
- **Temporal analysis with sunrise/sunset labeling**
- **File navigation and search capabilities**

## Base URL Structure
All endpoints are prefixed with `/api/` and follow RESTful conventions.

---

## Audio API Endpoints

### Get Audio File by Filename
```http
GET /api/audio/<filename>
```
Serves audio files with range support for streaming/seeking.

**Parameters:**
- `filename` (string): Audio filename from database

**Response:** Audio/WAV file with streaming support

**Use Cases:**
- Audio playback in research interfaces
- Streaming for long AudioMoth recordings
- Audio analysis tool integration

### Get Audio File by Date/Time
```http
GET /api/audio/<date>/<time>
```
Serves audio file for specific recording datetime.

**Parameters:**
- `date` (string): Recording date (YYYY-MM-DD)
- `time` (string): Recording time (HH:MM or HH:MM:SS)

**Response:** Audio/WAV file

**Example:**
```bash
curl "http://localhost:5000/api/audio/2025-06-20/06:00"
```

---

## Spectrogram API Endpoints

### Get Processed Spectrogram
```http
GET /api/spectrogram/<date>/<time>
```
Returns GPU-accelerated spectrogram image with colormap and gamma processing.

**Parameters:**
- `date` (string): Recording date
- `time` (string): Recording time

**Query Parameters:**
- `colormap` (optional): Matplotlib colormap name (default: 'viridis')
- `gamma` (optional): Gamma correction factor 0.1-10.0 (default: 1.0)

**Response:** PNG image (spectrogram visualization)

**Example:**
```bash
curl "http://localhost:5000/api/spectrogram/2025-06-20/06:00?colormap=plasma&gamma=1.5"
```

**Research Applications:**
- Visual inspection of frequency patterns
- Species identification through spectral signatures
- Temporal activity pattern analysis
- Publication-quality spectrogram generation

### Get Available Colormaps
```http
GET /api/colormaps
```
Returns list of available matplotlib colormaps for spectrogram visualization.

**Response:**
```json
{
  "success": true,
  "data": ["viridis", "plasma", "inferno", "magma", "cividis", ...]
}
```

### Get Colormap Data
```http
GET /api/colormap/<colormap_name>
```
Returns matplotlib colormap as JSON array for custom visualization.

**Parameters:**
- `colormap_name` (string): Name of matplotlib colormap

**Response:** JSON array of RGB values

### Get Mel Scale Mapping
```http
GET /api/mel_scale
```
Returns mel scale frequency mapping for spectrogram frequency axis.

**Query Parameters:**
- `sample_rate` (optional): Audio sample rate in Hz (default: 48000)
- `n_mels` (optional): Number of mel bins (default: 128)
- `fmin` (optional): Minimum frequency in Hz (default: 0)
- `fmax` (optional): Maximum frequency in Hz (default: sample_rate/2)

**Response:** JSON with mel scale frequency mappings

**Research Applications:**
- Perceptually-uniform frequency analysis
- Bird song analysis (mel scale matches avian auditory perception)
- Cross-species acoustic comparison

---

## Acoustic Indices API Endpoints

### Get Available Index Types
```http
GET /api/indices/available
```
Returns list of all computed acoustic index types in the database.

**Response:**
```json
{
  "success": true,
  "data": ["acoustic_complexity_index", "temporal_entropy", "spectral_entropy", ...]
}
```

### Get All Indices for Recording
```http
GET /api/indices/<date>/<time>
```
Returns all acoustic indices data for a specific recording.

**Response:**
```json
{
  "success": true,
  "data": {
    "file_info": {
      "id": 123,
      "filename": "...",
      "duration_seconds": 900
    },
    "indices": {
      "acoustic_complexity_index": [
        {"chunk_index": 0, "start_time_sec": 0.0, "value": 0.85},
        {"chunk_index": 1, "start_time_sec": 4.5, "value": 0.92}
      ],
      "temporal_entropy": [...]
    }
  }
}
```

**Research Applications:**
- Temporal pattern analysis across recording periods
- Index correlation studies
- Soundscape complexity assessment

### Get RGB-Mapped Indices Visualization
```http
GET /api/indices/<date>/<time>/rgb
```
Returns acoustic indices mapped to RGB channels for multi-dimensional visualization.

**Query Parameters:**
- `red` (optional): Index name for red channel
- `green` (optional): Index name for green channel  
- `blue` (optional): Index name for blue channel

**Response:**
```json
{
  "success": true,
  "data": {
    "rgb_data": [
      {
        "chunk_index": 0,
        "start_time_sec": 0.0,
        "rgb": [255, 128, 64],
        "raw_values": {
          "red": 0.85,
          "green": 0.42,
          "blue": 0.25
        }
      }
    ],
    "channel_assignments": {
      "red": "acoustic_complexity_index",
      "green": "temporal_entropy",
      "blue": "spectral_entropy"
    },
    "normalization_ranges": {...}
  }
}
```

**Research Applications:**
- Multi-dimensional soundscape visualization
- Index correlation analysis
- Pattern recognition across multiple acoustic dimensions

---

## File Management API Endpoints

### Get Available Dates
```http
GET /api/dates
```
Returns all dates that have audio recordings.

**Response:** Array of date strings (YYYY-MM-DD)

### Get Files for Specific Date
```http
GET /api/files/<date>
```
Returns all recordings for a specific date.

**Response:** Array of file metadata objects

### Get File Information
```http
GET /api/file/<date>/<time>
```
Returns detailed metadata for specific recording.

**Response:**
```json
{
  "success": true,
  "data": {
    "id": 123,
    "filename": "...",
    "filepath": "...",
    "recording_datetime": "2025-06-20T06:00:00",
    "duration_seconds": 900,
    "audiomoth_id": "...",
    "temperature_c": 15.2,
    "time_since_last": "SR+01:30",
    "time_to_next": "SS-08:45"
  }
}
```

### Search Files with Filters
```http
GET /api/files
```
Search recordings with temporal and other filters.

**Query Parameters:**
- `date_from` (optional): Start date (YYYY-MM-DD)
- `date_to` (optional): End date (YYYY-MM-DD)
- `time_from` (optional): Start time (HH:MM)
- `time_to` (optional): End time (HH:MM)
- `limit` (optional): Maximum results (1-1000, default: 100)

**Example:**
```bash
curl "http://localhost:5000/api/files?date_from=2025-06-20&date_to=2025-06-30&time_from=05:00&time_to=08:00&limit=50"
```

**Research Applications:**
- Dawn chorus analysis (filter by time_from=05:00&time_to=08:00)
- Seasonal pattern analysis (filter by date ranges)
- Temporal sampling for statistical analysis

### Navigation Between Files
```http
GET /api/navigation
```
Get next/previous file in temporal sequence.

**Query Parameters:**
- `date` (required): Current file date
- `time` (required): Current file time
- `direction` (required): 'next' or 'prev'

**Research Applications:**
- Sequential file analysis
- Temporal continuity checking
- Manual review workflows

### Get Available Times Structure
```http
GET /api/available_times
```
Returns hierarchical structure of all available dates and times.

**Response:**
```json
{
  "2025-06-20": ["06:00", "06:15", "06:30", ...],
  "2025-06-21": ["06:00", "06:15", "06:30", ...],
  ...
}
```

---

## Weather Integration API

### Get Weather Data for Recording
```http
GET /api/weather/<date>/<time>
```
Returns weather conditions and temporal labels for specific recording.

**Response:**
```json
{
  "success": true,
  "data": {
    "temperature_2m": 15.2,
    "relative_humidity_2m": 78.5,
    "wind_speed_10m": 5.3,
    "precipitation": 0.0,
    "sunrise_time": "06:45:00",
    "sunset_time": "18:30:00",
    "time_since_last": "SR+01:30",
    "time_to_next": "SS-08:45"
  }
}
```

**Research Applications:**
- Weather-acoustic correlation studies
- Activity pattern analysis relative to solar events
- Environmental impact assessment on soundscapes

---

## Advanced Research Workflows

### Multi-Index Time Series Analysis
Combine multiple endpoints to build comprehensive temporal analysis:

```python
# Get all available indices
indices = requests.get('/api/indices/available').json()['data']

# For each date in study period
for date in study_dates:
    files = requests.get(f'/api/files/{date}').json()['data']
    
    for file_info in files:
        # Get acoustic indices
        indices_data = requests.get(f'/api/indices/{date}/{file_info["time"]}').json()
        
        # Get weather context
        weather = requests.get(f'/api/weather/{date}/{file_info["time"]}').json()
        
        # Combine for analysis
        analysis_record = {
            'datetime': file_info['recording_datetime'],
            'temporal_label': weather['data']['time_since_last'],
            'indices': indices_data['data']['indices'],
            'weather': weather['data']
        }
```

### RGB Visualization Pipeline
Create multi-dimensional acoustic visualizations:

```python
# Define RGB channel assignments for ecological interpretation
rgb_mapping = {
    'red': 'acoustic_complexity_index',    # Structural complexity
    'green': 'temporal_entropy',           # Temporal predictability  
    'blue': 'spectral_entropy'            # Frequency diversity
}

# Generate RGB visualization
rgb_data = requests.get(
    f'/api/indices/{date}/{time}/rgb',
    params=rgb_mapping
).json()

# Create temporal RGB visualization showing soundscape dimensions over time
```

### Dawn Chorus Analysis Workflow
Systematic analysis of dawn activity patterns:

```python
# Find all dawn recordings (within 2 hours of sunrise)
dawn_files = requests.get('/api/files', params={
    'time_from': '05:00',
    'time_to': '08:00',
    'limit': 1000
}).json()['data']

# Filter for dawn period using temporal labels
dawn_recordings = []
for file_info in dawn_files:
    weather = requests.get(f'/api/weather/{file_info["date"]}/{file_info["time"]}').json()
    if weather['data']['time_since_last'].startswith('SR') and \
       int(weather['data']['time_since_last'][3:5]) <= 2:  # Within 2 hours of sunrise
        dawn_recordings.append(file_info)
```

## Technical Specifications

### Response Format
All API endpoints return JSON with standardized structure:
- **Success responses:** `{"success": true, "data": <result>}`
- **Error responses:** `{"success": false, "error": "<message>"}` with HTTP status codes

### Authentication
Currently no authentication required. For production deployment, implement:
- API key authentication for external access
- Rate limiting for computational endpoints
- CORS configuration for web applications

### Performance Considerations
- **Spectrogram endpoint:** GPU-accelerated, cached results
- **Audio streaming:** Range request support for efficient seeking
- **Database queries:** Indexed on datetime and file_id for fast retrieval
- **Large result sets:** Use `limit` parameter to control response size

### Error Handling
- **400 Bad Request:** Invalid parameters or date/time format
- **404 Not Found:** File or data not found for specified datetime
- **500 Internal Server Error:** Database connection or processing errors

---

## Integration Examples

### Python Research Interface
```python
class BioacousticAPI:
    def __init__(self, base_url):
        self.base_url = base_url
    
    def get_dawn_chorus_data(self, date_range):
        """Get all dawn recordings with indices and weather"""
        # Implementation using multiple API endpoints
        
    def analyze_temporal_patterns(self, index_name, period_filter):
        """Analyze index patterns across temporal periods"""
        # Implementation combining indices and temporal labels
```

### R Data Analysis
```r
library(httr)
library(jsonlite)

# Function to fetch and structure acoustic data for R analysis
get_acoustic_timeseries <- function(base_url, date_from, date_to) {
  # Implementation using httr and jsonlite
}
```

This API provides comprehensive access to all bioacoustic analysis capabilities, enabling researchers to build custom analysis workflows, automated processing pipelines, and interactive visualization tools.