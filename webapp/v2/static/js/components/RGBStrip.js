/**
 * RGB Strip Component
 * Renders a 2px RGB visualization strip above the spectrogram
 */

import { ApiService } from '../services/ApiService.js';

export class RGBStrip {
    constructor(containerId, stateManager) {
        this.container = document.getElementById(containerId);
        this.stateManager = stateManager;
        
        if (!this.container) {
            throw new Error(`RGB Strip container not found: ${containerId}`);
        }
        
        this.canvas = null;
        this.ctx = null;
        this.isVisible = false;
        
        this.init();
        this.bindStateEvents();
    }
    
    init() {
        this.render();
    }
    
    render() {
        this.container.innerHTML = `
            <canvas id="rgb-strip-canvas" class="rgb-strip" height="10" title="RGB Acoustic Indices Visualization"></canvas>
        `;
        
        this.canvas = document.getElementById('rgb-strip-canvas');
        this.stripContainer = this.container;
        
        // Add CSS class to container
        this.container.className = 'rgb-strip-container';
        this.container.style.display = 'block';
        
        if (this.canvas) {
            this.ctx = this.canvas.getContext('2d');
            // Disable image smoothing for pixel-perfect rendering
            this.ctx.imageSmoothingEnabled = false;
            
            // Sync with spectrogram canvas width
            this.syncCanvasSize();
            
        }
    }
    
    syncCanvasSize() {
        const spectrogramCanvas = document.getElementById('spectrogram-canvas');
        if (spectrogramCanvas && this.canvas) {
            const oldWidth = this.canvas.width;
            const newWidth = spectrogramCanvas.width || 1000;
            
            // Only resize if width actually changed (resizing clears canvas)
            if (oldWidth !== newWidth) {
                console.log(`⚠️ RGB Strip: Canvas width changing ${oldWidth} → ${newWidth} (will clear canvas!)`);
                this.canvas.width = newWidth;
                this.canvas.style.width = spectrogramCanvas.style.width || '100%';
                
                // Re-render RGB data after resize since canvas was cleared
                const state = this.stateManager.getState();
                if (state.rgbData && this.hasChannelAssignments(state.rgbChannels)) {
                    console.log('🔄 RGB Strip: Re-rendering after canvas resize');
                    this.renderRGBData(state.rgbData);
                }
            }
        }
    }
    
    
    bindStateEvents() {
        this.stateManager.addEventListener('statechange', (e) => {
            const { newState, oldState } = e.detail;
            
            // Sync canvas size when spectrogram changes
            if (newState.selectedDate !== oldState.selectedDate || 
                newState.selectedTime !== oldState.selectedTime) {
                
                // Sync canvas size after a short delay
                setTimeout(() => {
                    this.syncCanvasSize();
                }, 100);
            }
            
            // Update visualization when RGB channels change or when date/time changes
            if (this.shouldUpdateRGBData(newState, oldState)) {
                this.loadAndRenderRGBData();
            }
            
            // Update strip based on channel assignments
            if (newState.rgbChannels !== oldState.rgbChannels) {
                this.updateStripDisplay(newState.rgbChannels);
                this.updateTooltip(newState.rgbChannels);
            }
        });
    }
    
    shouldUpdateRGBData(newState, oldState) {
        // Update if date/time changed and we have channel assignments
        const dateTimeChanged = (
            newState.selectedDate !== oldState.selectedDate ||
            newState.selectedTime !== oldState.selectedTime
        );
        
        // Update if RGB channel assignments changed
        const channelsChanged = newState.rgbChannels !== oldState.rgbChannels;
        
        // Only update if we have a valid selection and assignments
        const hasValidSelection = newState.selectedDate && newState.selectedTime;
        const hasAssignments = this.hasChannelAssignments(newState.rgbChannels);
        
        return hasValidSelection && hasAssignments && (dateTimeChanged || channelsChanged);
    }
    
    updateStripDisplay(channels) {
        const hasAssignments = this.hasChannelAssignments(channels);
        
        // Always show the strip
        if (!this.isVisible) {
            this.show();
        }
        
        // Hide strip if no assignments
        if (!hasAssignments) {
            this.hide();
        }
    }
    
    hasChannelAssignments(channels) {
        return !!(channels.red || channels.green || channels.blue);
    }
    
    show() {
        if (this.stripContainer) {
            console.log('🟢 RGB Strip: SHOWING');
            this.stripContainer.style.display = 'block';
            this.isVisible = true;
        }
    }
    
    hide() {
        if (this.stripContainer) {
            console.log('🔴 RGB Strip: HIDING');
            this.stripContainer.style.display = 'none';
            this.isVisible = false;
        }
        this.clearCanvas();
    }
    
    updateTooltip(channels) {
        if (!this.canvas) return;
        
        const formatIndexName = (indexName) => {
            return indexName
                .replace(/_/g, ' ')
                .replace(/\b\w/g, letter => letter.toUpperCase());
        };
        
        const assignedChannels = Object.entries(channels)
            .filter(([channel, indexName]) => indexName)
            .map(([channel, indexName]) => `${channel.toUpperCase()}: ${formatIndexName(indexName)}`);
        
        if (assignedChannels.length === 0) {
            this.canvas.title = 'RGB Acoustic Indices Visualization - No channels assigned';
        } else {
            this.canvas.title = 'RGB Acoustic Indices: ' + assignedChannels.join(' | ');
        }
    }
    
    async loadAndRenderRGBData() {
        const state = this.stateManager.getState();
        
        if (!state.selectedDate || !state.selectedTime) {
            return;
        }
        
        const channels = state.rgbChannels;
        if (!this.hasChannelAssignments(channels)) {
            this.hide();
            return;
        }
        
        try {
            const rgbData = await ApiService.getRGBIndices(
                state.selectedDate,
                state.selectedTime,
                channels
            );
            
            this.stateManager.setRGBData(rgbData);
            this.show(); // Ensure strip is visible when we have data
            this.renderRGBData(rgbData);
            
        } catch (error) {
            console.error('Failed to load RGB data:', error);
            this.stateManager.setError(`Failed to load RGB data: ${error.message}`);
        }
    }
    
    renderRGBData(rgbData) {
        console.log('🎨 RGB Strip: RENDERING RGB DATA');
        if (!this.ctx || !rgbData || !rgbData.rgb_data) {
            console.log('❌ RGB Strip: Cannot render - missing context or data');
            return;
        }
        
        const data = rgbData.rgb_data;
        const chunkCount = data.length;
        
        // Keep canvas width same as spectrogram canvas
        const spectrogramCanvas = document.getElementById('spectrogram-canvas');
        const canvasWidth = spectrogramCanvas ? spectrogramCanvas.width : 1000;
        
        this.canvas.width = canvasWidth;
        this.canvas.height = 10;
        
        // Calculate how many pixels each chunk should span
        const pixelsPerChunk = canvasWidth / chunkCount;
        
        // Clear canvas
        this.ctx.clearRect(0, 0, canvasWidth, 10);
        
        // Draw each chunk as a rectangle spanning the calculated width
        for (let i = 0; i < chunkCount; i++) {
            const chunk = data[i];
            const [r, g, b] = chunk.rgb || [0, 0, 0];
            
            // Set fill color
            this.ctx.fillStyle = `rgb(${r}, ${g}, ${b})`;
            
            // Calculate position and width for this chunk
            const x = Math.floor(i * pixelsPerChunk);
            const width = Math.ceil(pixelsPerChunk);
            
            // Fill rectangle for this chunk
            this.ctx.fillRect(x, 0, width, 10);
        }
    }
    
    clearCanvas() {
        if (this.ctx) {
            console.log('🧹 RGB Strip: CLEARING CANVAS');
            this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        }
    }
    
    /**
     * Resize the strip to match spectrogram width
     * @param {number} width - New width in pixels
     */
    resizeToWidth(width) {
        if (this.stripContainer) {
            this.stripContainer.style.width = `${width}px`;
        }
        
        // Re-render if we have data
        const state = this.stateManager.getState();
        if (state.rgbData) {
            this.renderRGBData(state.rgbData);
        }
    }
    
    /**
     * Get RGB values at a specific time position
     * @param {number} timeOffset - Time offset in seconds
     * @returns {Object|null} RGB values and raw data at position
     */
    getValuesAtTime(timeOffset) {
        const state = this.stateManager.getState();
        const rgbData = state.rgbData;
        
        if (!rgbData || !rgbData.rgb_data) {
            return null;
        }
        
        // Find closest chunk
        const chunks = rgbData.rgb_data;
        const closestChunk = chunks.reduce((closest, chunk) => {
            const timeDiff = Math.abs(chunk.start_time_sec - timeOffset);
            const closestDiff = Math.abs(closest.start_time_sec - timeOffset);
            return timeDiff < closestDiff ? chunk : closest;
        });
        
        if (closestChunk) {
            return {
                rgb: closestChunk.rgb,
                raw_values: closestChunk.raw_values,
                chunk_index: closestChunk.chunk_index,
                start_time_sec: closestChunk.start_time_sec
            };
        }
        
        return null;
    }
    
    /**
     * Destroy the RGB strip component
     */
    destroy() {
        this.hide();
        if (this.container) {
            this.container.innerHTML = '';
        }
    }
}