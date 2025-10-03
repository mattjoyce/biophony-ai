/**
 * POI Strips Component
 * Renders POI time ranges as colored strips below the spectrogram
 */

import { ApiService } from '../services/ApiService.js';

export class POIStrips {
    constructor(containerId, stateManager) {
        this.container = document.getElementById(containerId);
        this.stateManager = stateManager;
        this.pois = [];
        this.stripHeight = 20;
        this.stripSpacing = 2;
        this.tooltip = null;
        
        if (!this.container) {
            throw new Error(`POI strips container not found: ${containerId}`);
        }
        
        this.init();
        this.bindStateEvents();
    }
    
    init() {
        // Create strips container
        this.stripsContainer = document.createElement('div');
        this.stripsContainer.className = 'poi-strips-container';
        this.stripsContainer.style.cssText = `
            position: relative;
            width: 100%;
            min-height: 10px;
            margin-top: 5px;
            overflow: hidden;
        `;
        this.container.appendChild(this.stripsContainer);
        
        // Create POI strips image element
        this.stripsImage = document.createElement('img');
        this.stripsImage.className = 'poi-strips-image';
        this.stripsImage.style.cssText = `
            display: block;
            width: 100%;
            height: auto;
            max-width: none;
        `;
        this.stripsContainer.appendChild(this.stripsImage);
        
        // Create tooltip element
        this.createTooltip();
    }
    
    createTooltip() {
        this.tooltip = document.createElement('div');
        this.tooltip.className = 'poi-tooltip';
        this.tooltip.style.cssText = `
            position: absolute;
            background: rgba(0, 0, 0, 0.9);
            color: white;
            padding: 8px;
            border-radius: 4px;
            font-size: 12px;
            pointer-events: none;
            z-index: 1000;
            max-width: 300px;
            display: none;
            line-height: 1.4;
        `;
        document.body.appendChild(this.tooltip);
    }
    
    bindStateEvents() {
        this.stateManager.addEventListener('statechange', (e) => {
            const { newState, oldState } = e.detail;
            
            // Reload POI strips when file changes
            if (this.shouldReloadPOIs(newState, oldState)) {
                this.loadPOIs();
            }
        });
    }
    
    shouldReloadPOIs(newState, oldState) {
        return (
            newState.selectedDate && newState.selectedTime &&
            (newState.selectedDate !== oldState.selectedDate ||
             newState.selectedTime !== oldState.selectedTime ||
             newState.colormap !== oldState.colormap) // Re-render on colormap change
        );
    }
    
    async loadPOIs() {
        const state = this.stateManager.getState();
        
        if (!state.selectedDate || !state.selectedTime) {
            this.clearStrips();
            return;
        }
        
        try {
            // Load POI data for tooltips
            const poiResponse = await fetch(`/api/file/${state.selectedDate}/${state.selectedTime}/pois`);
            if (poiResponse.ok) {
                const result = await poiResponse.json();
                this.pois = result.success ? (result.data || []) : [];
            } else {
                this.pois = [];
            }
            
            // Load POI strips PNG image
            this.renderStrips();
            
        } catch (error) {
            console.warn('Could not load POIs:', error);
            this.clearStrips();
        }
    }
    
    renderStrips() {
        const state = this.stateManager.getState();
        
        if (!state.selectedDate || !state.selectedTime) {
            this.clearStrips();
            return;
        }
        
        // Clear existing content and recreate image element
        this.stripsContainer.innerHTML = '';
        this.stripsImage = document.createElement('img');
        this.stripsImage.className = 'poi-strips-image';
        this.stripsImage.style.cssText = `
            display: block;
            width: 100%;
            height: auto;
            max-width: none;
            cursor: pointer;
        `;
        this.stripsContainer.appendChild(this.stripsImage);
        
        // Set up POI strips PNG URL with colormap
        const colormap = state.colormap || 'viridis';
        const imageUrl = `/api/poi-strips/${state.selectedDate}/${state.selectedTime}?colormap=${colormap}`;
        
        // Load the POI strips image
        this.stripsImage.onload = () => {
            console.log('POI strips PNG loaded successfully');
            this.setupImageInteractions();
        };
        
        this.stripsImage.onerror = () => {
            console.warn('Failed to load POI strips PNG, hiding container');
            this.clearStrips();
        };
        
        // Set the source to trigger loading
        this.stripsImage.src = imageUrl;
    }
    
    setupImageInteractions() {
        if (!this.stripsImage || !this.pois.length) {
            return;
        }
        
        const state = this.stateManager.getState();
        const currentFile = state.currentFile;
        const duration = currentFile ? currentFile.duration_seconds : 900;
        
        // Add mouse events for tooltips and clicks
        this.stripsImage.addEventListener('mousemove', (e) => {
            this.handleImageMouseMove(e, duration);
        });
        
        this.stripsImage.addEventListener('mouseleave', () => {
            this.hideTooltip();
        });
        
        this.stripsImage.addEventListener('click', (e) => {
            this.handleImageClick(e, duration);
        });
    }
    
    handleImageMouseMove(e, duration) {
        const rect = this.stripsImage.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        
        // Calculate time position
        const timePercent = x / rect.width;
        const timeSeconds = timePercent * duration;
        
        // Find POI at this location
        const poi = this.findPOIAtPosition(timeSeconds, y, rect.height);
        
        if (poi) {
            this.showTooltip(e, poi);
        } else {
            this.hideTooltip();
        }
    }
    
    handleImageClick(e, duration) {
        const rect = this.stripsImage.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        
        // Calculate time position
        const timePercent = x / rect.width;
        const timeSeconds = timePercent * duration;
        
        // Find POI at this location
        const poi = this.findPOIAtPosition(timeSeconds, y, rect.height);
        
        if (poi) {
            this.seekToPOI(poi);
        }
    }
    
    findPOIAtPosition(timeSeconds, y, imageHeight) {
        const stripHeight = 20; // Match server-side STRIP_HEIGHT
        const stripSpacing = 2; // Match server-side STRIP_SPACING
        
        // Calculate which strip index this Y position corresponds to
        const stripIndex = Math.floor(y / (stripHeight + stripSpacing));
        
        if (stripIndex < 0 || stripIndex >= this.pois.length) {
            return null;
        }
        
        const poi = this.pois[stripIndex];
        
        // Check if time position is within POI range
        if (timeSeconds >= poi.start_time_sec && timeSeconds <= poi.end_time_sec) {
            return poi;
        }
        
        return null;
    }
    
    
    showTooltip(e, poi) {
        const content = this.formatTooltipContent(poi);
        this.tooltip.innerHTML = content;
        this.tooltip.style.display = 'block';
        this.updateTooltipPosition(e);
    }
    
    hideTooltip() {
        this.tooltip.style.display = 'none';
    }
    
    updateTooltipPosition(e) {
        const rect = this.tooltip.getBoundingClientRect();
        let x = e.clientX + 10;
        let y = e.clientY - 10;
        
        // Adjust if tooltip would go off screen
        if (x + rect.width > window.innerWidth) {
            x = e.clientX - rect.width - 10;
        }
        if (y < 0) {
            y = e.clientY + 20;
        }
        
        this.tooltip.style.left = `${x}px`;
        this.tooltip.style.top = `${y}px`;
    }
    
    formatTooltipContent(poi) {
        const formatTime = (seconds) => {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const secs = seconds % 60;
            return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        };
        
        const duration = poi.end_time_sec - poi.start_time_sec;
        
        return `
            <div><strong>${poi.label || 'Unnamed POI'}</strong></div>
            <div>Time: ${formatTime(poi.start_time_sec)} - ${formatTime(poi.end_time_sec)}</div>
            <div>Duration: ${duration}s</div>
            <div>Confidence: ${((poi.confidence || 0) * 100).toFixed(1)}%</div>
            ${poi.anchor_index_name ? `<div>Index: ${poi.anchor_index_name}</div>` : ''}
            ${poi.notes ? `<div style="margin-top: 4px; font-style: italic;">${poi.notes}</div>` : ''}
            <div style="margin-top: 4px; font-size: 10px; opacity: 0.7;">Click to seek to this location</div>
        `;
    }
    
    seekToPOI(poi) {
        // Navigate to the POI's start time in the audio player
        const audioPlayer = window.audioMothApp?.audioPlayer;
        if (audioPlayer) {
            audioPlayer.seekToTime(poi.start_time_sec);
        }
    }
    
    clearStrips() {
        this.pois = [];
        if (this.stripsContainer) {
            this.stripsContainer.innerHTML = '';
            this.stripsContainer.style.minHeight = '10px';
        }
        if (this.stripsImage) {
            this.stripsImage.src = '';
            this.stripsImage = null;
        }
        this.hideTooltip();
    }
    
    /**
     * Destroy the POI strips component
     */
    destroy() {
        this.clearStrips();
        
        if (this.tooltip && this.tooltip.parentNode) {
            this.tooltip.parentNode.removeChild(this.tooltip);
        }
        
        if (this.stripsContainer && this.stripsContainer.parentNode) {
            this.stripsContainer.parentNode.removeChild(this.stripsContainer);
        }
    }
}