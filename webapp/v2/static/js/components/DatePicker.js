/**
 * Date Picker Component using Easepick
 * Handles date selection with available date constraints
 */

import { ApiService } from '../services/ApiService.js';

export class DatePicker {
    constructor(elementId, stateManager) {
        this.element = document.getElementById(elementId);
        this.stateManager = stateManager;
        this.picker = null;
        
        if (!this.element) {
            throw new Error(`DatePicker element not found: ${elementId}`);
        }
        
        this.init();
    }
    
    async init() {
        try {
            // Load available dates from API
            const availableDates = await ApiService.getAvailableDates();
            this.stateManager.setAvailableDates(availableDates);
            
            // Initialize Easepick
            this.setupEasepick(availableDates);
            
        } catch (error) {
            console.error('Failed to initialize DatePicker:', error);
            this.stateManager.setError('Failed to load available dates');
        }
    }
    
    setupEasepick(availableDates) {
        if (typeof easepick === 'undefined') {
            throw new Error('Easepick library not loaded');
        }
        
        this.picker = new easepick.create({
            element: this.element,
            css: [
                'https://cdn.jsdelivr.net/npm/@easepick/bundle@1.2.1/dist/index.css',
            ],
            plugins: ['LockPlugin'],
            format: 'YYYY-MM-DD',
            date: availableDates.length > 0 ? availableDates[0] : null,
            LockPlugin: {
                filter: (date) => {
                    // Lock dates that are NOT in our available dates
                    return !availableDates.includes(date.format('YYYY-MM-DD'));
                }
            },
            setup: (picker) => {
                picker.on('select', (e) => {
                    if (e.detail.date) {
                        const selectedDate = e.detail.date.format('YYYY-MM-DD');
                        this.handleDateSelected(selectedDate);
                    }
                });
                
                picker.on('clear', () => {
                    this.stateManager.selectDate(null);
                });
            }
        });
        
        // Set initial date if available
        if (availableDates.length > 0) {
            this.handleDateSelected(availableDates[0]);
        }
    }
    
    async handleDateSelected(date) {
        try {
            this.stateManager.setLoading(true);
            this.stateManager.selectDate(date);
            
            // Load files for the selected date
            const dayFiles = await ApiService.getFilesForDate(date);
            this.stateManager.setDayFiles(dayFiles);
            
        } catch (error) {
            console.error('Failed to load files for date:', error);
            this.stateManager.setError(`Failed to load files for ${date}`);
        } finally {
            this.stateManager.setLoading(false);
        }
    }
    
    /**
     * Set date programmatically
     * @param {string} date - Date string (YYYY-MM-DD)
     */
    setDate(date) {
        if (this.picker) {
            try {
                this.picker.setDate(date);
            } catch (error) {
                console.warn('Failed to set date in picker:', error);
                // Fallback: update input value directly
                this.element.value = date;
                this.handleDateSelected(date);
            }
        }
    }
    
    /**
     * Get currently selected date
     * @returns {string|null} Selected date or null
     */
    getDate() {
        if (this.picker) {
            try {
                const date = this.picker.getDate();
                return date ? date.format('YYYY-MM-DD') : null;
            } catch (error) {
                console.warn('Failed to get date from picker:', error);
                return this.element.value || null;
            }
        }
        return null;
    }
    
    /**
     * Navigate to next available date
     */
    async nextDate() {
        const currentDate = this.getDate();
        const availableDates = this.stateManager.getState().availableDates;
        
        if (currentDate && availableDates.length > 0) {
            const currentIndex = availableDates.indexOf(currentDate);
            if (currentIndex !== -1 && currentIndex < availableDates.length - 1) {
                const nextDate = availableDates[currentIndex + 1];
                this.setDate(nextDate);
            }
        }
    }
    
    /**
     * Navigate to previous available date
     */
    async prevDate() {
        const currentDate = this.getDate();
        const availableDates = this.stateManager.getState().availableDates;
        
        if (currentDate && availableDates.length > 0) {
            const currentIndex = availableDates.indexOf(currentDate);
            if (currentIndex > 0) {
                const prevDate = availableDates[currentIndex - 1];
                this.setDate(prevDate);
            }
        }
    }
    
    /**
     * Destroy the date picker
     */
    destroy() {
        if (this.picker) {
            try {
                this.picker.destroy();
            } catch (error) {
                console.warn('Failed to destroy picker:', error);
            }
            this.picker = null;
        }
    }
}