/**
 * Spectrogram Viewer Component
 * Handles spectrogram display with crosshairs, coordinate tracking, and colormap processing
 */

import { ApiService } from '../services/ApiService.js';

export class SpectrogramViewer {
    constructor(canvasId, stateManager) {
        this.canvas = document.getElementById(canvasId);
        this.stateManager = stateManager;
        this.ctx = null;
        this.originalImageData = null;
        this.melScaleData = null;
        this.currentGamma = 1.0;
        
        if (!this.canvas) {
            throw new Error(`Spectrogram canvas not found: ${canvasId}`);
        }
        
        this.crosshairs = new CrosshairController(this.canvas);
        this.infoPanels = new InfoPanelController();
        
        this.init();
        this.bindStateEvents();
    }
    
    init() {
        this.ctx = this.canvas.getContext('2d');
        
        // Mouse tracking for crosshairs and coordinates
        this.canvas.addEventListener('mousemove', (e) => this.handleMouseMove(e));
        this.canvas.addEventListener('mouseleave', () => this.handleMouseLeave());
        
        // Load mel scale data for frequency calculations
        this.loadMelScaleData();
    }
    
    bindStateEvents() {
        this.stateManager.addEventListener('statechange', (e) => {
            const { newState, oldState } = e.detail;
            
            // Handle colormap/gamma changes without full reload
            if (this.shouldReapplyColormap(newState, oldState)) {
                this.reapplyColormap(newState.colormap, newState.gamma);
            }
            // Full reload only for date/time changes
            else if (this.shouldReloadSpectrogram(newState, oldState)) {
                this.loadSpectrogram();
            }
        });
    }
    
    shouldReapplyColormap(newState, oldState) {
        return (
            this.originalImageData && // Only if we have existing image data
            newState.selectedDate === oldState.selectedDate &&
            newState.selectedTime === oldState.selectedTime &&
            newState.colormap !== oldState.colormap
            // Removed gamma from reload triggers - gamma is now handled directly
        );
    }
    
    shouldReloadSpectrogram(newState, oldState) {
        return (
            newState.selectedDate && newState.selectedTime &&
            (newState.selectedDate !== oldState.selectedDate ||
             newState.selectedTime !== oldState.selectedTime)
        );
    }
    
    async reapplyColormap(colormap, gamma) {
        if (!this.originalImageData) return;
        
        try {
            // Only handle colormap changes here - gamma is handled separately
            // For now, reload for colormap changes (future: implement client-side colormap)
            this.loadSpectrogram();
        } catch (error) {
            console.error('Failed to reapply colormap:', error);
        }
    }
    
    /**
     * Apply gamma adjustment directly to the canvas (real-time, no reload)
     * @param {number} gamma - Gamma value (0.1 to 3.0)
     */
    applyGammaAdjustment(gamma) {
        if (!this.originalImageData) {
            console.warn('No original image data available for gamma adjustment');
            return;
        }
        
        // Update current gamma tracking
        this.currentGamma = gamma;
        
        if (gamma === 1.0) {
            // If gamma is 1.0, just show original
            this.ctx.putImageData(this.originalImageData, 0, 0);
            return;
        }
        
        // Create gamma-adjusted image data
        const imageData = this.ctx.createImageData(this.originalImageData.width, this.originalImageData.height);
        const data = imageData.data;
        const originalData = this.originalImageData.data;
        
        const gammaCorrection = 1.0 / gamma;
        
        // Create gamma lookup table for performance (cache this if needed)
        const gammaTable = new Array(256);
        for (let i = 0; i < 256; i++) {
            gammaTable[i] = Math.pow(i / 255, gammaCorrection) * 255;
        }
        
        // Apply gamma to all pixels
        for (let i = 0; i < originalData.length; i += 4) {
            // Apply gamma to RGB channels (skip alpha)
            for (let c = 0; c < 3; c++) {
                const value = originalData[i + c];
                data[i + c] = Math.max(0, Math.min(255, Math.round(gammaTable[value])));
            }
            data[i + 3] = originalData[i + 3]; // Alpha channel unchanged
        }
        
        this.ctx.putImageData(imageData, 0, 0);
    }
    
    /**
     * Get the current gamma value from the canvas (for external access)
     */
    getCurrentGamma() {
        return this.currentGamma || 1.0;
    }
    
    async loadMelScaleData() {
        try {
            this.melScaleData = await ApiService.getMelScale();
        } catch (error) {
            console.warn('Failed to load mel scale data:', error);
            this.melScaleData = null;
        }
    }
    
    async loadSpectrogram() {
        const state = this.stateManager.getState();
        
        if (!state.selectedDate || !state.selectedTime) {
            this.clearCanvas();
            return;
        }
        
        try {
            this.stateManager.setLoading(true);
            
            // Load spectrogram image
            const blob = await ApiService.getSpectrogram(
                state.selectedDate,
                state.selectedTime,
                state.colormap,
                state.gamma
            );
            
            // Load and display image
            await this.displayImage(blob);
            
            // Load additional data
            this.loadFileInfo(state.selectedDate, state.selectedTime);
            this.loadWeatherData(state.selectedDate, state.selectedTime);
            
        } catch (error) {
            console.error('Failed to load spectrogram:', error);
            this.stateManager.setError(`Failed to load spectrogram: ${error.message}`);
        } finally {
            this.stateManager.setLoading(false);
        }
    }
    
    async displayImage(blob) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            
            img.onload = () => {
                try {
                    // Set canvas size to match image (revert to original behavior)
                    this.canvas.width = img.width;
                    this.canvas.height = img.height;
                    
                    // Draw image
                    this.ctx.drawImage(img, 0, 0);
                    
                    // Store original image data for coordinate calculations
                    this.originalImageData = this.ctx.getImageData(0, 0, img.width, img.height);
                    
                    // Clean up blob URL
                    URL.revokeObjectURL(img.src);
                    
                    resolve();
                } catch (error) {
                    reject(error);
                }
            };
            
            img.onerror = () => {
                URL.revokeObjectURL(img.src);
                reject(new Error('Failed to load image'));
            };
            
            img.src = URL.createObjectURL(blob);
        });
    }
    
    async loadFileInfo(date, time) {
        try {
            const fileInfo = await ApiService.getFileInfo(date, time);
            this.stateManager.setCurrentFile(fileInfo);
        } catch (error) {
            console.warn('Could not load file info:', error);
        }
    }
    
    async loadWeatherData(date, time) {
        try {
            const weatherData = await ApiService.getWeatherData(date, time);
            this.stateManager.setWeatherData(weatherData);
        } catch (error) {
            console.warn('Could not load weather data:', error);
            this.stateManager.setWeatherData(null);
        }
    }
    
    clearCanvas() {
        if (this.ctx) {
            this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        }
        this.originalImageData = null;
        this.infoPanels.clearCoordinates();
    }
    
    handleMouseMove(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        
        // Update crosshairs
        this.crosshairs.updatePosition(x, y);
        
        // Calculate and display coordinates
        if (this.canvas.width > 0 && this.canvas.height > 0) {
            const coords = this.calculateCoordinates(x, y);
            
            // Get RGB values at this time position if available
            const rgbStrip = this.getRGBStrip();
            if (rgbStrip) {
                const rgbValues = rgbStrip.getValuesAtTime(coords.timeOffset);
                coords.rgbValues = rgbValues;
            }
            
            this.infoPanels.updateCoordinates(coords);
        }
    }
    
    handleMouseLeave() {
        this.crosshairs.hide();
        this.infoPanels.clearCoordinates();
    }
    
    calculateCoordinates(x, y) {
        const state = this.stateManager.getState();

        // Get current file duration (default to 15 minutes for AudioMoth)
        const currentFile = state.currentFile;
        const duration = currentFile ? currentFile.duration_seconds : 900;

        // Calculate time offset using rendered canvas dimensions (accounts for CSS scaling)
        const rect = this.canvas.getBoundingClientRect();
        const normalizedX = x / rect.width;  // Percentage across canvas
        const normalizedY = y / rect.height; // Percentage down canvas

        // Calculate time offset within the recording
        const timeOffset = normalizedX * duration;

        // Calculate frequency using canvas intrinsic height for pixel mapping
        const intrinsicY = normalizedY * this.canvas.height;
        const frequency = this.pixelToFrequency(this.canvas.height - intrinsicY);

        return {
            pixelX: Math.round(x),
            pixelY: Math.round(y),
            timeOffset,
            frequency
        };
    }
    
    pixelToFrequency(yPixel) {
        if (this.melScaleData && this.melScaleData.scale_data) {
            // Use mel scale mapping
            const scaleIndex = Math.round((yPixel / this.canvas.height) * (this.melScaleData.scale_data.length - 1));
            const clampedIndex = Math.max(0, Math.min(scaleIndex, this.melScaleData.scale_data.length - 1));
            return Math.round(this.melScaleData.scale_data[clampedIndex].frequency_hz);
        } else {
            // Fallback to linear frequency mapping
            const sampleRate = 48000; // AudioMoth standard
            const nyquist = sampleRate / 2;
            return Math.round((yPixel / this.canvas.height) * nyquist);
        }
    }
    
    /**
     * Get canvas for external use (e.g., by AudioPlayer for cursor positioning)
     * @returns {HTMLCanvasElement} Canvas element
     */
    getCanvas() {
        return this.canvas;
    }
    
    /**
     * Get RGB strip instance from the main app
     * @returns {RGBStrip|null} RGB strip instance or null if not available
     */
    getRGBStrip() {
        // Access the RGB strip through the global app instance
        return window.audioMothApp?.rgbStrip || null;
    }
    
    /**
     * Destroy the spectrogram viewer
     */
    destroy() {
        this.crosshairs.destroy();
        this.clearCanvas();
    }
}

/**
 * Crosshair Controller
 * Manages the crosshair lines that follow the mouse cursor
 */
class CrosshairController {
    constructor(canvas) {
        this.canvas = canvas;
        this.verticalLine = document.getElementById('crosshair-vertical');
        this.horizontalLine = document.getElementById('crosshair-horizontal');
        
        if (!this.verticalLine || !this.horizontalLine) {
            console.warn('Crosshair elements not found');
        }
    }
    
    updatePosition(x, y) {
        if (this.verticalLine) {
            this.verticalLine.style.left = x + 'px';
            this.verticalLine.style.display = 'block';
        }
        
        if (this.horizontalLine) {
            this.horizontalLine.style.top = y + 'px';
            this.horizontalLine.style.display = 'block';
        }
    }
    
    hide() {
        if (this.verticalLine) {
            this.verticalLine.style.display = 'none';
        }
        if (this.horizontalLine) {
            this.horizontalLine.style.display = 'none';
        }
    }
    
    destroy() {
        this.hide();
    }
}

/**
 * Info Panel Controller
 * Manages the display of coordinate and weather information
 */
class InfoPanelController {
    constructor() {
        this.pixelCoords = document.getElementById('pixel-coords');
        this.timeCoords = document.getElementById('time-coords');
        this.freqCoords = document.getElementById('freq-coords');
        this.rgbCoords = document.getElementById('rgb-coords');
        this.temperature = document.getElementById('temperature');
        this.humidity = document.getElementById('humidity');
        this.windSpeed = document.getElementById('wind-speed');
        this.precipitation = document.getElementById('precipitation');
    }
    
    updateCoordinates({ pixelX, pixelY, timeOffset, frequency, rgbValues }) {
        if (this.pixelCoords) {
            this.pixelCoords.textContent = `x:${pixelX.toString().padStart(4, '0')} y:${pixelY.toString().padStart(4, '0')}`;
        }
        
        if (this.timeCoords) {
            this.timeCoords.textContent = `Time: ${this.formatTime(timeOffset)}`;
        }
        
        if (this.freqCoords) {
            this.freqCoords.textContent = `Freq: ${frequency.toString().padStart(4, '0')} Hz`;
        }
        
        if (this.rgbCoords) {
            if (rgbValues) {
                const { rgb, raw_values } = rgbValues;
                const rgbStr = rgb ? `RGB: ${rgb[0].toString().padStart(3, '0')} ${rgb[1].toString().padStart(3, '0')} ${rgb[2].toString().padStart(3, '0')}` : 'RGB: --- --- ---';
                this.rgbCoords.textContent = rgbStr;
                
                // Add raw values as tooltip if available
                if (raw_values) {
                    const tooltipText = [
                        raw_values.red ? `R: ${raw_values.red.toFixed(3)}` : '',
                        raw_values.green ? `G: ${raw_values.green.toFixed(3)}` : '',
                        raw_values.blue ? `B: ${raw_values.blue.toFixed(3)}` : ''
                    ].filter(v => v).join(' | ');
                    
                    this.rgbCoords.title = tooltipText;
                }
            } else {
                this.rgbCoords.textContent = 'RGB: --- --- ---';
                this.rgbCoords.title = '';
            }
        }
    }
    
    clearCoordinates() {
        if (this.pixelCoords) this.pixelCoords.textContent = 'x:---- y:----';
        if (this.timeCoords) this.timeCoords.textContent = 'Time: --:--:--';
        if (this.freqCoords) this.freqCoords.textContent = 'Freq: ---- Hz';
        if (this.rgbCoords) {
            this.rgbCoords.textContent = 'RGB: --- --- ---';
            this.rgbCoords.title = '';
        }
    }
    
    updateWeather(weatherData) {
        if (!weatherData) {
            this.clearWeather();
            return;
        }
        
        if (this.temperature) {
            this.temperature.textContent = weatherData.temperature !== null ? 
                `Temp: ${weatherData.temperature}°C` : 'Temp: --°C';
        }
        
        if (this.humidity) {
            this.humidity.textContent = weatherData.humidity !== null ? 
                `Humidity: ${weatherData.humidity}%` : 'Humidity: --%';
        }
        
        if (this.windSpeed) {
            this.windSpeed.textContent = weatherData.wind_speed !== null ? 
                `Wind: ${weatherData.wind_speed} km/h` : 'Wind: -- km/h';
        }
        
        if (this.precipitation) {
            this.precipitation.textContent = weatherData.precipitation !== null ? 
                `Rain: ${weatherData.precipitation} mm` : 'Rain: -- mm';
        }
    }
    
    clearWeather() {
        if (this.temperature) this.temperature.textContent = 'Temp: --°C';
        if (this.humidity) this.humidity.textContent = 'Humidity: --%';
        if (this.windSpeed) this.windSpeed.textContent = 'Wind: -- km/h';
        if (this.precipitation) this.precipitation.textContent = 'Rain: -- mm';
    }
    
    formatTime(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
}