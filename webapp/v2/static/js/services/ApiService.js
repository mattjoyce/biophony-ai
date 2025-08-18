/**
 * API Service for AudioMoth Spectrogram Viewer
 * Handles all API communication with proper error handling
 */

export class ApiService {
    /**
     * Base API request with error handling
     * @param {string} url - API endpoint URL
     * @param {Object} options - Fetch options
     * @returns {Promise} Response promise
     */
    static async request(url, options = {}) {
        try {
            const response = await fetch(url, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            return response;
        } catch (error) {
            console.error(`API request failed for ${url}:`, error);
            throw error;
        }
    }
    
    /**
     * Get available dates that have audio files
     * @returns {Promise<Array<string>>} Array of date strings (YYYY-MM-DD)
     */
    static async getAvailableDates() {
        const response = await this.request('/api/dates');
        const result = await response.json();
        
        if (result.success) {
            return result.data;
        } else {
            throw new Error(result.error || 'Failed to get available dates');
        }
    }
    
    /**
     * Get all files for a specific date
     * @param {string} date - Date string (YYYY-MM-DD)
     * @returns {Promise<Array>} Array of file objects
     */
    static async getFilesForDate(date) {
        const response = await this.request(`/api/files/${date}`);
        const result = await response.json();
        
        if (result.success) {
            return result.data;
        } else {
            throw new Error(result.error || 'Failed to get files for date');
        }
    }
    
    /**
     * Get specific file information
     * @param {string} date - Date string (YYYY-MM-DD)
     * @param {string} time - Time string (HH:MM)
     * @returns {Promise<Object>} File information
     */
    static async getFileInfo(date, time) {
        const response = await this.request(`/api/file/${date}/${time}`);
        const result = await response.json();
        
        if (result.success) {
            return result.data;
        } else {
            throw new Error(result.error || 'Failed to get file info');
        }
    }
    
    /**
     * Get spectrogram image as blob
     * @param {string} date - Date string (YYYY-MM-DD)
     * @param {string} time - Time string (HH:MM)
     * @param {string} colormap - Colormap name (default: 'viridis')
     * @param {number} gamma - Gamma correction value (default: 1.0)
     * @returns {Promise<Blob>} Spectrogram image blob
     */
    static async getSpectrogram(date, time, colormap = 'viridis', gamma = 1.0) {
        const params = new URLSearchParams({ colormap, gamma: gamma.toString() });
        const response = await this.request(`/api/spectrogram/${date}/${time}?${params}`);
        
        if (response.ok) {
            return response.blob();
        } else {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Failed to get spectrogram');
        }
    }
    
    /**
     * Get weather data for specific recording time
     * @param {string} date - Date string (YYYY-MM-DD)
     * @param {string} time - Time string (HH:MM)
     * @returns {Promise<Object>} Weather data
     */
    static async getWeatherData(date, time) {
        const response = await this.request(`/api/weather/${date}/${time}`);
        const result = await response.json();
        
        if (result.success) {
            return result.data;
        } else {
            throw new Error(result.error || 'Weather data not available');
        }
    }
    
    /**
     * Get URL for audio file streaming
     * @param {string} filename - Audio filename
     * @returns {string} Audio URL for Howler.js
     */
    static getAudioUrl(filename) {
        return `/api/audio/${filename}`;
    }
    
    /**
     * Get audio URL by date and time
     * @param {string} date - Date string (YYYY-MM-DD)
     * @param {string} time - Time string (HH:MM)
     * @returns {string} Audio URL
     */
    static getAudioUrlByDateTime(date, time) {
        return `/api/audio/${date}/${time}`;
    }
    
    /**
     * Get colormap data
     * @param {string} colormapName - Name of colormap
     * @returns {Promise<Array>} Colormap RGB values
     */
    static async getColormap(colormapName) {
        const response = await this.request(`/api/colormap/${colormapName}`);
        
        if (response.ok) {
            return response.json();
        } else {
            const errorData = await response.json();
            throw new Error(errorData.error || `Failed to get colormap: ${colormapName}`);
        }
    }
    
    /**
     * Get mel scale frequency mapping
     * @param {number} sampleRate - Sample rate (default: 48000)
     * @param {number} nMels - Number of mel bands (default: 128)
     * @param {number} fmin - Minimum frequency (default: 0)
     * @param {number} fmax - Maximum frequency (default: sampleRate/2)
     * @returns {Promise<Object>} Mel scale data
     */
    static async getMelScale(sampleRate = 48000, nMels = 128, fmin = 0, fmax = null) {
        const params = new URLSearchParams({ 
            sample_rate: sampleRate.toString(),
            n_mels: nMels.toString(),
            fmin: fmin.toString()
        });
        
        if (fmax !== null) {
            params.append('fmax', fmax.toString());
        }
        
        const response = await this.request(`/api/mel_scale?${params}`);
        return response.json();
    }
    
    /**
     * Get available times for all dates
     * @returns {Promise<Object>} Object with dates as keys and time arrays as values
     */
    static async getAvailableTimes() {
        const response = await this.request('/api/available_times');
        return response.json();
    }
    
    /**
     * Get navigation file (next/previous)
     * @param {string} date - Current date
     * @param {string} time - Current time
     * @param {string} direction - 'next' or 'prev'
     * @returns {Promise<Object>} Next/previous file info
     */
    static async getNavigationFile(date, time, direction) {
        const params = new URLSearchParams({ date, time, direction });
        const response = await this.request(`/api/navigation?${params}`);
        const result = await response.json();
        
        if (result.success) {
            return result.data;
        } else {
            throw new Error(result.error || `No ${direction} file found`);
        }
    }
    
    /**
     * Search files with filters
     * @param {Object} filters - Search filters
     * @returns {Promise<Array>} Array of matching files
     */
    static async searchFiles(filters = {}) {
        const params = new URLSearchParams();
        
        Object.entries(filters).forEach(([key, value]) => {
            if (value !== null && value !== undefined) {
                params.append(key, value.toString());
            }
        });
        
        const response = await this.request(`/api/files?${params}`);
        const result = await response.json();
        
        if (result.success) {
            return result.data;
        } else {
            throw new Error(result.error || 'Failed to search files');
        }
    }
    
    /**
     * Get available acoustic index types
     * @returns {Promise<Array<string>>} Array of index names
     */
    static async getAvailableIndices() {
        const response = await this.request('/api/indices/available');
        const result = await response.json();
        
        if (result.success) {
            return result.data;
        } else {
            throw new Error(result.error || 'Failed to get available indices');
        }
    }
    
    /**
     * Get all acoustic indices data for a specific file
     * @param {string} date - Date string (YYYY-MM-DD)
     * @param {string} time - Time string (HH:MM)
     * @returns {Promise<Object>} Indices data organized by index name
     */
    static async getFileIndices(date, time) {
        const response = await this.request(`/api/indices/${date}/${time}`);
        const result = await response.json();
        
        if (result.success) {
            return result.data;
        } else {
            throw new Error(result.error || 'Failed to get indices data');
        }
    }
    
    /**
     * Get RGB-mapped indices data for visualization
     * @param {string} date - Date string (YYYY-MM-DD)
     * @param {string} time - Time string (HH:MM)
     * @param {Object} channels - RGB channel assignments {red: 'index_name', green: 'index_name', blue: 'index_name'}
     * @returns {Promise<Object>} RGB visualization data
     */
    static async getRGBIndices(date, time, channels = {}) {
        const params = new URLSearchParams();
        
        if (channels.red) params.append('red', channels.red);
        if (channels.green) params.append('green', channels.green);
        if (channels.blue) params.append('blue', channels.blue);
        
        const response = await this.request(`/api/indices/${date}/${time}/rgb?${params}`);
        const result = await response.json();
        
        if (result.success) {
            return result.data;
        } else {
            throw new Error(result.error || 'Failed to get RGB indices data');
        }
    }
}