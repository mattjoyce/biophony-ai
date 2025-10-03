#!/usr/bin/env python3
"""
POI Strips service for AudioMoth Spectrogram Viewer
Generates PNG images for POI visualization strips
"""

import io
import os
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
import tempfile

from PIL import Image, ImageDraw
import numpy as np

from services.file_service import FileService
from services.spectrogram_service import SpectrogramService
from services.colormap_service import ColormapService


class POIStripsService:
    """Service for POI strips PNG generation"""
    
    STRIP_HEIGHT = 20
    STRIP_SPACING = 2
    
    @staticmethod
    def get_spectrogram_dimensions(date_str: str, time_str: str) -> Optional[Tuple[int, int]]:
        """Get dimensions of the original spectrogram PNG"""
        try:
            # Get the original spectrogram image
            image_file = SpectrogramService.get_spectrogram_image(date_str, time_str)
            if not image_file:
                return None
            
            # Load image and get dimensions
            img = Image.open(image_file)
            width, height = img.size
            image_file.close()
            
            return width, height
            
        except Exception as e:
            return None
    
    @staticmethod
    def get_poi_color(confidence: float, colormap: str) -> Tuple[int, int, int]:
        """Get RGB color for POI based on confidence and colormap"""
        # Binary high/low intensity based on confidence threshold
        is_high_confidence = confidence > 0.7  # 70% threshold
        
        # Color schemes matching spectrogram colormap exactly
        if colormap == 'viridis':
            # Viridis: purple (low) to yellow (high)
            return (253, 231, 37) if is_high_confidence else (68, 1, 84)
        elif colormap == 'plasma':
            # Plasma: purple (low) to bright pink/yellow (high)  
            return (240, 249, 33) if is_high_confidence else (13, 8, 135)
        elif colormap == 'inferno':
            # Inferno: black (low) to yellow (high)
            return (252, 255, 164) if is_high_confidence else (0, 0, 4)
        elif colormap == 'grayscale':
            # Grayscale: black (low) to white (high)
            return (255, 255, 255) if is_high_confidence else (0, 0, 0)
        else:
            # Default to viridis colors
            return (253, 231, 37) if is_high_confidence else (68, 1, 84)
    
    @staticmethod
    def generate_poi_strips_png(
        date_str: str, 
        time_str: str, 
        colormap: str = 'viridis'
    ) -> Optional[bytes]:
        """Generate POI strips PNG image matching spectrogram dimensions"""
        try:
            # Get spectrogram dimensions
            dimensions = POIStripsService.get_spectrogram_dimensions(date_str, time_str)
            if not dimensions:
                return None
            
            spec_width, spec_height = dimensions
            
            # Get POI data
            pois = FileService.get_pois_for_file(date_str, time_str)
            if not pois:
                # Return transparent PNG if no POIs
                return POIStripsService._create_empty_png(spec_width)
            
            # Get file duration
            file_info = FileService.get_file_by_datetime(date_str, time_str)
            if not file_info:
                return None
            
            duration_seconds = file_info.get('duration_seconds', 900)  # Default 15 minutes
            
            # Calculate total height needed
            total_height = len(pois) * (POIStripsService.STRIP_HEIGHT + POIStripsService.STRIP_SPACING)
            if total_height == 0:
                return POIStripsService._create_empty_png(spec_width)
            
            # Create image
            img = Image.new('RGBA', (spec_width, total_height), (0, 0, 0, 0))  # Transparent background
            draw = ImageDraw.Draw(img)
            
            # Draw each POI strip
            for i, poi in enumerate(pois):
                start_time = poi['start_time_sec']
                end_time = poi['end_time_sec']
                confidence = poi.get('confidence', 0.0)
                
                # Calculate pixel positions
                start_x = int((start_time / duration_seconds) * spec_width)
                end_x = int((end_time / duration_seconds) * spec_width)
                
                # Ensure minimum width for visibility
                if end_x - start_x < 2:
                    end_x = start_x + 2
                
                # Calculate Y position
                y_top = i * (POIStripsService.STRIP_HEIGHT + POIStripsService.STRIP_SPACING)
                y_bottom = y_top + POIStripsService.STRIP_HEIGHT
                
                # Get color based on confidence and colormap
                color = POIStripsService.get_poi_color(confidence, colormap)
                
                # Draw rectangle
                draw.rectangle(
                    [start_x, y_top, end_x, y_bottom], 
                    fill=color + (230,),  # Add alpha for slight transparency
                    outline=None
                )
            
            # Save to bytes
            output = io.BytesIO()
            img.save(output, format='PNG')
            output.seek(0)
            
            return output.getvalue()
            
        except Exception as e:
            # Return empty PNG on error
            return POIStripsService._create_empty_png(1000)  # Default width
    
    @staticmethod
    def _create_empty_png(width: int, height: int = 10) -> bytes:
        """Create empty transparent PNG"""
        img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        output = io.BytesIO()
        img.save(output, format='PNG')
        output.seek(0)
        return output.getvalue()