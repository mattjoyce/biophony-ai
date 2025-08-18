/**
 * Navigation Component
 * Handles file and day navigation with RGB state preservation
 */

import { ApiService } from '../services/ApiService.js';

export class Navigation {
    constructor(containerId, stateManager, mainApp) {
        this.container = document.getElementById(containerId);
        this.stateManager = stateManager;
        this.mainApp = mainApp; // Reference to main app for navigation methods
        
        if (!this.container) {
            throw new Error(`Navigation container not found: ${containerId}`);
        }
        
        this.prevDayBtn = null;
        this.prevFileBtn = null;
        this.nextFileBtn = null;
        this.nextDayBtn = null;
        this.currentFileDisplay = null;
        
        this.init();
        this.bindStateEvents();
    }
    
    init() {
        this.bindElements();
        this.bindEvents();
        this.updateDisplay();
    }
    
    bindElements() {
        this.prevDayBtn = document.getElementById('prev-day');
        this.prevFileBtn = document.getElementById('prev-file');
        this.nextFileBtn = document.getElementById('next-file');
        this.nextDayBtn = document.getElementById('next-day');
        this.currentFileDisplay = document.getElementById('current-file-display');
    }
    
    bindEvents() {
        if (this.prevFileBtn) {
            this.prevFileBtn.addEventListener('click', () => this.navigatePreviousFile());
        }
        
        if (this.nextFileBtn) {
            this.nextFileBtn.addEventListener('click', () => this.navigateNextFile());
        }
        
        if (this.prevDayBtn) {
            this.prevDayBtn.addEventListener('click', () => this.navigatePreviousDay());
        }
        
        if (this.nextDayBtn) {
            this.nextDayBtn.addEventListener('click', () => this.navigateNextDay());
        }
    }
    
    bindStateEvents() {
        this.stateManager.addEventListener('statechange', (e) => {
            const { newState, oldState } = e.detail;
            
            // Update display when selection changes
            if (newState.selectedDate !== oldState.selectedDate ||
                newState.selectedTime !== oldState.selectedTime ||
                newState.currentFile !== oldState.currentFile) {
                this.updateDisplay();
                this.updateButtonStates();
            }
        });
    }
    
    updateDisplay() {
        const state = this.stateManager.getState();
        
        if (this.currentFileDisplay) {
            if (state.selectedDate && state.selectedTime) {
                const fileInfo = state.currentFile;
                if (fileInfo) {
                    this.currentFileDisplay.textContent = 
                        `${state.selectedDate} ${state.selectedTime} - ${fileInfo.filename}`;
                } else {
                    this.currentFileDisplay.textContent = 
                        `${state.selectedDate} ${state.selectedTime}`;
                }
            } else {
                this.currentFileDisplay.textContent = 'No file selected';
            }
        }
    }
    
    updateButtonStates() {
        const state = this.stateManager.getState();
        const hasSelection = state.selectedDate && state.selectedTime;
        
        // Enable/disable buttons based on selection
        if (this.prevFileBtn) this.prevFileBtn.disabled = !hasSelection;
        if (this.nextFileBtn) this.nextFileBtn.disabled = !hasSelection;
        if (this.prevDayBtn) this.prevDayBtn.disabled = !hasSelection;
        if (this.nextDayBtn) this.nextDayBtn.disabled = !hasSelection;
    }
    
    async navigatePreviousFile() {
        console.log('Navigation: Previous file clicked');
        if (this.mainApp && this.mainApp.navigatePrev) {
            console.log('Navigation: Calling mainApp.navigatePrev()');
            await this.mainApp.navigatePrev();
        } else {
            console.log('Navigation: mainApp.navigatePrev not available');
        }
    }
    
    async navigateNextFile() {
        console.log('Navigation: Next file clicked');
        if (this.mainApp && this.mainApp.navigateNext) {
            console.log('Navigation: Calling mainApp.navigateNext()');
            await this.mainApp.navigateNext();
        } else {
            console.log('Navigation: mainApp.navigateNext not available');
        }
    }
    
    async navigatePreviousDay() {
        console.log('Navigation: Previous day clicked');
        const state = this.stateManager.getState();
        if (!state.selectedDate || !state.selectedTime) {
            console.log('Navigation: No date/time selected');
            return;
        }
        
        try {
            this.stateManager.setLoading(true);
            
            const targetTime = state.selectedTime;
            const currentDate = new Date(state.selectedDate);
            
            // Find previous day with data
            const availableDates = state.availableDates || [];
            const currentDateIndex = availableDates.indexOf(state.selectedDate);
            
            console.log('Navigation: Current date index:', currentDateIndex, 'of', availableDates.length);
            console.log('Navigation: Available dates:', availableDates);
            
            if (currentDateIndex > 0) {
                const prevDate = availableDates[currentDateIndex - 1];
                console.log('Navigation: Looking for', targetTime, 'on', prevDate);
                
                // Try to find same time on previous day
                const file = await this.findFileAtTime(prevDate, targetTime);
                if (file) {
                    console.log('Navigation: Found exact time file:', file);
                    this.navigateToFile(file);
                } else {
                    // If exact time not found, find nearest time
                    const nearestFile = await this.findNearestTimeOnDate(prevDate, targetTime);
                    if (nearestFile) {
                        console.log('Navigation: Found nearest time file:', nearestFile);
                        this.navigateToFile(nearestFile);
                    } else {
                        console.log('Navigation: No files found on previous day');
                    }
                }
            } else {
                console.log('Navigation: Already at first day');
            }
            
        } catch (error) {
            console.warn('No previous day available:', error);
        } finally {
            this.stateManager.setLoading(false);
        }
    }
    
    async navigateNextDay() {
        const state = this.stateManager.getState();
        if (!state.selectedDate || !state.selectedTime) return;
        
        try {
            this.stateManager.setLoading(true);
            
            const targetTime = state.selectedTime;
            
            // Find next day with data
            const availableDates = state.availableDates || [];
            const currentDateIndex = availableDates.indexOf(state.selectedDate);
            
            if (currentDateIndex < availableDates.length - 1) {
                const nextDate = availableDates[currentDateIndex + 1];
                
                // Try to find same time on next day
                const file = await this.findFileAtTime(nextDate, targetTime);
                if (file) {
                    this.navigateToFile(file);
                } else {
                    // If exact time not found, find nearest time
                    const nearestFile = await this.findNearestTimeOnDate(nextDate, targetTime);
                    if (nearestFile) {
                        this.navigateToFile(nearestFile);
                    }
                }
            }
            
        } catch (error) {
            console.warn('No next day available:', error);
        } finally {
            this.stateManager.setLoading(false);
        }
    }
    
    async findFileAtTime(date, time) {
        try {
            const files = await ApiService.getFilesForDate(date);
            return files.find(file => file.time === time);
        } catch (error) {
            return null;
        }
    }
    
    async findNearestTimeOnDate(date, targetTime) {
        try {
            const files = await ApiService.getFilesForDate(date);
            if (files.length === 0) return null;
            
            // Convert target time to minutes for comparison
            const [targetHours, targetMinutes] = targetTime.split(':').map(Number);
            const targetTotalMinutes = targetHours * 60 + targetMinutes;
            
            // Find closest time
            let closestFile = files[0];
            let smallestDiff = Infinity;
            
            files.forEach(file => {
                const [hours, minutes] = file.time.split(':').map(Number);
                const totalMinutes = hours * 60 + minutes;
                const diff = Math.abs(totalMinutes - targetTotalMinutes);
                
                if (diff < smallestDiff) {
                    smallestDiff = diff;
                    closestFile = file;
                }
            });
            
            return closestFile;
        } catch (error) {
            return null;
        }
    }
    
    navigateToFile(fileInfo) {
        if (!fileInfo) {
            console.log('Navigation: No file info provided');
            return;
        }
        
        console.log('Navigation: Navigating to file:', fileInfo);
        
        // Use the main app's date picker for proper navigation
        const currentState = this.stateManager.getState();
        
        if (fileInfo.date !== currentState.selectedDate) {
            console.log('Navigation: Date change needed from', currentState.selectedDate, 'to', fileInfo.date);
            // Directly update state - don't use date picker for programmatic navigation
            console.log('Navigation: Updating state directly');
            this.stateManager.setState({
                selectedDate: fileInfo.date,
                selectedTime: fileInfo.time
            });
        } else {
            console.log('Navigation: Same date, just updating time to', fileInfo.time);
            // Same date - just update time
            this.stateManager.selectTime(fileInfo.time);
        }
    }
    
    /**
     * Destroy the navigation component
     */
    destroy() {
        // Event listeners are automatically removed when elements are destroyed
    }
}