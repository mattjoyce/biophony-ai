/**
 * Controls Component
 * Handles colormap and gamma adjustment controls
 */

export class Controls {
    constructor(stateManager, spectrogramViewer) {
        this.stateManager = stateManager;
        this.spectrogramViewer = spectrogramViewer;
        
        // Get control elements
        this.colormapSelector = document.getElementById('colormap-selector');
        this.gammaSlider = document.getElementById('gamma-slider');
        this.gammaValue = document.getElementById('gamma-value');
        
        // Debouncing for gamma
        this.gammaDebounceTimer = null;
        this.gammaUpdateFrame = null;
        
        this.init();
        this.bindStateEvents();
    }
    
    init() {
        // Setup colormap selector
        if (this.colormapSelector) {
            this.colormapSelector.addEventListener('change', (e) => {
                this.handleColormapChange(e.target.value);
            });
            
            // Set initial value
            const currentColormap = this.stateManager.getState().colormap;
            this.colormapSelector.value = currentColormap;
        }
        
        // Setup gamma slider with real-time adjustment
        if (this.gammaSlider) {
            this.gammaSlider.addEventListener('input', (e) => {
                this.handleGammaInputRealtime(parseFloat(e.target.value));
            });
            
            // Save to state when slider stops moving (debounced)
            this.gammaSlider.addEventListener('change', (e) => {
                this.handleGammaChangeFinal(parseFloat(e.target.value));
            });
            
            // Double-click to reset gamma
            this.gammaSlider.addEventListener('dblclick', () => {
                this.resetGamma();
            });
            
            // Set initial value
            const currentGamma = this.stateManager.getState().gamma;
            this.gammaSlider.value = currentGamma;
        }
        
        // Update gamma display
        this.updateGammaDisplay();
    }
    
    bindStateEvents() {
        this.stateManager.addEventListener('statechange', (e) => {
            const { newState, oldState } = e.detail;
            
            // Update controls when state changes externally
            if (newState.colormap !== oldState.colormap) {
                this.updateColormapSelector(newState.colormap);
            }
            
            if (newState.gamma !== oldState.gamma) {
                this.updateGammaSlider(newState.gamma);
            }
        });
    }
    
    handleColormapChange(colormap) {
        // Save preference to localStorage
        localStorage.setItem('selectedColormap', colormap);
        
        // Update state
        this.stateManager.setColormap(colormap);
    }
    
    handleGammaInputRealtime(gamma) {
        // Cancel any pending frame
        if (this.gammaUpdateFrame) {
            cancelAnimationFrame(this.gammaUpdateFrame);
        }
        
        // Schedule update on next frame for smooth performance
        this.gammaUpdateFrame = requestAnimationFrame(() => {
            // Apply gamma directly to canvas (real-time)
            if (this.spectrogramViewer) {
                this.spectrogramViewer.applyGammaAdjustment(gamma);
            }
            
            // Update display immediately
            this.updateGammaDisplayValue(gamma);
            this.gammaUpdateFrame = null;
        });
    }
    
    handleGammaChangeFinal(gamma) {
        // Clear any pending timers
        if (this.gammaDebounceTimer) {
            clearTimeout(this.gammaDebounceTimer);
        }
        
        // Debounce state updates and localStorage saves
        this.gammaDebounceTimer = setTimeout(() => {
            // Only update state when user stops dragging (for localStorage, etc.)
            this.stateManager.setGamma(gamma);
            this.saveGammaPreference(gamma);
            this.gammaDebounceTimer = null;
        }, 300); // 300ms debounce
    }
    
    saveGammaPreference(gamma) {
        localStorage.setItem('selectedGamma', gamma.toString());
    }
    
    resetGamma() {
        const resetValue = 1.0;
        
        // Update slider
        if (this.gammaSlider) {
            this.gammaSlider.value = resetValue;
        }
        
        // Apply immediately to canvas
        if (this.spectrogramViewer) {
            this.spectrogramViewer.applyGammaAdjustment(resetValue);
        }
        
        // Update display and save
        this.updateGammaDisplayValue(resetValue);
        this.stateManager.setGamma(resetValue);
        this.saveGammaPreference(resetValue);
    }
    
    updateColormapSelector(colormap) {
        if (this.colormapSelector && this.colormapSelector.value !== colormap) {
            this.colormapSelector.value = colormap;
        }
    }
    
    updateGammaSlider(gamma) {
        if (this.gammaSlider && parseFloat(this.gammaSlider.value) !== gamma) {
            this.gammaSlider.value = gamma;
            this.updateGammaDisplay();
        }
    }
    
    updateGammaDisplay() {
        if (this.gammaValue) {
            const gamma = this.stateManager.getState().gamma;
            this.gammaValue.textContent = gamma.toFixed(1);
        }
    }
    
    updateGammaDisplayValue(gamma) {
        if (this.gammaValue) {
            this.gammaValue.textContent = gamma.toFixed(1);
        }
    }
    
    /**
     * Load saved preferences from localStorage
     */
    loadSavedPreferences() {
        // Load saved colormap
        const savedColormap = localStorage.getItem('selectedColormap');
        if (savedColormap) {
            this.stateManager.setColormap(savedColormap);
        }
        
        // Load saved gamma (if any)
        const savedGamma = localStorage.getItem('selectedGamma');
        if (savedGamma) {
            const gamma = parseFloat(savedGamma);
            if (!isNaN(gamma) && gamma > 0 && gamma <= 10) {
                this.stateManager.setGamma(gamma);
            }
        }
    }
    
    /**
     * Save current preferences to localStorage
     */
    savePreferences() {
        const state = this.stateManager.getState();
        localStorage.setItem('selectedColormap', state.colormap);
        localStorage.setItem('selectedGamma', state.gamma.toString());
    }
    
    /**
     * Get available colormap options
     * @returns {Array<string>} Array of colormap names
     */
    getAvailableColormaps() {
        if (this.colormapSelector) {
            return Array.from(this.colormapSelector.options).map(option => option.value);
        }
        return [];
    }
    
    /**
     * Add colormap option dynamically
     * @param {string} value - Colormap value
     * @param {string} text - Display text
     */
    addColormapOption(value, text) {
        if (this.colormapSelector) {
            const option = document.createElement('option');
            option.value = value;
            option.textContent = text;
            this.colormapSelector.appendChild(option);
        }
    }
    
    /**
     * Set gamma limits
     * @param {number} min - Minimum gamma value
     * @param {number} max - Maximum gamma value
     * @param {number} step - Step size
     */
    setGammaLimits(min = 0.1, max = 3.0, step = 0.1) {
        if (this.gammaSlider) {
            this.gammaSlider.min = min;
            this.gammaSlider.max = max;
            this.gammaSlider.step = step;
        }
    }
    
    /**
     * Destroy the controls component
     */
    destroy() {
        // Clean up timers and animation frames
        if (this.gammaDebounceTimer) {
            clearTimeout(this.gammaDebounceTimer);
            this.gammaDebounceTimer = null;
        }
        
        if (this.gammaUpdateFrame) {
            cancelAnimationFrame(this.gammaUpdateFrame);
            this.gammaUpdateFrame = null;
        }
        
        // Save preferences before destroying
        this.savePreferences();
    }
}