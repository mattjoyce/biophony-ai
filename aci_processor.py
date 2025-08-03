#!/usr/bin/env python3
"""
ACI (Acoustic Complexity Index) Processing Module
Modular processor for generating ACI overlays from AudioMoth WAV files
"""

import os
import torch
import torchaudio
import numpy as np
from PIL import Image
from maad import features, sound
import sqlite3


class ACIProcessor:
    """Core ACI processing functionality"""
    
    def __init__(self, config, device):
        """
        Initialize ACI processor
        
        Args:
            config: Configuration dictionary from YAML
            device: torch.device for GPU/CPU processing
        """
        self.config = config
        self.device = device
        
        # ACI processing parameters
        self.chunk_duration_sec = config.get('chunk_duration_sec', None)
        self.output_width_px = config.get('width-px', None)
        self.output_height_px = config.get('height-px', None)
        self.normalization_method = config.get('aci_normalization', 'percentile')
        self.output_suffix = config.get('aci_output_suffix', '_aci_overlay')
        
        # Audio parameters (from crib sheet)
        self.sample_rate = None
        self.file_duration_sec = None  # 15 minutes
        
        # Calculate chunk parameters
        self.samples_per_chunk = int(self.sample_rate * self.chunk_duration_sec)
        self.n_chunks = int(self.file_duration_sec / self.chunk_duration_sec)
        self.pixels_per_chunk = self.output_width_px // self.n_chunks
        
        print(f"ACI Processor initialized:")
        print(f"  Device: {self.device}")
        print(f"  Chunk duration: {self.chunk_duration_sec}s")
        print(f"  Chunks per file: {self.n_chunks}")
        print(f"  Pixels per chunk: {self.pixels_per_chunk}")
        print(f"  Output size: {self.output_width_px}x{self.output_height_px}px")
    
    def process_single_file(self, audio_file):
        """
        Process a single audio file to generate ACI overlay
        
        Args:
            audio_file: Path to WAV file
            
        Returns:
            str: "created", "exists", or "error: message"
        """
        # Generate output filename
        audio_dir = os.path.dirname(audio_file)
        audio_basename = os.path.basename(audio_file)
        png_filename = audio_basename.replace('.WAV', f'{self.output_suffix}.png').replace('.wav', f'{self.output_suffix}.png')
        output_file = os.path.join(audio_dir, png_filename)
        
        # Check if output already exists
        if os.path.exists(output_file):
            return "exists"
        
        # Load existing spectrogram image instead of recomputing
        spectrogram_file = audio_file.replace('.WAV', '.png').replace('.wav', '.png')
        if not os.path.exists(spectrogram_file):
            raise FileNotFoundError(f"Spectrogram image not found: {spectrogram_file}")
        
        # Load spectrogram image and move to device
        spectrogram_img = Image.open(spectrogram_file)
        if spectrogram_img.mode != 'L':
            spectrogram_img = spectrogram_img.convert('L')
        
        spectrogram_array = np.array(spectrogram_img)
        spectrogram_tensor = torch.from_numpy(spectrogram_array).float().to(self.device)
        
        # Validate spectrogram dimensions
        if spectrogram_tensor.shape != (self.output_height_px, self.output_width_px):
            raise ValueError(f"Spectrogram dimensions mismatch: {spectrogram_tensor.shape} != ({self.output_height_px}, {self.output_width_px})")
        
        # Compute ACI values from spectrogram chunks
        aci_values = self.compute_aci_from_spectrogram(spectrogram_tensor)
        
        # Normalize and render overlay
        self.normalize_and_render(aci_values, output_file)
        
        # Note: Database storage removed - will use separate indices aggregation table later
        return "created"
    
    def compute_aci_from_spectrogram(self, spectrogram_tensor):
        """
        Compute ACI values from spectrogram tensor chunks
        
        Args:
            spectrogram_tensor: 2D torch tensor (height, width) on device
            
        Returns:
            np.array: ACI values for each time chunk
        """
        height, width = spectrogram_tensor.shape
        
        # Validate dimensions
        if width != self.output_width_px:
            raise ValueError(f"Width mismatch: {width} != {self.output_width_px}")
        
        aci_values = []
        
        # Process spectrogram in time chunks (columns) using GPU operations
        for i in range(self.n_chunks):
            start_col = i * self.pixels_per_chunk
            end_col = start_col + self.pixels_per_chunk
            
            # Strict bounds checking
            if end_col > width:
                raise ValueError(f"Chunk {i} extends beyond spectrogram width: {end_col} > {width}")
            
            # Extract spectrogram chunk (all frequencies, time slice) on GPU
            chunk = spectrogram_tensor[:, start_col:end_col]
            
            # Validate chunk size
            if chunk.shape[1] != self.pixels_per_chunk:
                raise ValueError(f"Chunk {i} has unexpected width: {chunk.shape[1]} != {self.pixels_per_chunk}")
            
            # Convert to CPU numpy for maad processing (maad is CPU-only)
            # Normalize from [0,255] to [0,1] spectrogram amplitude
            chunk_cpu = (chunk / 255.0).cpu().numpy()
            
            # Compute ACI using scikit-maad - no error handling, fail immediately
            _, _, aci_sum = features.acoustic_complexity_index(chunk_cpu)
            aci_values.append(float(aci_sum))
        
        return np.array(aci_values)
    
    def normalize_and_render(self, aci_values, output_file):
        """
        Normalize ACI values and render as PNG overlay
        
        Args:
            aci_values: Array of ACI values
            output_file: Output PNG file path
        """
        # Validate input data
        if len(aci_values) == 0:
            raise ValueError("ACI values array is empty")
        
        if not np.isfinite(aci_values).all():
            raise ValueError("ACI values contain non-finite numbers")
        
        # Normalize to [0, 255] range - fail if range is invalid
        if self.normalization_method == 'percentile':
            p2 = np.percentile(aci_values, 2)
            p98 = np.percentile(aci_values, 98)
            if p98 <= p2:
                raise ValueError(f"Invalid percentile range: p2={p2}, p98={p98}")
            aci_clamped = np.clip(aci_values, p2, p98)
            aci_norm = (aci_clamped - p2) / (p98 - p2)
        else:
            # Min-max normalization
            aci_min, aci_max = aci_values.min(), aci_values.max()
            if aci_max <= aci_min:
                raise ValueError(f"Invalid ACI range: min={aci_min}, max={aci_max}")
            aci_norm = (aci_values - aci_min) / (aci_max - aci_min)
        
        # Scale to uint8
        aci_uint8 = (aci_norm * 255).astype(np.uint8)
        
        # Expand to pixel width (each chunk gets multiple pixels)
        aci_expanded = np.repeat(aci_uint8, self.pixels_per_chunk)
        
        # Strict size validation - must be exact
        expected_size = self.n_chunks * self.pixels_per_chunk
        if len(aci_expanded) != expected_size:
            raise ValueError(f"Expanded array size mismatch: {len(aci_expanded)} != {expected_size}")
        
        if len(aci_expanded) != self.output_width_px:
            raise ValueError(f"Output width mismatch: {len(aci_expanded)} != {self.output_width_px}")
        
        # Create grayscale image (1 pixel tall)
        overlay_1d = Image.fromarray(aci_expanded.reshape(1, -1), mode='L')
        
        # Resize to target height
        overlay = overlay_1d.resize((self.output_width_px, self.output_height_px), Image.Resampling.NEAREST)
        
        # Save PNG
        overlay.save(output_file)
    
