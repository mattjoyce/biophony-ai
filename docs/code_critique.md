# AudioMoth Code Critique & Refactoring Recommendations

## 🚨 Critical Issues

### 1. **Monolithic Architecture**
- **1,000+ line HTML file** with embedded CSS and JavaScript
- **Single massive Python file** handling 20+ different concerns
- No separation between presentation, business logic, and data layers

### 2. **Poor Separation of Concerns**
```python
# Backend doing frontend work
@app.route('/api/colormap/<colormap_name>')
def api_colormap(colormap_name):
    import matplotlib.pyplot as plt  # Heavy import in route handler
    # Complex colormap generation should be separate service
```

```javascript
// Frontend doing backend-style data processing
function processCircles() {
    // 50+ lines of complex data transformation
    // Should be handled by backend API
}
```

### 3. **Security Vulnerabilities**
```python
# Dangerous file operations
temp_file = tempfile.NamedTemporaryFile(
    mode='w+b',
    suffix=f'_{file_uuid}.txt',
    delete=False  # Manual cleanup required
)
```

```python
# Direct file serving without proper validation
return send_file(str(image_file), mimetype='image/png')
```

### 4. **Performance Issues**
- **Heavy imports in request handlers** (matplotlib, numpy)
- **Large HTML payload** (~1000 lines sent to every client)
- **Inefficient canvas operations** (multiple imageData manipulations)
- **No caching** for expensive operations like colormap generation

### 5. **Complex State Management**
```javascript
// Global state nightmare
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

## 🔧 Specific Problems

### Backend Issues

#### Raw SQL Everywhere
```python
cursor.execute("""
    SELECT filepath, filename FROM audio_files 
    WHERE DATE(recording_datetime) = ? 
    AND TIME(recording_datetime) = ?
    LIMIT 1
""", (date, f"{time}:00"))
```
**Problem**: No ORM, no query builder, SQL scattered throughout route handlers

#### Fat Route Handlers
```python
@app.route('/api/weather')
def api_weather():
    # 30+ lines of complex logic
    # Should be in service layer
```

#### Mixed Responsibilities
```python
# Same file handles:
# - Web routes
# - Database operations  
# - File operations
# - Image processing
# - Weather data
# - Audio processing
```

### Frontend Issues

#### Massive JavaScript Classes
```javascript
class SpectrogramAudioPlayer {
    // 200+ lines
    // Handles audio, UI, timing, events, error handling
}

class CustomTimeline {
    // 300+ lines  
    // Handles rendering, events, data processing, zoom, pan
}
```

#### Inconsistent Error Handling
```javascript
// Sometimes:
errorMessage.textContent = 'Error loading spectrogram';
errorMessage.style.display = 'block';

// Sometimes:
console.error('Audio playback error:', error);
this.showError('Failed to load audio file');

// Sometimes:
throw new Error(`HTTP ${response.status}: ${response.statusText}`);
```

#### Complex DOM Manipulation
```javascript
// Manual coordinate tracking
const x = Math.round(event.clientX - rect.left);
const y = Math.round(event.clientY - rect.top);
const yBottomLeft = canvas.height - y;
const frequency = getFrequencyFromPixel(yBottomLeft, canvas.height);
```

## 🏗️ Recommended Architecture

### 1. **Backend Restructure**

```
backend/
├── app.py                 # Flask app setup only
├── models/               # SQLAlchemy models
│   ├── audio_file.py
│   ├── weather_data.py
│   └── annotation.py
├── services/             # Business logic
│   ├── spectrogram_service.py
│   ├── audio_service.py
│   ├── weather_service.py
│   └── colormap_service.py
├── api/                  # Route handlers (thin)
│   ├── files_api.py
│   ├── weather_api.py
│   └── spectrogram_api.py
├── database/
│   └── connection.py
└── config/
    └── settings.py
```

### 2. **Frontend Restructure**

```
frontend/
├── index.html           # Minimal HTML structure
├── css/
│   ├── main.css
│   ├── timeline.css
│   └── spectrogram.css
├── js/
│   ├── main.js
│   ├── components/
│   │   ├── SpectrogramViewer.js
│   │   ├── AudioPlayer.js
│   │   ├── Timeline.js
│   │   └── WeatherPanel.js
│   ├── services/
│   │   ├── ApiService.js
│   │   └── StateManager.js
│   └── utils/
│       ├── coordinates.js
│       └── time.js
```

### 3. **Better Patterns**

#### Replace Raw SQL with ORM
```python
# Instead of:
cursor.execute("SELECT * FROM audio_files WHERE date = ?", (date,))

# Use:
audio_files = AudioFile.query.filter_by(date=date).all()
```

#### Service Layer Pattern
```python
class SpectrogramService:
    def get_spectrogram(self, date: str, time: str) -> SpectrogramData:
        # Business logic here
        
    def apply_colormap(self, image_data: bytes, colormap: str) -> bytes:
        # Colormap logic here
```

#### Component-Based Frontend
```javascript
class SpectrogramViewer extends EventTarget {
    constructor(container) {
        super();
        this.container = container;
        this.canvas = container.querySelector('canvas');
        this.state = new StateManager();
    }
    
    async loadSpectrogram(date, time) {
        try {
            const data = await ApiService.getSpectrogram(date, time);
            this.render(data);
            this.dispatchEvent(new CustomEvent('loaded', { detail: data }));
        } catch (error) {
            this.handleError(error);
        }
    }
}
```

### 4. **State Management**
```javascript
class StateManager extends EventTarget {
    constructor() {
        super();
        this.state = {
            currentDate: null,
            currentTime: null,
            selectedColormap: 'viridis',
            audioPlayer: null
        };
    }
    
    setState(updates) {
        const oldState = { ...this.state };
        this.state = { ...this.state, ...updates };
        this.dispatchEvent(new CustomEvent('statechange', { 
            detail: { oldState, newState: this.state } 
        }));
    }
}
```

## 🎯 Immediate Action Items

### 1. **Split the Files**
- Extract CSS to separate files
- Extract JavaScript modules
- Break Python file into logical modules

### 2. **Add Error Boundaries**
```javascript
class ErrorBoundary {
    static wrap(fn) {
        return async function(...args) {
            try {
                return await fn.apply(this, args);
            } catch (error) {
                ErrorHandler.handle(error);
            }
        };
    }
}
```

### 3. **Implement Caching**
```python
from functools import lru_cache

@lru_cache(maxsize=128)
def get_colormap(colormap_name: str) -> List[List[int]]:
    # Expensive colormap generation
```

### 4. **Add Input Validation**
```python
from pydantic import BaseModel

class SpectrogramRequest(BaseModel):
    date: str
    time: str
    colormap: str = 'viridis'
    
    @validator('date')
    def validate_date(cls, v):
        # Date validation logic
```

### 5. **Use Modern Frontend Tools**
Consider migrating to:
- **React/Vue** for component architecture
- **TypeScript** for type safety
- **Webpack/Vite** for bundling
- **CSS-in-JS** or **CSS modules** for styling

## 🚀 Benefits of Refactoring

1. **Maintainability**: Easier to find and fix bugs
2. **Testability**: Each component can be unit tested
3. **Performance**: Faster load times, better caching
4. **Security**: Proper input validation and sanitization
5. **Scalability**: New features easier to add
6. **Developer Experience**: Cleaner code, better debugging

## 💡 Quick Wins

Start with these low-risk improvements:
1. Extract CSS to separate file
2. Split JavaScript into modules
3. Add error handling middleware
4. Implement request validation
5. Add basic caching for expensive operations

The current code works but is a maintenance nightmare. A gradual refactoring approach would significantly improve code quality and developer productivity.