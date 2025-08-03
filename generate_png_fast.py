#!/usr/bin/env python3
"""
Fast PNG generation from existing NPZ spectral data
No axes, no borders, greyscale only, uses config power range for contrast
"""

import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import yaml
import argparse
import time
from pathlib import Path
from spectrogram_utils import find_all_spectrogram_files, load_spectrogram

# Use non-interactive backend for speed
matplotlib.use('Agg')

def parse_arguments():
    parser = argparse.ArgumentParser(description="Generate fast PNG spectrograms from NPZ data")
    parser.add_argument("--config", "-c", required=True, help="YAML configuration file")
    parser.add_argument("--input", "-i", help="Input directory with NPZ files (overrides config)")
    parser.add_argument("--single-file", "-s", help="Process single NPZ file")
    parser.add_argument("--target", type=int, nargs='+', help="Target subset(s) (not used with --single-file)")
    parser.add_argument("--force", "-f", action="store_true", help="Force regeneration of existing PNGs")
    return parser.parse_args()

def load_config(config_path):
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)

def create_fast_png(npz_path, config, force=False):
    """Create PNG from NPZ data - fast, no axes, greyscale"""
    
    # Check if PNG already exists
    png_path = npz_path.replace('_spec.npz', '_spec.png')
    if os.path.exists(png_path) and not force:
        return "exists"
    
    try:
        # Load spectral data
        data = load_spectrogram(npz_path)
        spec = data['spec']  # Already in dB scale
        
        # Apply contrast scaling from config
        vmin = config.get('global_min', -40)
        vmax = config.get('global_max', 40)
        
        # Get display dimensions from config
        width_px = config.get('width-px', 1000)
        height_px = config.get('height-px', 300)
        dpi = config.get('dpi', 100)
        
        # Calculate figure size in inches
        fig_width = width_px / dpi
        fig_height = height_px / dpi
        
        # Create figure with exact size, no margins
        fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=dpi)
        
        # Remove all axes, borders, margins
        ax.set_position([0, 0, 1, 1])
        ax.axis('off')
        
        # Display spectrogram (flip vertically for proper frequency orientation)
        ax.imshow(
            spec, 
            aspect='auto',
            origin='lower',
            cmap='gray',
            vmin=vmin,
            vmax=vmax,
            interpolation='nearest'
        )
        
        # Save with no padding
        plt.savefig(
            png_path,
            dpi=dpi,
            bbox_inches='tight',
            pad_inches=0,
            facecolor='black',
            edgecolor='none'
        )
        
        plt.close(fig)
        return "created"
        
    except Exception as e:
        return f"error: {e}"

def main():
    args = parse_arguments()
    config = load_config(args.config)
    
    # Handle single file mode
    if args.single_file:
        if not os.path.exists(args.single_file):
            print(f"✗ File not found: {args.single_file}")
            return
        npz_files = [args.single_file]
        target_name = "SINGLE_FILE"
        print(f"Processing single file: {os.path.basename(args.single_file)}")
    else:
        # Directory mode
        if not args.target:
            raise ValueError("--target is required when processing directories")
            
        # Determine input directory: CLI argument overrides config
        if args.input:
            input_dir = args.input
            print(f"✓ Using CLI input directory: {input_dir}")
        elif 'input_directory' in config:
            input_dir = config['input_directory']
            print(f"✓ Using config input directory: {input_dir}")
        else:
            raise ValueError("No input directory specified. Use --input or add 'input_directory' to config.")
        
        print(f"Finding NPZ files in: {input_dir}")
        all_npz_files = find_all_spectrogram_files(input_dir)
        
        # Select files based on target indices
        npz_files = []
        for i, f in enumerate(all_npz_files):
            if i % 10 in args.target:
                npz_files.append(f)
        
        target_str = "_".join(map(str, args.target))
        target_name = f"GROUP_{target_str}"
        
        print(f"Processing {target_name}: {len(npz_files)}/{len(all_npz_files)} NPZ files")
    
    if not npz_files:
        print("No NPZ files found!")
        return
    
    # Process files
    created = 0
    exists = 0
    errors = 0
    
    for i, npz_file in enumerate(npz_files, 1):
        file_start_time = time.time()
        print(f"[{target_name}] [{i:4d}/{len(npz_files)}] {os.path.basename(npz_file)}...", end=" ")
        
        result = create_fast_png(npz_file, config, args.force)
        
        file_end_time = time.time()
        file_duration = file_end_time - file_start_time
        
        if result == "created":
            created += 1
            print(f"✓ ({file_duration:.2f}s)")
        elif result == "exists":
            exists += 1
            print(f"(exists) ({file_duration:.2f}s)")
        else:
            errors += 1
            print(f"✗ {result} ({file_duration:.2f}s)")
    
    print(f"\n🎉 [{target_name}] Complete! Created: {created}, Exists: {exists}, Errors: {errors}")

if __name__ == "__main__":
    main()