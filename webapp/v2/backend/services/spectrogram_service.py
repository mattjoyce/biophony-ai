#!/usr/bin/env python3
"""
Spectrogram service for AudioMoth Spectrogram Viewer
Handles spectrogram image processing and serving
"""

import io
import os
from pathlib import Path
from typing import Optional, Union, BinaryIO
import tempfile

from PIL import Image
import numpy as np

from services.file_service import FileService
from services.colormap_service import ColormapService

# Import cross-platform path utilities if available
try:
    from spectrogram_utils import reconstruct_path_from_database
    CROSS_PLATFORM_AVAILABLE = True
except ImportError:
    CROSS_PLATFORM_AVAILABLE = False


class SpectrogramService:
    """Service for spectrogram operations"""
    
    @staticmethod
    def get_spectrogram_image(date_str: str, time_str: str) -> Optional[BinaryIO]:
        """Return spectrogram image as bytes"""
        # Get file info for the datetime
        file_info = FileService.get_file_by_datetime(date_str, time_str)
        if not file_info:
            return None
        
        # Resolve filepath using cross-platform logic if available
        filepath = file_info['filepath']
        filename = file_info['filename']
        
        # Try to resolve cross-platform path if data is available
        if CROSS_PLATFORM_AVAILABLE:
            volume_prefix = file_info.get('volume_prefix')
            relative_path = file_info.get('relative_path')
            
            if volume_prefix and relative_path:
                try:
                    # Simple cross-platform resolution using stored volume prefix
                    # This works if the webapp is running on the same volume as stored
                    # For full cross-platform support, webapp would need config access
                    # to determine current environment's volume prefix
                    resolved_filepath = reconstruct_path_from_database(volume_prefix, relative_path)
                    if os.path.exists(resolved_filepath):
                        filepath = resolved_filepath
                except Exception:
                    pass  # Fall back to original filepath
        
        # Look for corresponding spectrogram PNG
        audio_dir = Path(filepath).parent
        base_name = Path(filename).stem
        
        # Try different spectrogram filename patterns
        patterns = [
            f"{base_name}_spec.png",
            f"{base_name}_aci_overlay.png",
            f"{base_name}.png"
        ]
        
        image_file = None
        for pattern in patterns:
            potential_file = audio_dir / pattern
            if potential_file.exists():
                image_file = potential_file
                break
        
        if not image_file:
            return None
        
        # Return file-like object
        return open(image_file, 'rb')
    
    @staticmethod
    def apply_colormap(image_data: bytes, colormap: str, gamma: float = 1.0) -> bytes:
        """Apply colormap and gamma correction to grayscale image"""
        try:
            # Load image from bytes
            img = Image.open(io.BytesIO(image_data))
            
            # Convert to grayscale if not already
            if img.mode != 'L':
                img = img.convert('L')
            
            # Convert to numpy array
            img_array = np.array(img)
            
            # Apply gamma correction if needed
            if gamma != 1.0:
                # Normalize to 0-1 range
                normalized = img_array.astype(np.float32) / 255.0
                # Apply gamma correction
                gamma_corrected = np.power(normalized, 1.0 / gamma)
                # Convert back to 0-255 range
                img_array = (gamma_corrected * 255).astype(np.uint8)
            
            # Apply colormap if not grayscale
            if colormap != 'grayscale':
                colormap_data = ColormapService.get_colormap(colormap)
                if colormap_data:
                    # Apply colormap
                    colored_array = np.zeros((img_array.shape[0], img_array.shape[1], 3), dtype=np.uint8)
                    for i in range(256):
                        mask = img_array == i
                        if np.any(mask):
                            color = colormap_data[i] if i < len(colormap_data) else [i, i, i]
                            colored_array[mask] = color
                    
                    # Convert back to PIL Image
                    result_img = Image.fromarray(colored_array, 'RGB')
                else:
                    # Fallback to grayscale
                    result_img = Image.fromarray(img_array, 'L')
            else:
                # Keep as grayscale
                result_img = Image.fromarray(img_array, 'L')
            
            # Save to bytes
            output = io.BytesIO()
            result_img.save(output, format='PNG')
            output.seek(0)
            
            return output.getvalue()
            
        except Exception as e:
            # Return original image data on error
            return image_data
    
    @staticmethod
    def get_spectrogram_with_processing(
        date_str: str, 
        time_str: str, 
        colormap: str = 'viridis', 
        gamma: float = 1.0
    ) -> Optional[bytes]:
        """Get spectrogram image with colormap and gamma processing applied"""
        # Get original image
        image_file = SpectrogramService.get_spectrogram_image(date_str, time_str)
        if not image_file:
            return None
        
        try:
            # Read image data
            image_data = image_file.read()
            image_file.close()
            
            # Apply processing if needed
            if colormap != 'grayscale' or gamma != 1.0:
                processed_data = SpectrogramService.apply_colormap(image_data, colormap, gamma)
                return processed_data
            
            return image_data
            
        except Exception as e:
            if hasattr(image_file, 'close'):
                image_file.close()
            return None