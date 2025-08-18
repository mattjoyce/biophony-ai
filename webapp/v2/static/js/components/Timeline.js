/**
 * Timeline Component for AudioMoth Spectrogram Viewer
 * Canvas-based timeline showing available audio files for selected date
 */

export class Timeline {
    constructor(containerId, stateManager) {
        this.container = document.getElementById(containerId);
        this.stateManager = stateManager;
        this.canvas = null;
        this.ctx = null;
        this.files = [];
        this.selectedTime = null;
        
        if (!this.container) {
            throw new Error(`Timeline container not found: ${containerId}`);
        }
        
        this.init();
        this.bindStateEvents();
    }
    
    init() {
        // Create canvas element
        this.canvas = document.createElement('canvas');
        this.canvas.style.cursor = 'pointer';
        this.canvas.style.display = 'block';
        
        this.container.appendChild(this.canvas);
        this.ctx = this.canvas.getContext('2d');
        
        // Store clickable areas for each file marker
        this.clickableAreas = [];
        
        // Create tooltip element
        this.tooltip = document.createElement('div');
        this.tooltip.style.cssText = `
            position: absolute;
            background: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 12px;
            font-family: monospace;
            pointer-events: none;
            z-index: 1000;
            display: none;
            white-space: nowrap;
        `;
        document.body.appendChild(this.tooltip);
        
        // Setup canvas sizing
        this.setupCanvas();
        
        // Bind events
        this.canvas.addEventListener('click', (e) => this.handleClick(e));
        this.canvas.addEventListener('mousemove', (e) => this.handleMouseMove(e));
        this.canvas.addEventListener('mouseleave', () => this.handleMouseLeave());
        
        // Handle resize
        window.addEventListener('resize', () => this.setupCanvas());
        
        // Initial render
        this.render();
    }
    
    setupCanvas() {
        const rect = this.container.getBoundingClientRect();
        
        // Account for container padding (15px on each side = 30px total)
        const availableWidth = rect.width - 30;
        const availableHeight = rect.height - 30;
        
        // Set canvas internal dimensions to match exact display size
        this.canvas.width = availableWidth;
        this.canvas.height = availableHeight;
        
        // Set CSS size to match internal dimensions (1:1 mapping)
        this.canvas.style.width = availableWidth + 'px';
        this.canvas.style.height = availableHeight + 'px';
        
        // Store dimensions
        this.canvasWidth = availableWidth;
        this.canvasHeight = availableHeight;
        
        console.log(`Timeline canvas: ${availableWidth}x${availableHeight}`);
        
        // Re-render after resize
        this.render();
    }
    
    bindStateEvents() {
        this.stateManager.addEventListener('statechange', (e) => {
            const { newState, oldState } = e.detail;
            
            // Update files when day files change
            if (newState.dayFiles !== oldState.dayFiles) {
                this.setFiles(newState.dayFiles);
            }
            
            // Update selection when time changes
            if (newState.selectedTime !== oldState.selectedTime) {
                this.selectedTime = newState.selectedTime;
                this.render();
            }
        });
    }
    
    setFiles(files) {
        this.files = files || [];
        this.render();
    }
    
    render() {
        if (!this.ctx) return;
        
        const width = this.canvasWidth;
        const height = this.canvasHeight;
        
        // Clear canvas
        this.ctx.clearRect(0, 0, width, height);
        
        if (this.files.length === 0) {
            this.renderEmptyState(width, height);
            return;
        }
        
        // Draw timeline base
        this.drawTimelineBase(width, height);
        
        // Draw time axis
        this.drawTimeAxis(width, height);
        
        // Draw file markers
        this.drawFileMarkers(width, height);
    }
    
    renderEmptyState(width, height) {
        this.ctx.fillStyle = '#999';
        this.ctx.font = '14px Arial';
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';
        this.ctx.fillText('No files available for selected date', width / 2, height / 2);
    }
    
    drawTimelineBase(width, height) {
        const y = height - 30;
        
        // Draw main timeline line
        this.ctx.strokeStyle = '#ccc';
        this.ctx.lineWidth = 2;
        this.ctx.beginPath();
        this.ctx.moveTo(0, y);
        this.ctx.lineTo(width, y);
        this.ctx.stroke();
    }
    
    drawTimeAxis(width, height) {
        const y = height - 30;
        
        // Draw hour markers
        for (let hour = 0; hour <= 24; hour += 6) {
            const x = (hour / 24) * width;
            
            // Draw tick mark
            this.ctx.strokeStyle = '#666';
            this.ctx.lineWidth = 1;
            this.ctx.beginPath();
            this.ctx.moveTo(x, y - 5);
            this.ctx.lineTo(x, y + 5);
            this.ctx.stroke();
            
            // Draw label
            this.ctx.fillStyle = '#666';
            this.ctx.font = '12px Arial';
            this.ctx.textAlign = 'center';
            this.ctx.textBaseline = 'top';
            this.ctx.fillText(`${hour.toString().padStart(2, '0')}:00`, x, y + 8);
        }
    }
    
    drawFileMarkers(width, height) {
        const y = height - 30;
        const radius = 6;
        
        // Clear clickable areas and rebuild them
        this.clickableAreas = [];
        
        this.files.forEach(file => {
            // Simple calculation: time as fraction of day * width
            const [hours, minutes] = file.time.split(':').map(Number);
            const minutesSinceMidnight = hours * 60 + minutes;
            const x = (minutesSinceMidnight / 1440) * width; // 1440 = 24 * 60 minutes in a day
            
            const isSelected = this.selectedTime === file.time;
            
            // Store clickable area
            this.clickableAreas.push({
                file: file,
                x: x,
                y: y,
                radius: 15  // Click tolerance
            });
            
            // Draw filled circle
            this.ctx.fillStyle = isSelected ? '#dc3545' : '#007bff';
            this.ctx.beginPath();
            this.ctx.arc(x, y, radius, 0, 2 * Math.PI);
            this.ctx.fill();
            
            // Draw white border (separate path)
            this.ctx.strokeStyle = '#fff';
            this.ctx.lineWidth = 2;
            this.ctx.beginPath();
            this.ctx.arc(x, y, radius, 0, 2 * Math.PI);
            this.ctx.stroke();
            
            // Draw selection ring if selected
            if (isSelected) {
                this.ctx.strokeStyle = '#dc3545';
                this.ctx.lineWidth = 2;
                this.ctx.beginPath();
                this.ctx.arc(x, y, radius + 3, 0, 2 * Math.PI);
                this.ctx.stroke();
            }
        });
    }
    
    handleClick(e) {
        const rect = this.canvas.getBoundingClientRect();
        const clickX = e.clientX - rect.left;
        const clickY = e.clientY - rect.top;
        
        // Direct click detection - canvas coordinates = screen coordinates (1:1)
        for (const area of this.clickableAreas) {
            const distance = Math.sqrt(
                Math.pow(clickX - area.x, 2) + 
                Math.pow(clickY - area.y, 2)
            );
            
            if (distance <= area.radius) {
                console.log(`✓ Clicked ${area.file.time}: click(${clickX.toFixed(1)}, ${clickY.toFixed(1)}) vs marker(${area.x.toFixed(1)}, ${area.y.toFixed(1)}) = ${distance.toFixed(1)}px`);
                this.stateManager.selectTime(area.file.time);
                return;
            }
        }
        
        console.log(`✗ No marker at (${clickX.toFixed(1)}, ${clickY.toFixed(1)})`);
    }
    
    handleMouseMove(e) {
        const rect = this.canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        
        // Direct hover detection - canvas coordinates = screen coordinates (1:1)
        let hoveringArea = null;
        
        for (const area of this.clickableAreas) {
            const distance = Math.sqrt(
                Math.pow(mouseX - area.x, 2) + 
                Math.pow(mouseY - area.y, 2)
            );
            
            if (distance <= area.radius) {
                hoveringArea = area;
                break;
            }
        }
        
        // Update cursor and tooltip
        if (hoveringArea) {
            this.canvas.style.cursor = 'pointer';
            this.showTooltip(e.clientX, e.clientY, hoveringArea.file);
        } else {
            this.canvas.style.cursor = 'default';
            this.hideTooltip();
        }
    }
    
    handleMouseLeave() {
        this.canvas.style.cursor = 'default';
        this.hideTooltip();
    }
    
    showTooltip(clientX, clientY, file) {
        const content = `${file.time} - ${file.filename.replace('.WAV', '')}<br>Duration: ${Math.round(file.duration_seconds / 60)}min`;
        this.tooltip.innerHTML = content;
        this.tooltip.style.display = 'block';
        
        // Get tooltip dimensions after content is set
        const tooltipRect = this.tooltip.getBoundingClientRect();
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        
        // Calculate horizontal position
        let leftPos = clientX + 10; // Default: 10px to the right of cursor
        
        // Check if tooltip extends off the right edge
        if (leftPos + tooltipRect.width > viewportWidth) {
            // Move tooltip to the left of cursor
            leftPos = clientX - tooltipRect.width - 10;
            
            // Ensure it doesn't go off the left edge
            if (leftPos < 0) {
                leftPos = 5; // 5px margin from left edge
            }
        }
        
        // Calculate vertical position
        let topPos = clientY - 40; // Default: 40px above cursor
        
        // Check if tooltip extends off the top edge
        if (topPos < 0) {
            topPos = clientY + 20; // Show below cursor instead
        }
        
        // Check if tooltip extends off the bottom edge
        if (topPos + tooltipRect.height > viewportHeight) {
            topPos = viewportHeight - tooltipRect.height - 5; // 5px margin from bottom
        }
        
        this.tooltip.style.left = leftPos + 'px';
        this.tooltip.style.top = topPos + 'px';
    }
    
    hideTooltip() {
        this.tooltip.style.display = 'none';
    }
    
    /**
     * Update selected time (called externally)
     * @param {string} time - Time string (HH:MM)
     */
    selectTime(time) {
        this.selectedTime = time;
        this.render();
    }
    
    /**
     * Get file at specific time
     * @param {string} time - Time string (HH:MM)
     * @returns {Object|null} File object or null
     */
    getFileAtTime(time) {
        return this.files.find(file => file.time === time) || null;
    }
    
    /**
     * Destroy the timeline component
     */
    destroy() {
        if (this.canvas && this.canvas.parentNode) {
            this.canvas.parentNode.removeChild(this.canvas);
        }
        if (this.tooltip && this.tooltip.parentNode) {
            this.tooltip.parentNode.removeChild(this.tooltip);
        }
        window.removeEventListener('resize', this.setupCanvas);
    }
}