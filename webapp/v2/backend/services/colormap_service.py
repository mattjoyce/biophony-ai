#!/usr/bin/env python3
"""
Colormap service for AudioMoth Spectrogram Viewer
Handles colormap generation and caching
"""

from typing import Optional, List, Dict, Any
import numpy as np
import matplotlib.pyplot as plt
from functools import lru_cache


class ColormapService:
    """Service for colormap operations with caching"""
    
    # Cache for colormap data to avoid repeated matplotlib imports
    _colormap_cache: Dict[str, List[List[int]]] = {}
    
    @staticmethod
    @lru_cache(maxsize=32)
    def get_colormap(colormap_name: str) -> Optional[List[List[int]]]:
        """Get matplotlib colormap as RGB array with caching"""
        # Check cache first
        if colormap_name in ColormapService._colormap_cache:
            return ColormapService._colormap_cache[colormap_name]
        
        # Handle grayscale special case
        if colormap_name in ['gray', 'grayscale']:
            return None
        
        try:
            # Get the colormap from matplotlib
            cmap = plt.get_cmap(colormap_name)
            
            # Sample 256 colors from the colormap
            colors = []
            for i in range(256):
                rgba = cmap(i / 255.0)
                # Convert to RGB (0-255)
                rgb = [int(rgba[0] * 255), int(rgba[1] * 255), int(rgba[2] * 255)]
                colors.append(rgb)
            
            # Cache the result
            ColormapService._colormap_cache[colormap_name] = colors
            
            return colors
            
        except (ValueError, AttributeError):
            # Invalid colormap name
            return None
    
    @staticmethod
    def get_available_colormaps() -> List[str]:
        """Get list of available colormap names"""
        return [
            'viridis', 'plasma', 'inferno', 'magma', 'cividis',
            'jet', 'hot', 'cool', 'spring', 'summer', 'autumn', 'winter',
            'copper', 'bone', 'pink', 'gray', 'seismic', 'RdYlBu', 
            'Spectral', 'coolwarm'
        ]
    
    @staticmethod
    def clear_cache() -> None:
        """Clear colormap cache"""
        ColormapService._colormap_cache.clear()
        ColormapService.get_colormap.cache_clear()
    
    @staticmethod
    def get_mel_scale_data(
        sample_rate: int = 48000,
        n_mels: int = 128,
        fmin: float = 0,
        fmax: Optional[float] = None
    ) -> Dict[str, Any]:
        """Get mel scale frequency mapping for spectrograms"""
        if fmax is None:
            fmax = sample_rate // 2
        
        def hz_to_mel(hz):
            return 2595 * np.log10(1 + hz / 700)
        
        def mel_to_hz(mel):
            return 700 * (10**(mel / 2595) - 1)
        
        # Create mel scale points
        mel_min = hz_to_mel(fmin)
        mel_max = hz_to_mel(fmax)
        mel_points = np.linspace(mel_min, mel_max, n_mels + 1)
        
        # Convert back to Hz
        freq_points = [mel_to_hz(mel) for mel in mel_points]
        
        # Create mapping for pixel positions
        scale_data = []
        for i, freq in enumerate(freq_points):
            pixel_y = i  # Y position from bottom of spectrogram
            scale_data.append({
                'pixel_y': pixel_y,
                'frequency_hz': round(freq, 1),
                'frequency_khz': round(freq / 1000, 2)
            })
        
        return {
            'scale_data': scale_data,
            'sample_rate': sample_rate,
            'n_mels': n_mels,
            'fmin': fmin,
            'fmax': fmax
        }