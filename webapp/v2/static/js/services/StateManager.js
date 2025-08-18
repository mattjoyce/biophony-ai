/**
 * State Manager for AudioMoth Spectrogram Viewer
 * Centralized state management with event-driven updates
 */

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
            isLoading: false,
            currentFile: null,
            weatherData: null,
            error: null,
            // RGB Indices state
            availableIndices: [],
            rgbChannels: {
                red: null,
                green: null,
                blue: null
            },
            rgbData: null
        };
    }
    
    /**
     * Update state and emit change event
     * @param {Object} updates - Partial state updates
     */
    setState(updates) {
        const oldState = { ...this.state };
        this.state = { ...this.state, ...updates };
        
        // Emit state change event
        this.dispatchEvent(new CustomEvent('statechange', {
            detail: { 
                oldState, 
                newState: this.state,
                changes: updates
            }
        }));
    }
    
    /**
     * Get current state (immutable copy)
     * @returns {Object} Current state
     */
    getState() {
        return { ...this.state };
    }
    
    /**
     * Clear error state
     */
    clearError() {
        if (this.state.error) {
            this.setState({ error: null });
        }
    }
    
    /**
     * Set error state
     * @param {string} errorMessage - Error message
     */
    setError(errorMessage) {
        this.setState({ error: errorMessage });
    }
    
    /**
     * Set loading state
     * @param {boolean} isLoading - Loading state
     */
    setLoading(isLoading) {
        this.setState({ isLoading });
    }
    
    /**
     * Update available dates
     * @param {Array<string>} dates - Available dates
     */
    setAvailableDates(dates) {
        this.setState({ availableDates: dates });
    }
    
    /**
     * Select a date and update related state
     * @param {string} date - Selected date (YYYY-MM-DD)
     */
    selectDate(date) {
        this.setState({ 
            selectedDate: date,
            selectedTime: null, // Clear time when date changes
            currentFile: null,
            weatherData: null
        });
    }
    
    /**
     * Select a time for the current date
     * @param {string} time - Selected time (HH:MM)
     */
    selectTime(time) {
        this.setState({ selectedTime: time });
    }
    
    /**
     * Update files for the current day
     * @param {Array} files - Files for the day
     */
    setDayFiles(files) {
        this.setState({ dayFiles: files });
    }
    
    /**
     * Update colormap setting
     * @param {string} colormap - Colormap name
     */
    setColormap(colormap) {
        this.setState({ colormap });
    }
    
    /**
     * Update gamma setting
     * @param {number} gamma - Gamma value
     */
    setGamma(gamma) {
        this.setState({ gamma });
    }
    
    /**
     * Set current file information
     * @param {Object} file - File information
     */
    setCurrentFile(file) {
        this.setState({ currentFile: file });
    }
    
    /**
     * Set weather data
     * @param {Object} weather - Weather data
     */
    setWeatherData(weather) {
        this.setState({ weatherData: weather });
    }
    
    /**
     * Get current date/time selection
     * @returns {Object} Current selection
     */
    getCurrentSelection() {
        return {
            date: this.state.selectedDate,
            time: this.state.selectedTime,
            hasSelection: !!(this.state.selectedDate && this.state.selectedTime)
        };
    }
    
    /**
     * Set available acoustic indices
     * @param {Array<string>} indices - Available index names
     */
    setAvailableIndices(indices) {
        this.setState({ availableIndices: indices });
    }
    
    /**
     * Set RGB channel assignment
     * @param {string} channel - 'red', 'green', or 'blue'
     * @param {string} indexName - Index name to assign to channel
     */
    setRGBChannel(channel, indexName) {
        if (!['red', 'green', 'blue'].includes(channel)) {
            throw new Error(`Invalid RGB channel: ${channel}`);
        }
        
        const newChannels = { ...this.state.rgbChannels };
        newChannels[channel] = indexName;
        
        this.setState({ rgbChannels: newChannels });
    }
    
    /**
     * Clear RGB channel assignment
     * @param {string} channel - 'red', 'green', or 'blue'
     */
    clearRGBChannel(channel) {
        this.setRGBChannel(channel, null);
    }
    
    /**
     * Clear all RGB channel assignments
     */
    clearAllRGBChannels() {
        this.setState({
            rgbChannels: {
                red: null,
                green: null,
                blue: null
            },
            rgbData: null
        });
    }
    
    /**
     * Set RGB visualization data
     * @param {Object} rgbData - RGB visualization data from API
     */
    setRGBData(rgbData) {
        this.setState({ rgbData });
    }
    
    /**
     * Get current RGB channel assignments
     * @returns {Object} RGB channel assignments
     */
    getRGBChannels() {
        return { ...this.state.rgbChannels };
    }
    
    /**
     * Check if any RGB channels are assigned
     * @returns {boolean} True if at least one channel is assigned
     */
    hasRGBAssignments() {
        const channels = this.state.rgbChannels;
        return !!(channels.red || channels.green || channels.blue);
    }
    
    /**
     * Check if state has changed for specific keys
     * @param {Object} oldState - Previous state
     * @param {Object} newState - Current state  
     * @param {Array<string>} keys - Keys to check
     * @returns {boolean} True if any key changed
     */
    static hasChanged(oldState, newState, keys) {
        return keys.some(key => oldState[key] !== newState[key]);
    }
}