/**
 * Audio Player Component using Howler.js
 * Handles audio playback with visual cursor tracking on spectrogram
 */

import { ApiService } from '../services/ApiService.js';

export class AudioPlayer {
    constructor(stateManager, spectrogramViewer) {
        this.stateManager = stateManager;
        this.spectrogramViewer = spectrogramViewer;
        this.audio = null;
        this.animationId = null;
        this.currentFilename = null;
        
        // Get control elements
        this.playPauseBtn = document.getElementById('play-pause');
        this.stopBtn = document.getElementById('stop');
        this.timeDisplay = document.getElementById('time-display');
        this.cursor = document.getElementById('playback-cursor');
        
        this.init();
        this.bindStateEvents();
    }
    
    init() {
        // Setup control event listeners
        if (this.playPauseBtn) {
            this.playPauseBtn.addEventListener('click', () => this.togglePlayPause());
        }
        
        if (this.stopBtn) {
            this.stopBtn.addEventListener('click', () => this.stop());
        }
        
        // Setup spectrogram click-to-play
        if (this.spectrogramViewer) {
            const canvas = this.spectrogramViewer.getCanvas();
            if (canvas) {
                canvas.addEventListener('click', (e) => this.handleSpectrogramClick(e));
            }
        }
        
        this.updateControls(false);
    }
    
    bindStateEvents() {
        this.stateManager.addEventListener('statechange', (e) => {
            const { newState, oldState } = e.detail;
            
            // Update audio source when file changes
            if (newState.currentFile !== oldState.currentFile) {
                this.loadAudioFile(newState.currentFile);
            }
            
            // Update weather display
            if (newState.weatherData !== oldState.weatherData) {
                if (this.spectrogramViewer && this.spectrogramViewer.infoPanels) {
                    this.spectrogramViewer.infoPanels.updateWeather(newState.weatherData);
                }
            }
        });
    }
    
    loadAudioFile(fileInfo) {
        // Stop current audio
        this.stop();
        
        if (!fileInfo || !fileInfo.filename) {
            this.currentFilename = null;
            this.updateControls(false);
            return;
        }
        
        this.currentFilename = fileInfo.filename;
        
        // Create new Howl instance
        this.audio = new Howl({
            src: [ApiService.getAudioUrl(fileInfo.filename)],
            format: ['wav'],
            preload: true,
            onload: () => {
                console.log('Audio loaded successfully');
                this.updateControls(true);
            },
            onplay: () => {
                this.updatePlayPauseButton(true);
                // Show cursor and update position when playback starts
                const currentTime = this.audio.seek() || 0;
                this.updateCursorPosition(currentTime);
                this.showCursor();
                this.startCursorAnimation();
            },
            onpause: () => {
                this.updatePlayPauseButton(false);
                this.stopCursorAnimation();
            },
            onstop: () => {
                this.updatePlayPauseButton(false);
                this.stopCursorAnimation();
                this.hideCursor();
            },
            onend: () => {
                this.updatePlayPauseButton(false);
                this.stopCursorAnimation();
                this.hideCursor();
            },
            onerror: (error) => {
                console.error('Audio playback error:', error);
                this.stateManager.setError('Failed to load audio file');
                this.updateControls(false);
            }
        });
    }
    
    handleSpectrogramClick(e) {
        if (!this.audio || !this.currentFilename) {
            console.warn('No audio file loaded');
            return;
        }
        
        const canvas = this.spectrogramViewer.getCanvas();
        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        
        // Calculate time offset using canvas display width
        const state = this.stateManager.getState();
        const currentFile = state.currentFile;
        const duration = currentFile ? currentFile.duration_seconds : 900;
        const timeOffset = (x / rect.width) * duration;
        
        this.playAtTime(timeOffset);
    }
    
    playAtTime(timeOffset) {
        if (!this.audio) {
            console.warn('No audio loaded');
            return;
        }
        
        try {
            // Force stop any current playback and clear animation
            this.stop();
            
            // Use Howler global stop to ensure no overlapping audio
            if (typeof Howler !== 'undefined') {
                Howler.stop();
            }
            
            // Small delay to ensure stop takes effect
            setTimeout(() => {
                // Show cursor at click position immediately
                this.updateCursorPosition(timeOffset);
                this.showCursor();
                
                // Seek to position and play
                this.audio.seek(timeOffset);
                this.audio.play();
            }, 10);
            
        } catch (error) {
            console.error('Playback error:', error);
            this.stateManager.setError('Audio playback failed');
        }
    }
    
    togglePlayPause() {
        if (!this.audio) return;
        
        if (this.audio.playing()) {
            this.audio.pause();
        } else {
            // Show cursor and update position when resuming playback
            const currentTime = this.audio.seek() || 0;
            this.updateCursorPosition(currentTime);
            this.showCursor();
            this.audio.play();
        }
    }
    
    stop() {
        if (this.audio) {
            this.audio.stop();
        }
        this.stopCursorAnimation();
        this.hideCursor();
    }
    
    startCursorAnimation() {
        this.stopCursorAnimation();
        
        const animate = () => {
            if (this.audio && this.audio.playing()) {
                const currentTime = this.audio.seek();
                this.updateCursorPosition(currentTime);
                this.updateTimeDisplay(currentTime);
                this.animationId = requestAnimationFrame(animate);
            } else {
                this.animationId = null;
            }
        };
        
        this.animationId = requestAnimationFrame(animate);
    }
    
    stopCursorAnimation() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }
    }
    
    updateCursorPosition(currentTime) {
        if (!this.cursor || !this.spectrogramViewer) return;
        
        const canvas = this.spectrogramViewer.getCanvas();
        const state = this.stateManager.getState();
        const currentFile = state.currentFile;
        const duration = currentFile ? currentFile.duration_seconds : 900;
        
        const progress = currentTime / duration;
        // Use same approach as crosshairs: simple pixel calculation
        const rect = canvas.getBoundingClientRect();
        const x = progress * rect.width;
        
        this.cursor.style.left = x + 'px';
    }
    
    showCursor() {
        if (this.cursor) {
            this.cursor.style.display = 'block';
            this.cursor.style.visibility = 'visible';
        }
    }
    
    hideCursor() {
        if (this.cursor) {
            this.cursor.style.display = 'none';
        }
    }
    
    updateControls(enabled) {
        if (this.playPauseBtn) {
            this.playPauseBtn.disabled = !enabled;
        }
        
        if (this.stopBtn) {
            this.stopBtn.disabled = !enabled;
        }
        
        this.updateTimeDisplay(0);
    }
    
    updatePlayPauseButton(isPlaying) {
        if (this.playPauseBtn) {
            this.playPauseBtn.textContent = isPlaying ? '⏸' : '▶';
        }
    }
    
    updateTimeDisplay(currentTime) {
        if (!this.timeDisplay) return;
        
        const state = this.stateManager.getState();
        const currentFile = state.currentFile;
        const duration = currentFile ? currentFile.duration_seconds : 900;
        
        const current = this.formatTime(currentTime);
        const total = this.formatTime(duration);
        
        this.timeDisplay.textContent = `${current} / ${total}`;
    }
    
    formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    
    /**
     * Get current playback position
     * @returns {number} Current time in seconds
     */
    getCurrentTime() {
        return this.audio ? this.audio.seek() : 0;
    }
    
    /**
     * Check if audio is currently playing
     * @returns {boolean} True if playing
     */
    isPlaying() {
        return this.audio ? this.audio.playing() : false;
    }
    
    /**
     * Set volume (0.0 to 1.0)
     * @param {number} volume - Volume level
     */
    setVolume(volume) {
        if (this.audio) {
            this.audio.volume(Math.max(0, Math.min(1, volume)));
        }
    }
    
    /**
     * Destroy the audio player
     */
    destroy() {
        this.stop();
        
        if (this.audio) {
            this.audio.unload();
            this.audio = null;
        }
        
        this.currentFilename = null;
        this.updateControls(false);
    }
}