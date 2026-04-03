### Main App Setup (`app.py`)
```python
from flask import Flask
from config import load_config, setup_cli
from database import init_database
from api.files import files_bp
from api.spectrograms import spectrograms_bp
from api.audio import audio_bp

def create_app(config_path: str):
    """Application factory pattern"""
    app = Flask(__name__)
    
    # Load configuration
    config = load_config(config_path)
    app.config.update(config)
    
    # Initialize database
    init_database(config.get('database_path', 'audiomoth.db'))
    
    # Register blueprints
    app.register_blueprint(files_bp)
    app.register_blueprint(spectrograms_bp)
    app.register_blueprint(audio_bp)
    
    return app

if __name__ == '__main__':
    args = setup_cli()
    app = create_app(args.config)
    app.run(host='0.0.0.0', port=args.port, debug=True)
```

Perfect! This preserves your existing workflow:

✅ **Same config files** - Reuse your existing YAML configs  
✅ **Same CLI pattern** - `python app.py --config my_project.yaml`  
✅ **Same paths** - Database, audio, spectrogram paths all configurable  
✅ **Backward compatible** - Won't break your existing project setup

### Development Workflow
```bash
# Run v1 (existing) on port 8000
cd ./webapp/v1
python web_app.py --config ../config/site_a.yaml

# Run v2 (new) on port 8001 for testing
cd ./webapp/v2/backend  
python app.py --config ../../config/site_a.yaml --port 8001
```

This way you can run both versions side-by-side during development, using the same data sources, and gradually migrate when v2 is ready for your real frog research! 🐸# AudioMoth Spectrogram Viewer - Development Specification

> **Note for AI Coders**: This spec includes code examples as concrete guidance for architecture patterns and anti-patterns. Use these as templates for consistent implementation across components.

## Overview
A clean, maintainable web application for viewing AudioMoth spectrograms with date selection, timeline navigation, and audio playback.

## Technology Stack

### Backend
- **Flask 3.x** - Lightweight web framework
- **SQLAlchemy 2.x** - Modern ORM with type hints
- **Pydantic** - Request/response validation
- **Pillow** - Image processing
- **NumPy** - Numerical operations for spectrograms
- **Matplotlib** - Colormap generation (cached)

### Frontend
- **Vanilla JavaScript (ES6+ modules)** - No framework overhead
- **Canvas API** - High-performance spectrogram rendering
- **Web Audio API** - Audio playback via Howler.js
- **Easepick** - Date picker with constraints
- **CSS Grid/Flexbox** - Modern responsive layout

### Development Tools
- **Python 3.11+** - Modern Python features
- **ESLint** - JavaScript linting
- **Black** - Python code formatting
- **pytest** - Backend testing
- **Jest** - Frontend testing (optional)

### Why These Choices?
- **Flask over FastAPI** - Simpler for this use case, less overhead
- **Vanilla JS over React** - Direct canvas manipulation, no virtual DOM overhead
- **SQLAlchemy over raw SQL** - Type safety, relationship management
- **Easepick over custom datepicker** - Proven, constraint-capable
- **Howler.js over Web Audio API** - Better browser compatibility, simpler API

## Architecture Principles
- **Clean separation**: No SQL in frontend, no HTML generation in backend
- **Component-based**: Each UI element is a self-contained module
- **Service layer**: Business logic separated from routes
- **Structured vanilla JS**: No framework overhead, but proper organization
- **Event-driven**: Components communicate via events, not direct calls

## File Structure

```
audiomoth-viewer/
├── backend/
│   ├── app.py                 # Flask app setup only
│   ├── models/
│   │   ├── __init__.py
│   │   └── audio_file.py      # SQLAlchemy models
│   ├── services/
│   │   ├── __init__.py
│   │   ├── file_service.py    # File operations
│   │   ├── spectrogram_service.py
│   │   └── colormap_service.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── files.py           # File-related endpoints
│   │   ├── spectrograms.py    # Spectrogram endpoints
│   │   └── audio.py           # Audio endpoints
│   ├── database.py            # Database connection
│   └── config.py              # Configuration
├── frontend/
│   ├── index.html             # Minimal HTML structure
│   ├── css/
│   │   └── main.css          # All styles
│   └── js/
│       ├── main.js           # App initialization
│       ├── components/
│       │   ├── DatePicker.js
│       │   ├── Timeline.js
│       │   ├── SpectrogramViewer.js
│       │   └── AudioPlayer.js
│       ├── services/
│       │   ├── ApiService.js  # All API communication
│       │   └── StateManager.js
│       └── utils/
│           └── helpers.js
└── requirements.txt
```

## Backend Specification

### Models (`models/audio_file.py`)
```python
from sqlalchemy import Column, Integer, String, DateTime, Float
from database import Base

class AudioFile(Base):
    __tablename__ = 'audio_files'
    
    id = Column(Integer, primary_key=True)
    filename = Column(String, nullable=False)
    filepath = Column(String, nullable=False)
    recording_datetime = Column(DateTime, nullable=False)
    duration_seconds = Column(Float, nullable=False)
    audiomoth_id = Column(String)
```

### Services

#### File Service (`services/file_service.py`)
```python
from typing import List, Optional
from datetime import date
from models.audio_file import AudioFile

class FileService:
    @staticmethod
    def get_available_dates() -> List[str]:
        """Return list of dates that have audio files (YYYY-MM-DD format)"""
        pass
    
    @staticmethod
    def get_files_for_date(date: str) -> List[dict]:
        """Return all files for a specific date with time and metadata"""
        pass
    
    @staticmethod
    def get_file_by_datetime(date: str, time: str) -> Optional[dict]:
        """Get specific file by date and time"""
        pass
    
    @staticmethod
    def get_weather_for_datetime(date: str, time: str) -> Optional[dict]:
        """Get weather data for specific recording time"""
        pass
    
    @staticmethod
    def get_file_by_filename(filename: str) -> Optional[dict]:
        """Get file information by filename for audio serving"""
        pass
```

#### Spectrogram Service (`services/spectrogram_service.py`)
```python
from typing import Optional
import io

class SpectrogramService:
    @staticmethod
    def get_spectrogram_image(date: str, time: str) -> Optional[io.BytesIO]:
        """Return spectrogram image as bytes"""
        pass
    
    @staticmethod
    def apply_colormap(image_data: bytes, colormap: str, gamma: float) -> bytes:
        """Apply colormap and gamma correction to grayscale image"""
        pass
```

### API Endpoints

#### Files API (`api/files.py`)
```python
from flask import Blueprint, jsonify
from services.file_service import FileService

files_bp = Blueprint('files', __name__)

@files_bp.route('/api/dates')
def get_available_dates():
    """Get all dates that have audio files"""
    dates = FileService.get_available_dates()
    return jsonify(dates)

@files_bp.route('/api/files/<date>')
def get_files_for_date(date: str):
    """Get all files for a specific date"""
    files = FileService.get_files_for_date(date)
    return jsonify(files)

@files_bp.route('/api/file/<date>/<time>')
def get_file_info(date: str, time: str):
    """Get specific file information"""
    file_info = FileService.get_file_by_datetime(date, time)
    if not file_info:
        return jsonify({'error': 'File not found'}), 404
    return jsonify(file_info)

@files_bp.route('/api/weather/<date>/<time>')
def get_weather_data(date: str, time: str):
    """Get weather data for specific recording"""
    weather_data = FileService.get_weather_for_datetime(date, time)
    if not weather_data:
        return jsonify({'error': 'Weather data not found'}), 404
    return jsonify(weather_data)
```

#### Spectrograms API (`api/spectrograms.py`)
```python
from flask import Blueprint, request, send_file
from services.spectrogram_service import SpectrogramService

spectrograms_bp = Blueprint('spectrograms', __name__)

@spectrograms_bp.route('/api/spectrogram/<date>/<time>')
def get_spectrogram(date: str, time: str):
    """Get spectrogram image"""
    colormap = request.args.get('colormap', 'viridis')
    gamma = float(request.args.get('gamma', 1.0))
    
    image_data = SpectrogramService.get_spectrogram_image(date, time)
    if not image_data:
        return jsonify({'error': 'Spectrogram not found'}), 404
    
    # Apply colormap and gamma if not default
    if colormap != 'grayscale' or gamma != 1.0:
        image_data = SpectrogramService.apply_colormap(image_data, colormap, gamma)
    
    return send_file(image_data, mimetype='image/png')
```

#### Audio API (`api/audio.py`)
```python
from flask import Blueprint, send_file, request
from services.file_service import FileService

audio_bp = Blueprint('audio', __name__)

@audio_bp.route('/api/audio/<filename>')
def serve_audio(filename: str):
    """Serve audio files with range support for streaming"""
    file_info = FileService.get_file_by_filename(filename)
    if not file_info:
        return jsonify({'error': 'Audio file not found'}), 404
    
    return send_file(
        file_info['filepath'], 
        mimetype='audio/wav',
        conditional=True  # Enable range requests
    )
```

## Frontend Specification

### HTML Structure (`index.html`)
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AudioMoth Spectrogram Viewer</title>
    <link rel="stylesheet" href="css/main.css">
    <script src="https://cdn.jsdelivr.net/npm/@easepick/bundle@1.2.1/dist/index.umd.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/howler/2.2.3/howler.min.js"></script>
</head>
<body>
    <div class="app">
        <header class="controls">
            <div class="date-control">
                <label>Date:</label>
                <input type="text" id="date-picker" readonly>
            </div>
            <div class="colormap-control">
                <label>Colormap:</label>
                <select id="colormap-selector">
                    <option value="viridis">Viridis</option>
                    <option value="plasma">Plasma</option>
                    <option value="inferno">Inferno</option>
                    <option value="grayscale">Grayscale</option>
                </select>
            </div>
            <div class="gamma-control">
                <label>Gamma:</label>
                <input type="range" id="gamma-slider" min="0.1" max="3.0" value="1.0" step="0.1">
                <span id="gamma-value">1.0</span>
            </div>
        </header>
        
        <main class="viewer">
            <div id="timeline-container" class="timeline"></div>
            
            <div class="viewer-layout">
                <div class="info-panels">
                    <div class="coordinates-panel">
                        <h4>Cursor Position</h4>
                        <div id="pixel-coords">x:---- y:----</div>
                        <div id="time-coords">Time: --:--:--</div>
                        <div id="freq-coords">Freq: ---- Hz</div>
                    </div>
                    <div class="weather-panel">
                        <h4>Weather Data</h4>
                        <div id="temperature">Temp: --°C</div>
                        <div id="humidity">Humidity: --%</div>
                        <div id="wind-speed">Wind: -- km/h</div>
                        <div id="precipitation">Rain: -- mm</div>
                    </div>
                </div>
                
                <div id="spectrogram-container" class="spectrogram">
                    <canvas id="spectrogram-canvas"></canvas>
                    <div id="crosshair-vertical" class="crosshair-vertical"></div>
                    <div id="crosshair-horizontal" class="crosshair-horizontal"></div>
                    <div id="playback-cursor" class="cursor"></div>
                </div>
            </div>
            
            <div id="audio-controls" class="audio-controls">
                <button id="play-pause">▶</button>
                <button id="stop">⏹</button>
                <span id="time-display">00:00 / 15:00</span>
            </div>
        </main>
    </div>
    
    <script type="module" src="js/main.js"></script>
</body>
</html>
```

### Component Specifications

#### State Manager (`js/services/StateManager.js`)
```javascript
export class StateManager extends EventTarget {
    constructor() {
        super();
        this.state = {
            selectedDate: null,
            selectedTime: null,
            availableDates: [],
            dayFiles: [],
            colormap: 'viridis',
            gamma: 1.0,
            isLoading: false
        };
    }
    
    setState(updates) {
        const oldState = { ...this.state };
        this.state = { ...this.state, ...updates };
        this.dispatchEvent(new CustomEvent('statechange', {
            detail: { oldState, newState: this.state }
        }));
    }
    
    getState() {
        return { ...this.state };
    }
}
```

#### API Service (`js/services/ApiService.js`)
```javascript
export class ApiService {
    static async getAvailableDates() {
        const response = await fetch('/api/dates');
        return response.json();
    }
    
    static async getFilesForDate(date) {
        const response = await fetch(`/api/files/${date}`);
        return response.json();
    }
    
    static async getSpectrogram(date, time, colormap = 'viridis', gamma = 1.0) {
        const params = new URLSearchParams({ colormap, gamma });
        const response = await fetch(`/api/spectrogram/${date}/${time}?${params}`);
        return response.blob();
    }
    
    static async getWeatherData(date, time) {
        const response = await fetch(`/api/weather/${date}/${time}`);
        if (!response.ok) {
            throw new Error(`Weather data not available: ${response.status}`);
        }
        return response.json();
    }
    
    static getAudioUrl(filename) {
        // Return URL for Howler.js to stream directly (supports range requests)
        return `/api/audio/${filename}`;
    }
}
```

#### Date Picker Component (`js/components/DatePicker.js`)
```javascript
import { ApiService } from '../services/ApiService.js';

export class DatePicker {
    constructor(elementId, stateManager) {
        this.element = document.getElementById(elementId);
        this.stateManager = stateManager;
        this.picker = null;
        this.init();
    }
    
    async init() {
        const availableDates = await ApiService.getAvailableDates();
        this.stateManager.setState({ availableDates });
        
        this.picker = new easepick.create({
            element: this.element,
            format: 'YYYY-MM-DD',
            LockPlugin: {
                filter: (date) => !availableDates.includes(date.format('YYYY-MM-DD'))
            },
            setup: (picker) => {
                picker.on('select', (e) => {
                    const selectedDate = e.detail.date.format('YYYY-MM-DD');
                    this.handleDateSelected(selectedDate);
                });
            }
        });
    }
    
    async handleDateSelected(date) {
        this.stateManager.setState({ isLoading: true });
        const dayFiles = await ApiService.getFilesForDate(date);
        this.stateManager.setState({
            selectedDate: date,
            dayFiles,
            selectedTime: null,
            isLoading: false
        });
    }
}
```

#### Timeline Component (`js/components/Timeline.js`)
```javascript
export class Timeline {
    constructor(containerId, stateManager) {
        this.container = document.getElementById(containerId);
        this.stateManager = stateManager;
        this.canvas = null;
        this.init();
    }
    
    init() {
        this.canvas = document.createElement('canvas');
        this.canvas.width = 800;
        this.canvas.height = 60;
        this.container.appendChild(this.canvas);
        
        this.canvas.addEventListener('click', (e) => this.handleClick(e));
        
        // Listen for state changes
        this.stateManager.addEventListener('statechange', (e) => {
            const { newState } = e.detail;
            if (newState.dayFiles !== e.detail.oldState.dayFiles) {
                this.render(newState.dayFiles);
            }
        });
    }
    
    render(files) {
        const ctx = this.canvas.getContext('2d');
        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Draw timeline base
        ctx.strokeStyle = '#ccc';
        ctx.beginPath();
        ctx.moveTo(0, 30);
        ctx.lineTo(this.canvas.width, 30);
        ctx.stroke();
        
        // Draw file markers
        files.forEach(file => {
            const x = this.timeToX(file.time);
            ctx.fillStyle = '#007bff';
            ctx.beginPath();
            ctx.arc(x, 30, 4, 0, 2 * Math.PI);
            ctx.fill();
        });
    }
    
    timeToX(timeStr) {
        const [hours, minutes] = timeStr.split(':').map(Number);
        const totalMinutes = hours * 60 + minutes;
        return (totalMinutes / (24 * 60)) * this.canvas.width;
    }
    
    handleClick(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        
        // Find closest file
        const state = this.stateManager.getState();
        let closestFile = null;
        let minDistance = Infinity;
        
        state.dayFiles.forEach(file => {
            const fileX = this.timeToX(file.time);
            const distance = Math.abs(x - fileX);
            if (distance < minDistance && distance < 20) {
                minDistance = distance;
                closestFile = file;
            }
        });
        
        if (closestFile) {
            this.stateManager.setState({ selectedTime: closestFile.time });
        }
    }
}
```

#### Spectrogram Viewer (`js/components/SpectrogramViewer.js`)
```javascript
import { ApiService } from '../services/ApiService.js';

export class SpectrogramViewer {
    constructor(canvasId, stateManager) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.stateManager = stateManager;
        this.crosshairs = new CrosshairController(this.canvas);
        this.infoPanels = new InfoPanelController();
        this.init();
    }
    
    init() {
        // Mouse tracking for crosshairs and coordinates
        this.canvas.addEventListener('mousemove', (e) => this.handleMouseMove(e));
        this.canvas.addEventListener('mouseleave', () => this.handleMouseLeave());
        
        // Listen for state changes
        this.stateManager.addEventListener('statechange', (e) => {
            const { newState, oldState } = e.detail;
            
            // Reload spectrogram if date, time, colormap, or gamma changed
            if (newState.selectedDate && newState.selectedTime &&
                (newState.selectedDate !== oldState.selectedDate ||
                 newState.selectedTime !== oldState.selectedTime ||
                 newState.colormap !== oldState.colormap ||
                 newState.gamma !== oldState.gamma)) {
                this.loadSpectrogram();
                this.loadWeatherData();
            }
        });
    }
    
    handleMouseMove(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        
        // Update crosshairs
        this.crosshairs.updatePosition(x, y);
        
        // Calculate and display coordinates
        const coords = this.calculateCoordinates(x, y);
        this.infoPanels.updateCoordinates(coords);
    }
    
    handleMouseLeave() {
        this.crosshairs.hide();
        this.infoPanels.clearCoordinates();
    }
    
    calculateCoordinates(x, y) {
        // Convert canvas coordinates to time and frequency
        const state = this.stateManager.getState();
        const currentFile = state.dayFiles.find(f => f.time === state.selectedTime);
        const duration = currentFile ? currentFile.duration_seconds : 900; // fallback to 15 min
        
        const timeOffset = (x / this.canvas.width) * duration;
        const frequency = this.pixelToFrequency(this.canvas.height - y);
        
        return {
            pixelX: Math.round(x),
            pixelY: Math.round(y),
            timeOffset,
            frequency
        };
    }
    
    pixelToFrequency(yPixel) {
        // Basic linear frequency mapping - can be enhanced with mel scale later
        const sampleRate = 48000; // AudioMoth standard
        const nyquist = sampleRate / 2;
        return Math.round((yPixel / this.canvas.height) * nyquist);
    }
    
    async loadSpectrogram() {
        const state = this.stateManager.getState();
        if (!state.selectedDate || !state.selectedTime) return;
        
        try {
            const blob = await ApiService.getSpectrogram(
                state.selectedDate,
                state.selectedTime,
                state.colormap,
                state.gamma
            );
            
            const img = new Image();
            img.onload = () => {
                this.canvas.width = img.width;
                this.canvas.height = img.height;
                this.ctx.drawImage(img, 0, 0);
                URL.revokeObjectURL(img.src);
            };
            img.src = URL.createObjectURL(blob);
            
        } catch (error) {
            console.error('Failed to load spectrogram:', error);
        }
    }
    
    async loadWeatherData() {
        const state = this.stateManager.getState();
        if (!state.selectedDate || !state.selectedTime) return;
        
        try {
            const weatherData = await ApiService.getWeatherData(
                state.selectedDate,
                state.selectedTime
            );
            this.infoPanels.updateWeather(weatherData);
        } catch (error) {
            console.warn('Weather data not available:', error);
            this.infoPanels.clearWeather();
        }
    }
}

// Crosshair management component
class CrosshairController {
    constructor(canvas) {
        this.canvas = canvas;
        this.verticalLine = document.getElementById('crosshair-vertical');
        this.horizontalLine = document.getElementById('crosshair-horizontal');
    }
    
    updatePosition(x, y) {
        this.verticalLine.style.left = x + 'px';
        this.verticalLine.style.display = 'block';
        
        this.horizontalLine.style.top = y + 'px';
        this.horizontalLine.style.display = 'block';
    }
    
    hide() {
        this.verticalLine.style.display = 'none';
        this.horizontalLine.style.display = 'none';
    }
}

// Info panels management component
class InfoPanelController {
    constructor() {
        this.pixelCoords = document.getElementById('pixel-coords');
        this.timeCoords = document.getElementById('time-coords');
        this.freqCoords = document.getElementById('freq-coords');
        this.temperature = document.getElementById('temperature');
        this.humidity = document.getElementById('humidity');
        this.windSpeed = document.getElementById('wind-speed');
        this.precipitation = document.getElementById('precipitation');
    }
    
    updateCoordinates({ pixelX, pixelY, timeOffset, frequency }) {
        this.pixelCoords.textContent = `x:${pixelX.toString().padStart(4, '0')} y:${pixelY.toString().padStart(4, '0')}`;
        this.timeCoords.textContent = `Time: ${this.formatTime(timeOffset)}`;
        this.freqCoords.textContent = `Freq: ${frequency.toString().padStart(4, '0')} Hz`;
    }
    
    clearCoordinates() {
        this.pixelCoords.textContent = 'x:---- y:----';
        this.timeCoords.textContent = 'Time: --:--:--';
        this.freqCoords.textContent = 'Freq: ---- Hz';
    }
    
    updateWeather({ temperature, humidity, windSpeed, precipitation }) {
        this.temperature.textContent = temperature !== null ? `Temp: ${temperature}°C` : 'Temp: --°C';
        this.humidity.textContent = humidity !== null ? `Humidity: ${humidity}%` : 'Humidity: --%';
        this.windSpeed.textContent = windSpeed !== null ? `Wind: ${windSpeed} km/h` : 'Wind: -- km/h';
        this.precipitation.textContent = precipitation !== null ? `Rain: ${precipitation} mm` : 'Rain: -- mm';
    }
    
    clearWeather() {
        this.temperature.textContent = 'Temp: --°C';
        this.humidity.textContent = 'Humidity: --%';
        this.windSpeed.textContent = 'Wind: -- km/h';
        this.precipitation.textContent = 'Rain: -- mm';
    }
    
    formatTime(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
}
```

## Data Flow

1. **App Initialization**: Load available dates from API
2. **Date Selection**: User picks date → Load files for that date → Render timeline
3. **Time Selection**: User clicks timeline → Load spectrogram and audio
4. **Control Changes**: Colormap/gamma changes → Reload spectrogram with new parameters

## Key Requirements

### Essential UI Features  
- ✅ **Alpha-blended crosshairs** - Semi-transparent vertical/horizontal lines that follow cursor
- ✅ **Real-time coordinate display** - Show pixel coordinates, time offset, and frequency under cursor  
- ✅ **Weather data panels** - Display temperature, humidity, wind, precipitation for selected recording
- ✅ **Simple timeline** - Horizontal line showing files for the day, no zoom/pan needed
- ✅ **Single date picker** with easepick, constrained to available dates
- ✅ **Colormap support** - Multiple colormap options with real-time switching
- ✅ **Gamma adjustment** - Real-time gamma correction with slider
- ✅ **Audio playback** - Click-to-play with visual cursor tracking

### CSS Requirements for Key Features
```css
/* Alpha-blended crosshairs */
.crosshair-vertical, .crosshair-horizontal {
    position: absolute;
    background: rgba(255, 255, 255, 0.7); /* 70% opacity white */
    pointer-events: none;
    z-index: 10;
}

.crosshair-vertical {
    width: 1px;
    height: 100%;
    top: 0;
}

.crosshair-horizontal {
    height: 1px;
    width: 100%;
    left: 0;
}

/* Info panels styling */
.info-panels {
    display: flex;
    flex-direction: column;
    gap: 10px;
    min-width: 150px;
}

.coordinates-panel {
    background: #f8f9fa;
    border: 1px solid #ddd;
    border-radius: 4px;
    padding: 10px;
    font-family: monospace;
    font-size: 12px;
}

.weather-panel {
    background: #e8f4fd;
    border: 1px solid #bee5eb;
    border-radius: 4px;
    padding: 10px;
    font-family: monospace;
    font-size: 12px;
}
```

### Backend
- ✅ **No business logic in routes** - Routes only handle HTTP, delegate to services
- ✅ **Clean error handling** - Consistent error responses
- ✅ **Input validation** - Validate all parameters
- ✅ **Caching** - Cache expensive operations like colormap generation

### Frontend  
- ✅ **No SQL or backend logic** - Frontend only handles UI and API calls
- ✅ **Component isolation** - Each component manages only its own state
- ✅ **Proper error handling** - User-friendly error messages
- ✅ **Responsive design** - Works on different screen sizes

### Features
- ✅ **Single date picker** with easepick, constrained to available dates
- ✅ **Simple timeline** - Horizontal line showing files for the day, no zoom/pan
- ✅ **Colormap support** - Multiple colormap options
- ✅ **Gamma adjustment** - Real-time gamma correction
- ✅ **Audio playback** - Click-to-play with visual cursor
- ✅ **Spectrogram display** - Canvas-based with coordinate tracking

## Development Notes

- Use **ES6 modules** for clean imports/exports
- Implement **proper error boundaries** 
- Add **loading states** for better UX
- Use **semantic HTML** and **accessible design**
- Keep **components small** and **single-purpose**
- **No global variables** except the main app instance

## ⚠️ CRITICAL: Things to Avoid (Anti-patterns from previous codebase)

### Backend Anti-patterns
❌ **No SQL in route handlers**
```python
# DON'T DO THIS:
@app.route('/api/files')
def api_files():
    cursor.execute("SELECT * FROM audio_files WHERE date = ?", (date,))
```

❌ **No heavy imports in routes**
```python
# DON'T DO THIS:
@app.route('/api/colormap')
def colormap():
    import matplotlib.pyplot as plt  # Heavy import on every request
```

❌ **No mixed responsibilities in single functions**
- Don't put database queries, file operations, and HTTP handling in one function
- Don't generate HTML in Python code
- Don't put business logic in route handlers

❌ **No unsafe file operations**
```python
# DON'T DO THIS:
return send_file(str(image_file), mimetype='image/png')  # No validation
temp_file = tempfile.NamedTemporaryFile(delete=False)    # Manual cleanup
```

❌ **No inconsistent error handling**
- Don't mix error response formats
- Don't let exceptions bubble up to users
- Don't ignore error cases

### Frontend Anti-patterns
❌ **No monolithic files**
- Don't put 1000+ lines in one HTML file
- Don't mix CSS, JavaScript, and HTML in one file
- Don't create mega-classes with 200+ lines

❌ **No global state soup**
```javascript
// DON'T DO THIS:
let colormapCache = {};
let melScaleData = null;
let currentPlayer = null;
let currentSelectedTime = null;
let availableTimes = {};
let lastSelectedTime = null;
let lastColormap = 'viridis';
let audioPlayer = null;
let customTimeline = null;
```

❌ **No complex manual DOM manipulation**
```javascript
// DON'T DO THIS:
document.getElementById('pixelCoords').textContent = `x:${x} y:${y}`;
document.getElementById('timeCoords').textContent = `Time: ${timeString}`;
document.getElementById('freqCoords').textContent = `Freq: ${frequency} Hz`;
// Repeated everywhere with no abstraction
```

❌ **No mixed async/sync patterns**
```javascript
// DON'T DO THIS:
function loadSpectrogram() {
    fetch('/api/spectrogram').then(response => {
        // Mix of promises and callbacks
        img.onload = function() {
            // Nested callbacks inside promises
        }
    });
}
```

❌ **No complex event handler chains**
```javascript
// DON'T DO THIS:
canvas.addEventListener('click', (e) => {
    // 50+ lines of logic
    // Multiple responsibilities
    // Direct DOM manipulation
    // State mutations
});
```

### General Anti-patterns
❌ **No magic numbers and strings**
```javascript
// DON'T DO THIS:
canvas.width = 1000;  // Magic number
timeSlot = '00:00';   // Magic string
```

❌ **No inconsistent naming**
```javascript
// DON'T DO THIS:
let currentSelectedTime = null;
let lastSelectedTime = null;
let selectedTime = null;
// Three different names for similar concepts
```

❌ **No nested ternary operators**
```javascript
// DON'T DO THIS:
const value = condition1 ? (condition2 ? value1 : value2) : (condition3 ? value3 : value4);
```

❌ **No function parameter overloading**
```python
# DON'T DO THIS:
def process_data(date=None, time=None, files=None, data=None):
    # Function that does completely different things based on parameters
```

❌ **No error swallowing**
```javascript
// DON'T DO THIS:
try {
    riskyOperation();
} catch (e) {
    // Silent failure
}
```

### Specific Code Smells to Avoid
❌ **Functions doing multiple things**
- `loadSpectrogram()` that also handles audio, weather, and file info
- Classes with 10+ public methods
- Route handlers that do database operations

❌ **Tight coupling**
- Components that directly reference other components' internals
- Global state that multiple components modify directly
- Hard-coded dependencies

❌ **Poor error boundaries**
- Errors that cascade across unrelated components
- No user-friendly error messages
- Inconsistent error handling patterns

❌ **Performance anti-patterns**
- Loading large libraries on every request
- No caching for expensive operations
- Redundant API calls
- Heavy DOM manipulation in loops

### Memory Leaks to Avoid
❌ **Event listener leaks**
```javascript
// DON'T DO THIS:
function setupComponent() {
    canvas.addEventListener('click', handler);
    // Never removed, causes memory leaks
}
```

❌ **Audio object leaks**
```javascript
// DON'T DO THIS:
currentPlayer = new Howl({...});
// Old player never disposed, memory grows
```

## ✅ DO INSTEAD

### What Worked Well in Original Code (Keep These)
✅ **Canvas-based spectrogram rendering** - Performant, flexible  
✅ **Click-to-play audio functionality** - Intuitive user interaction  
✅ **Visual playback cursor** - Good user feedback  
✅ **Coordinate tracking on mouse move** - Useful for analysis  
✅ **Alpha-blended crosshair lines** - Vertical/horizontal cursor guides with transparency  
✅ **Info panels** - Real-time cursor coordinates, time, and frequency display  
✅ **Weather data integration** - Contextual environmental data for each recording  
✅ **Colormap switching** - Good feature, just needs cleaner implementation  
✅ **Gamma adjustment** - Valuable image enhancement tool  
✅ **Easepick date constraints** - Elegant solution for available dates  

### Use These Patterns
✅ **Service layer pattern** - Separate business logic from routes  
✅ **Component composition** - Small, focused components  
✅ **Event-driven architecture** - Loose coupling via events  
✅ **Proper error boundaries** - Consistent error handling  
✅ **Resource cleanup** - Dispose of objects properly  
✅ **Input validation** - Validate at API boundaries  
✅ **Caching** - Cache expensive operations  
✅ **Configuration** - External config, no hard-coded values