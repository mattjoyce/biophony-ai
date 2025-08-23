/**
 * Main Application Entry Point
 * AudioMoth Spectrogram Viewer - Clean Architecture Implementation
 */

import { StateManager } from './services/StateManager.js';
import { ApiService } from './services/ApiService.js';
import { DatePicker } from './components/DatePicker.js';
import { Timeline } from './components/Timeline.js';
import { SpectrogramViewer } from './components/SpectrogramViewer.js';
import { AudioPlayer } from './components/AudioPlayer.js';
import { Controls } from './components/Controls.js';
import { RGBPicker } from './components/RGBPicker.js';
import { RGBStrip } from './components/RGBStrip.js';
import { Navigation } from './components/Navigation.js';
import { POIStrips } from './components/POIStrips.js';

class AudioMothApp {
    constructor() {
        this.stateManager = null;
        this.datePicker = null;
        this.timeline = null;
        this.spectrogramViewer = null;
        this.audioPlayer = null;
        this.controls = null;
        this.rgbPicker = null;
        this.rgbStrip = null;
        this.navigation = null;
        this.poiStrips = null;
        
        this.init();
    }
    
    async init() {
        try {
            console.log('Initializing AudioMoth Spectrogram Viewer...');
            
            // Initialize state manager
            this.stateManager = new StateManager();
            
            // Initialize components
            await this.initializeComponents();
            
            // Setup error handling
            this.setupErrorHandling();
            
            // Load saved preferences
            this.loadSavedPreferences();
            
            // Setup URL parameters handling (deeplinks)
            this.handleUrlParameters();
            
            console.log('AudioMoth Spectrogram Viewer initialized successfully');
            
        } catch (error) {
            console.error('Failed to initialize application:', error);
            this.showError('Failed to initialize application. Please refresh the page.');
        }
    }
    
    async initializeComponents() {
        // Initialize date picker
        this.datePicker = new DatePicker('date-picker', this.stateManager);
        
        // Initialize timeline
        this.timeline = new Timeline('timeline-container', this.stateManager);
        
        // Initialize spectrogram viewer
        this.spectrogramViewer = new SpectrogramViewer('spectrogram-canvas', this.stateManager);
        
        // Initialize audio player
        this.audioPlayer = new AudioPlayer(this.stateManager, this.spectrogramViewer);
        
        // Initialize controls (pass spectrogramViewer for direct gamma manipulation)
        this.controls = new Controls(this.stateManager, this.spectrogramViewer);
        
        // Initialize RGB components
        this.rgbPicker = new RGBPicker('rgb-picker-container', this.stateManager);
        this.rgbStrip = new RGBStrip('rgb-strip-container', this.stateManager);
        
        // Initialize navigation
        this.navigation = new Navigation('navigation-container', this.stateManager, this);
        
        // Initialize POI strips
        this.poiStrips = new POIStrips('poi-strips-container', this.stateManager);
        
        // Setup component interactions
        this.setupComponentInteractions();
    }
    
    setupComponentInteractions() {
        // Listen for state changes to coordinate components
        this.stateManager.addEventListener('statechange', (e) => {
            const { newState, oldState, changes } = e.detail;
            
            // Log state changes for debugging
            if (Object.keys(changes).length > 0) {
                console.log('State changed:', changes);
            }
            
            // Handle errors
            if (newState.error && newState.error !== oldState.error) {
                this.showError(newState.error);
            }
            
            // Handle loading states
            if (newState.isLoading !== oldState.isLoading) {
                this.setLoadingState(newState.isLoading);
            }
        });
    }
    
    setupErrorHandling() {
        // Global error handler
        window.addEventListener('error', (e) => {
            console.error('Global error:', e.error);
            this.showError('An unexpected error occurred.');
        });
        
        // Unhandled promise rejection handler
        window.addEventListener('unhandledrejection', (e) => {
            console.error('Unhandled promise rejection:', e.reason);
            this.showError('An unexpected error occurred.');
            e.preventDefault();
        });
    }
    
    loadSavedPreferences() {
        if (this.controls) {
            this.controls.loadSavedPreferences();
        }
    }
    
    handleUrlParameters() {
        const urlParams = new URLSearchParams(window.location.search);
        
        const paramDate = urlParams.get('date');
        const paramFile = urlParams.get('file');
        const paramFileId = urlParams.get('file_id');
        const paramTime = urlParams.get('time');
        const paramColormap = urlParams.get('colormap');
        const paramGamma = urlParams.get('gamma');
        
        // Handle file_id parameter first (preferred method)
        if (paramFileId) {
            this.handleFileIdParameter(paramFileId, paramTime);
            return;
        }
        
        // Handle file parameter (fallback for legacy links)
        if (paramFile) {
            this.handleFileParameter(paramFile, paramTime);
            return; // Let file handling set other parameters
        }
        
        // Set parameters if provided (when no file parameter)
        if (paramDate && this.datePicker) {
            this.datePicker.setDate(paramDate);
        }
        
        if (paramTime) {
            // Wait for date to be processed, then set time
            setTimeout(() => {
                this.stateManager.selectTime(paramTime);
            }, 500);
        }
        
        if (paramColormap) {
            this.stateManager.setColormap(paramColormap);
        }
        
        if (paramGamma) {
            const gamma = parseFloat(paramGamma);
            if (!isNaN(gamma) && gamma > 0 && gamma <= 10) {
                this.stateManager.setGamma(gamma);
            }
        }
    }
    
    async handleFileParameter(filename, time) {
        try {
            // Find the file in the database to get its date
            const response = await fetch(`/api/files/search?filename=${encodeURIComponent(filename)}`);
            if (!response.ok) {
                throw new Error(`File not found: ${filename}`);
            }
            
            const result = await response.json();
            if (!result.success || !result.data || !result.data.recording_datetime) {
                throw new Error(`Invalid file data for: ${filename}`);
            }
            
            const fileData = result.data;
            // Extract date from recording_datetime (format: 2025-06-20T00:00:00)
            const dateStr = fileData.recording_datetime.split('T')[0];
            
            // Set the date first
            if (this.datePicker) {
                this.datePicker.setDate(dateStr);
            }
            
            // Wait for date processing, then navigate to the file and set time
            setTimeout(() => {
                // Navigate to the specific file
                this.navigation.navigateToFile(filename);
                
                // Set time if provided
                if (time) {
                    setTimeout(() => {
                        this.stateManager.selectTime(parseInt(time));
                    }, 500);
                }
            }, 750);
            
        } catch (error) {
            console.error('Error handling file parameter:', error);
            this.showError(`Could not navigate to file: ${filename}`);
        }
    }
    
    async handleFileIdParameter(fileId, time) {
        try {
            // Get file info by ID
            const response = await fetch(`/api/files/id/${fileId}`);
            if (!response.ok) {
                throw new Error(`File not found with ID: ${fileId}`);
            }
            
            const result = await response.json();
            if (!result.success || !result.data || !result.data.recording_datetime) {
                throw new Error(`Invalid file data for ID: ${fileId}`);
            }
            
            const fileData = result.data;
            // Extract date from recording_datetime (format: 2025-06-20T00:00:00)
            const dateStr = fileData.recording_datetime.split('T')[0];
            
            // Set the date first
            if (this.datePicker) {
                this.datePicker.setDate(dateStr);
            }
            
            // Wait for date processing, then navigate to the file and set time
            setTimeout(() => {
                // Navigate to the specific file using filename
                this.navigation.navigateToFile({
                    filename: fileData.filename,
                    date: fileData.date,
                    time: fileData.time
                });
                
                // Set time if provided (time is in seconds offset from start of file)
                if (time) {
                    setTimeout(() => {
                        // For POI deep linking, navigate to the file's base time
                        // The spectrogram and indices APIs need the exact file time
                        console.log(`POI navigation: Loading file ${fileData.filename} at time ${fileData.time} with ${time}s offset`);
                        this.stateManager.selectTime(fileData.time);
                        
                        // TODO: In the future, we could add timeline cursor positioning
                        // to show the exact POI location within the 15-minute file
                    }, 500);
                }
            }, 750);
            
        } catch (error) {
            console.error('Error handling file_id parameter:', error);
            this.showError(`Could not navigate to file ID: ${fileId}`);
        }
    }
    
    showError(message) {
        // Create or update error display
        let errorElement = document.getElementById('error-display');
        
        if (!errorElement) {
            errorElement = document.createElement('div');
            errorElement.id = 'error-display';
            errorElement.className = 'error';
            errorElement.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
                border-radius: 4px;
                padding: 15px 20px;
                max-width: 400px;
                z-index: 1000;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            `;
            document.body.appendChild(errorElement);
        }
        
        errorElement.textContent = message;
        errorElement.style.display = 'block';
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            if (errorElement.parentNode) {
                errorElement.style.display = 'none';
                this.stateManager.clearError();
            }
        }, 5000);
        
        // Click to dismiss
        errorElement.addEventListener('click', () => {
            errorElement.style.display = 'none';
            this.stateManager.clearError();
        });
    }
    
    setLoadingState(isLoading) {
        const app = document.querySelector('.app');
        if (app) {
            if (isLoading) {
                app.classList.add('loading');
            } else {
                app.classList.remove('loading');
            }
        }
    }
    
    /**
     * Generate deeplink URL for current state
     * @returns {string} Shareable URL
     */
    generateDeeplink() {
        const state = this.stateManager.getState();
        const params = new URLSearchParams();
        
        if (state.selectedDate) params.set('date', state.selectedDate);
        if (state.selectedTime) params.set('time', state.selectedTime);
        if (state.colormap !== 'viridis') params.set('colormap', state.colormap);
        if (state.gamma !== 1.0) params.set('gamma', state.gamma.toString());
        
        const url = new URL(window.location);
        url.search = params.toString();
        
        return url.toString();
    }
    
    /**
     * Navigate to next file chronologically
     */
    async navigateNext() {
        const state = this.stateManager.getState();
        
        if (!state.selectedDate || !state.selectedTime) {
            console.warn('No current selection for navigation');
            return;
        }
        
        try {
            const nextFile = await ApiService.getNavigationFile(
                state.selectedDate, 
                state.selectedTime, 
                'next'
            );
            
            // Update date if different
            if (nextFile.date !== state.selectedDate) {
                this.datePicker.setDate(nextFile.date);
                // Wait for date change to process
                setTimeout(() => {
                    this.stateManager.selectTime(nextFile.time);
                }, 200);
            } else {
                this.stateManager.selectTime(nextFile.time);
            }
            
        } catch (error) {
            console.warn('No next file available:', error);
        }
    }
    
    /**
     * Navigate to previous file chronologically
     */
    async navigatePrev() {
        const state = this.stateManager.getState();
        
        if (!state.selectedDate || !state.selectedTime) {
            console.warn('No current selection for navigation');
            return;
        }
        
        try {
            const prevFile = await ApiService.getNavigationFile(
                state.selectedDate, 
                state.selectedTime, 
                'prev'
            );
            
            // Update date if different
            if (prevFile.date !== state.selectedDate) {
                this.datePicker.setDate(prevFile.date);
                // Wait for date change to process
                setTimeout(() => {
                    this.stateManager.selectTime(prevFile.time);
                }, 200);
            } else {
                this.stateManager.selectTime(prevFile.time);
            }
            
        } catch (error) {
            console.warn('No previous file available:', error);
        }
    }
    
    /**
     * Cleanup and destroy the application
     */
    destroy() {
        // Cleanup components
        if (this.audioPlayer) this.audioPlayer.destroy();
        if (this.spectrogramViewer) this.spectrogramViewer.destroy();
        if (this.timeline) this.timeline.destroy();
        if (this.datePicker) this.datePicker.destroy();
        if (this.controls) this.controls.destroy();
        if (this.rgbPicker) this.rgbPicker.destroy();
        if (this.rgbStrip) this.rgbStrip.destroy();
        if (this.navigation) this.navigation.destroy();
        if (this.poiStrips) this.poiStrips.destroy();
        
        // Remove error display
        const errorElement = document.getElementById('error-display');
        if (errorElement && errorElement.parentNode) {
            errorElement.parentNode.removeChild(errorElement);
        }
        
        console.log('AudioMoth Spectrogram Viewer destroyed');
    }
}

// Initialize application when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.audioMothApp = new AudioMothApp();
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (window.audioMothApp) {
        window.audioMothApp.destroy();
    }
});