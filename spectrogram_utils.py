#!/usr/bin/env python3
"""
Standardized utilities for spectrogram data saving and loading
Ensures consistent format across all pipeline components
"""

import numpy as np
import os
import glob
from pathlib import Path
from typing import Dict, Tuple, Optional, Any, List, Union

# Required fields for spectrogram NPZ files
REQUIRED_FIELDS = {
    'spec',           # Raw mel spectrogram in dB scale
    'fn',             # Mel frequency centers in Hz
    'time_bins',      # Time bin centers in seconds
    'sample_rate',    # Original sample rate
    'n_fft',          # FFT window size
    'hop_length',     # Hop length in samples
    'n_mels',         # Number of mel bands
    'power',          # Power for spectrogram (typically 2.0)
    'db_scale',       # Whether dB scale is applied (True)
    'normalization'   # Whether normalization was applied (False for raw)
}

def save_spectrogram(
    output_path: str,
    spec: np.ndarray,
    fn: np.ndarray,
    time_bins: np.ndarray,
    sample_rate: int,
    n_fft: int,
    hop_length: int,
    n_mels: int,
    power: float = 2.0,
    db_scale: bool = True,
    normalization: bool = False
) -> None:
    """
    Save spectrogram data in standardized NPZ format
    
    Args:
        output_path: Path to save NPZ file
        spec: Mel spectrogram array [n_mels, time_steps] in dB scale
        fn: Mel frequency centers in Hz [n_mels]
        time_bins: Time bin centers in seconds [time_steps]
        sample_rate: Original audio sample rate
        n_fft: FFT window size
        hop_length: Hop length in samples
        n_mels: Number of mel frequency bands
        power: Power for spectrogram calculation
        db_scale: Whether dB scale was applied
        normalization: Whether any normalization was applied
    """
    
    # Validate inputs
    if spec.ndim != 2:
        raise ValueError(f"Spectrogram must be 2D, got shape {spec.shape}")
    
    if len(fn) != spec.shape[0]:
        raise ValueError(f"Frequency vector length {len(fn)} doesn't match spectrogram height {spec.shape[0]}")
    
    if len(time_bins) != spec.shape[1]:
        raise ValueError(f"Time bins length {len(time_bins)} doesn't match spectrogram width {spec.shape[1]}")
    
    if len(fn) != n_mels:
        raise ValueError(f"Frequency vector length {len(fn)} doesn't match n_mels {n_mels}")
    
    # Save with standardized format
    np.savez_compressed(
        output_path,
        spec=spec.astype(np.float32),
        fn=fn.astype(np.float32),
        time_bins=time_bins.astype(np.float64),
        sample_rate=np.array([sample_rate], dtype=np.int32),
        n_fft=np.array([n_fft], dtype=np.int32),
        hop_length=np.array([hop_length], dtype=np.int32),
        n_mels=np.array([n_mels], dtype=np.int32),
        power=np.array([power], dtype=np.float32),
        db_scale=np.array([db_scale], dtype=bool),
        normalization=np.array([normalization], dtype=bool)
    )

def load_spectrogram(npz_path: str, validate: bool = True) -> Dict[str, Any]:
    """
    Load spectrogram data from standardized NPZ format
    
    Args:
        npz_path: Path to NPZ file
        validate: Whether to validate required fields
        
    Returns:
        Dictionary containing all spectrogram data and metadata
    """
    
    if not os.path.exists(npz_path):
        raise FileNotFoundError(f"Spectrogram file not found: {npz_path}")
    
    try:
        data = np.load(npz_path)
        
        if validate:
            # Check required fields
            missing_fields = REQUIRED_FIELDS - set(data.files)
            if missing_fields:
                raise ValueError(f"Missing required fields: {missing_fields}")
            
            # Validate dimensions
            spec = data['spec']
            fn = data['fn']
            time_bins = data['time_bins']
            
            if spec.ndim != 2:
                raise ValueError(f"Invalid spectrogram shape: {spec.shape}")
                
            if len(fn) != spec.shape[0]:
                raise ValueError(f"Frequency vector length mismatch: {len(fn)} vs {spec.shape[0]}")
                
            if len(time_bins) != spec.shape[1]:
                raise ValueError(f"Time bins length mismatch: {len(time_bins)} vs {spec.shape[1]}")
        
        # Convert to standard format
        result = {
            'spec': data['spec'],
            'fn': data['fn'],
            'time_bins': data['time_bins'],
            'sample_rate': int(data['sample_rate'].item()),
            'n_fft': int(data['n_fft'].item()),
            'hop_length': int(data['hop_length'].item()),
            'n_mels': int(data['n_mels'].item()),
            'power': float(data['power'].item()),
            'db_scale': bool(data['db_scale'].item()),
            'normalization': bool(data['normalization'].item())
        }
        
        return result
        
    except Exception as e:
        raise RuntimeError(f"Failed to load spectrogram from {npz_path}: {e}")

def get_spectrogram_path(wav_path: str) -> str:
    """
    Get the corresponding spectrogram NPZ path for a WAV file
    
    Args:
        wav_path: Path to WAV file
        
    Returns:
        Path to corresponding NPZ file
    """
    base_path = wav_path.replace('.WAV', '').replace('.wav', '')
    return f"{base_path}_spec.npz"

def create_mel_frequency_vector(sample_rate: int, n_fft: int, n_mels: int) -> np.ndarray:
    """
    Create mel frequency centers in Hz
    
    Args:
        sample_rate: Audio sample rate
        n_fft: FFT window size  
        n_mels: Number of mel bands
        
    Returns:
        Array of mel frequency centers in Hz [n_mels]
    """
    # Get mel frequency edges in Hz - need n_mels+1 edges for n_mels centers
    mel_min = 0.0
    mel_max = 2595.0 * np.log10(1.0 + (sample_rate / 2.0) / 700.0)
    mel_points = np.linspace(mel_min, mel_max, n_mels + 1)
    hz_points = 700.0 * (10.0**(mel_points / 2595.0) - 1.0)
    
    # Return center frequencies between edges
    mel_centers = (hz_points[:-1] + hz_points[1:]) / 2.0
    return mel_centers  # Should be exactly n_mels length

def create_time_vector(n_time_steps: int, hop_length: int, sample_rate: int) -> np.ndarray:
    """
    Create time bin centers in seconds
    
    Args:
        n_time_steps: Number of time steps in spectrogram
        hop_length: Hop length in samples
        sample_rate: Audio sample rate
        
    Returns:
        Array of time bin centers in seconds
    """
    return np.arange(n_time_steps) * hop_length / sample_rate

def validate_spectrogram_format(data: Dict[str, Any]) -> bool:
    """
    Validate that spectrogram data follows the required format
    
    Args:
        data: Dictionary containing spectrogram data
        
    Returns:
        True if valid, raises exception if invalid
    """
    # Check required keys
    missing_keys = REQUIRED_FIELDS - set(data.keys())
    if missing_keys:
        raise ValueError(f"Missing required keys: {missing_keys}")
    
    # Check dimensions
    spec = data['spec']
    fn = data['fn'] 
    time_bins = data['time_bins']
    n_mels = data['n_mels']
    
    if spec.ndim != 2:
        raise ValueError(f"Spectrogram must be 2D, got {spec.ndim}D")
        
    if len(fn) != spec.shape[0]:
        raise ValueError(f"Frequency vector length {len(fn)} != spectrogram height {spec.shape[0]}")
        
    if len(time_bins) != spec.shape[1]:
        raise ValueError(f"Time vector length {len(time_bins)} != spectrogram width {spec.shape[1]}")
        
    if len(fn) != n_mels:
        raise ValueError(f"Frequency vector length {len(fn)} != n_mels {n_mels}")
    
    # Check data types and ranges
    if not data['db_scale']:
        raise ValueError("Spectrogram must be in dB scale for acoustic indices")
        
    if data['normalization']:
        raise ValueError("Spectrogram must not be normalized for acoustic indices")
    
    return True

def find_all_wav_files(root_dir: str) -> List[str]:
    """
    Find all WAV files recursively using pathlib
    
    Args:
        root_dir: Root directory to search
        
    Returns:
        Sorted list of WAV file paths as strings
    """
    root_path = Path(root_dir)
    wav_files = list(root_path.rglob("*.WAV"))
    return sorted([str(f) for f in wav_files])

def find_all_spectrogram_files(root_dir: str) -> List[str]:
    """
    Find all spectrogram files recursively using pathlib
    
    Args:
        root_dir: Root directory to search
        
    Returns:
        Sorted list of spectrogram file paths as strings
    """
    root_path = Path(root_dir)
    npz_files = list(root_path.rglob("*.npz"))
    return sorted([str(f) for f in npz_files])

def get_volume_prefix(config: Dict[str, Any]) -> str:
    """
    Extract volume prefix from config input_directory
    
    Args:
        config: Configuration dictionary containing input_directory
        
    Returns:
        Volume prefix string (e.g., "/Volumes/Extreme SSD", "/mnt/n/AudioWalks/H3-VC")
        
    Raises:
        ValueError: If input_directory not found in config
    """
    if 'input_directory' not in config:
        raise ValueError("input_directory not found in config")
    
    input_dir = config['input_directory'].rstrip('/')
    
    # Known volume prefixes for cross-platform support
    known_volumes = [
        "/Volumes/Extreme SSD",     # macOS
        "/mnt/n/AudioWalks/H3-VC",  # WSL
    ]
    
    for volume in known_volumes:
        if input_dir.startswith(volume):
            return volume
    
    # Fallback: use the input_directory as-is if no known volume matches
    return input_dir

def convert_to_relative_path(full_path: str, volume_prefix: str) -> str:
    """
    Convert absolute path to relative path by removing volume prefix
    
    Args:
        full_path: Full absolute path
        volume_prefix: Volume prefix to remove
        
    Returns:
        Relative path without volume prefix
    """
    full_path = full_path.rstrip('/')
    volume_prefix = volume_prefix.rstrip('/')
    
    if full_path.startswith(volume_prefix):
        relative_path = full_path[len(volume_prefix):].lstrip('/')
        return relative_path
    
    # If path doesn't start with volume prefix, return as-is
    return full_path

def resolve_cross_platform_path(config: Dict[str, Any], relative_path: str) -> str:
    """
    Resolve relative path to absolute path using config volume prefix
    
    Args:
        config: Configuration dictionary containing input_directory
        relative_path: Relative path to resolve
        
    Returns:
        Absolute path with volume prefix from config
    """
    volume_prefix = get_volume_prefix(config)
    relative_path = relative_path.lstrip('/')
    return os.path.join(volume_prefix, relative_path)

def get_spectrogram_path_cross_platform(config: Dict[str, Any], wav_path: str) -> str:
    """
    Get the corresponding spectrogram NPZ path for a WAV file (cross-platform)
    
    Args:
        config: Configuration dictionary for volume resolution
        wav_path: Path to WAV file (absolute or relative)
        
    Returns:
        Path to corresponding NPZ file with same volume context
    """
    # If wav_path is relative, resolve it first
    if not os.path.isabs(wav_path):
        wav_path = resolve_cross_platform_path(config, wav_path)
    
    # Convert to NPZ path
    base_path = wav_path.replace('.WAV', '').replace('.wav', '')
    return f"{base_path}_spec.npz"

def split_path_for_database(config: Dict[str, Any], full_path: str) -> Tuple[str, str]:
    """
    Split a full path into volume_prefix and relative_path for database storage
    
    Args:
        config: Configuration dictionary containing input_directory
        full_path: Full absolute path to split
        
    Returns:
        Tuple of (volume_prefix, relative_path) for database storage
    """
    volume_prefix = get_volume_prefix(config)
    relative_path = convert_to_relative_path(full_path, volume_prefix)
    return volume_prefix, relative_path

def reconstruct_path_from_database(volume_prefix: str, relative_path: str) -> str:
    """
    Reconstruct full path from database volume_prefix and relative_path
    
    Args:
        volume_prefix: Volume prefix from database
        relative_path: Relative path from database
        
    Returns:
        Full absolute path
    """
    relative_path = relative_path.lstrip('/')
    return os.path.join(volume_prefix, relative_path)