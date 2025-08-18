/**
 * RGB Picker Component
 * Handles selection of acoustic indices for RGB color channels
 */

import { ApiService } from '../services/ApiService.js';

export class RGBPicker {
    constructor(containerId, stateManager) {
        this.container = document.getElementById(containerId);
        this.stateManager = stateManager;
        
        if (!this.container) {
            throw new Error(`RGB Picker container not found: ${containerId}`);
        }
        
        this.availableIndices = [];
        this.channelSelectors = {};
        
        this.init();
        this.bindStateEvents();
        this.loadAvailableIndices();
    }
    
    init() {
        this.render();
        this.bindEvents();
    }
    
    render() {
        this.container.innerHTML = `
            <div class="rgb-picker">
                <h3>RGB Indices</h3>
                <div class="rgb-channels">
                    <div class="channel-group">
                        <div class="channel-selector red-channel">
                            <div class="channel-color red"></div>
                            <select id="rgb-red-select" class="channel-select">
                                <option value="">Red Channel</option>
                            </select>
                            <button class="clear-channel" data-channel="red">×</button>
                        </div>
                    </div>
                    
                    <div class="channel-group">
                        <div class="channel-selector green-channel">
                            <div class="channel-color green"></div>
                            <select id="rgb-green-select" class="channel-select">
                                <option value="">Green Channel</option>
                            </select>
                            <button class="clear-channel" data-channel="green">×</button>
                        </div>
                    </div>
                    
                    <div class="channel-group">
                        <div class="channel-selector blue-channel">
                            <div class="channel-color blue"></div>
                            <select id="rgb-blue-select" class="channel-select">
                                <option value="">Blue Channel</option>
                            </select>
                            <button class="clear-channel" data-channel="blue">×</button>
                        </div>
                    </div>
                </div>
                
                <div class="rgb-controls">
                    <button id="clear-all-channels" class="btn btn-small">Clear All</button>
                </div>
            </div>
        `;
        
        // Store references to selectors
        this.channelSelectors = {
            red: document.getElementById('rgb-red-select'),
            green: document.getElementById('rgb-green-select'),
            blue: document.getElementById('rgb-blue-select')
        };
    }
    
    bindEvents() {
        // Channel selection events
        Object.entries(this.channelSelectors).forEach(([channel, selector]) => {
            selector.addEventListener('change', (e) => {
                this.handleChannelSelection(channel, e.target.value);
            });
        });
        
        // Clear channel buttons
        this.container.querySelectorAll('.clear-channel').forEach(button => {
            button.addEventListener('click', (e) => {
                const channel = e.target.dataset.channel;
                this.clearChannel(channel);
            });
        });
        
        // Clear all button
        const clearAllBtn = document.getElementById('clear-all-channels');
        if (clearAllBtn) {
            clearAllBtn.addEventListener('click', () => this.clearAllChannels());
        }
    }
    
    bindStateEvents() {
        this.stateManager.addEventListener('statechange', (e) => {
            const { newState, oldState } = e.detail;
            
            // Update UI when available indices change
            if (newState.availableIndices !== oldState.availableIndices) {
                this.updateAvailableIndices(newState.availableIndices);
            }
            
            // Update UI when RGB channels change
            if (newState.rgbChannels !== oldState.rgbChannels) {
                this.updateChannelSelections(newState.rgbChannels);
            }
        });
    }
    
    async loadAvailableIndices() {
        try {
            this.stateManager.setLoading(true);
            const indices = await ApiService.getAvailableIndices();
            this.stateManager.setAvailableIndices(indices);
        } catch (error) {
            console.error('Failed to load available indices:', error);
            this.stateManager.setError(`Failed to load available indices: ${error.message}`);
        } finally {
            this.stateManager.setLoading(false);
        }
    }
    
    updateAvailableIndices(indices) {
        this.availableIndices = indices;
        
        // Update all channel selectors
        Object.values(this.channelSelectors).forEach(selector => {
            // Store current selection
            const currentValue = selector.value;
            
            // Clear and rebuild options
            selector.innerHTML = `<option value="">${selector.dataset.placeholder || 'Select Index'}</option>`;
            
            indices.forEach(index => {
                const option = document.createElement('option');
                option.value = index;
                option.textContent = this.formatIndexName(index);
                selector.appendChild(option);
            });
            
            // Restore selection if still valid
            if (currentValue && indices.includes(currentValue)) {
                selector.value = currentValue;
            }
        });
    }
    
    updateChannelSelections(channels) {
        // Update selector values
        Object.entries(channels).forEach(([channel, indexName]) => {
            const selector = this.channelSelectors[channel];
            if (selector) {
                selector.value = indexName || '';
            }
        });
    }
    
    
    handleChannelSelection(channel, indexName) {
        if (indexName) {
            // Check if this index is already assigned to another channel
            const currentChannels = this.stateManager.getRGBChannels();
            const conflictChannel = Object.entries(currentChannels)
                .find(([ch, idx]) => ch !== channel && idx === indexName);
            
            if (conflictChannel) {
                // Clear the conflicting channel
                this.stateManager.clearRGBChannel(conflictChannel[0]);
            }
            
            this.stateManager.setRGBChannel(channel, indexName);
        } else {
            this.stateManager.clearRGBChannel(channel);
        }
    }
    
    clearChannel(channel) {
        this.stateManager.clearRGBChannel(channel);
    }
    
    clearAllChannels() {
        this.stateManager.clearAllRGBChannels();
    }
    
    formatIndexName(indexName) {
        // Format index names for display (replace underscores, capitalize)
        return indexName
            .replace(/_/g, ' ')
            .replace(/\b\w/g, letter => letter.toUpperCase());
    }
    
    /**
     * Get current RGB channel assignments
     * @returns {Object} Current channel assignments
     */
    getChannelAssignments() {
        return this.stateManager.getRGBChannels();
    }
    
    /**
     * Check if any channels are assigned
     * @returns {boolean} True if at least one channel is assigned
     */
    hasAssignments() {
        return this.stateManager.hasRGBAssignments();
    }
    
    /**
     * Destroy the RGB picker component
     */
    destroy() {
        if (this.container) {
            this.container.innerHTML = '';
        }
    }
}