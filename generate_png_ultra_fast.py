#!/usr/bin/env python3
"""
Ultra-fast PNG generation from NPZ data using PIL directly
No matplotlib overhead - should be 50-100x faster
"""

import os
import numpy as np
import yaml
import argparse
import time
from PIL import Image
from pathlib import Path
from filelock import FileLock, Timeout
from spectrogram_utils import find_all_spectrogram_files, load_spectrogram

def parse_arguments():
    parser = argparse.ArgumentParser(description="Generate ultra-fast PNG spectrograms from NPZ data")
    parser.add_argument("--config", "-c", required=True, help="YAML configuration file")
    parser.add_argument("--input", "-i", help="Input directory with NPZ files (overrides config)")
    parser.add_argument("--single-file", "-s", help="Process single NPZ file")
    parser.add_argument("--target", type=int, nargs='+', help="Target subset(s) (not used with --single-file)")
    parser.add_argument("--force", "-f", action="store_true", help="Force regeneration of existing PNGs")
    return parser.parse_args()

def load_config(config_path):
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)

def create_ultra_fast_png(npz_path, config, force=False):
    """Create PNG using PIL directly - ultra fast"""
    
    png_path = npz_path.replace('_spec.npz', '_spec.png')
    if os.path.exists(png_path) and not force:
        return "exists"
    
    try:
        # Load only the spec array, skip validation for speed
        with np.load(npz_path) as data:
            spec = data['spec']  # Shape: [n_mels, time_steps]
        
        # Get config values (cache these outside the function in production)
        vmin = config.get('global_min', -40)
        vmax = config.get('global_max', 40)
        width_px = config.get('width-px', 1000)
        height_px = config.get('height-px', 300)
        
        # Flip vertically for proper frequency orientation
        spec = np.flipud(spec)
        
        # Clip and normalize to 0-255 in one step
        spec_norm = np.clip((spec - vmin) / (vmax - vmin) * 255, 0, 255).astype(np.uint8)
        
        # Resize to exact pixel dimensions using PIL
        img = Image.fromarray(spec_norm, mode='L')  # 'L' = grayscale
        img_resized = img.resize((width_px, height_px), Image.NEAREST)
        
        # Save with minimal compression for speed
        img_resized.save(png_path, 'PNG', compress_level=1)
        
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
        
        # We need to find ALL files in scope first (including WAV files), then filter NPZ files by target
        # This matches the logic of other scripts where target is based on position in complete file list
        from spectrogram_utils import find_all_wav_files
        all_wav_files = find_all_wav_files(input_dir)  # All files in scope
        
        # Select NPZ files based on target indices using WAV file positions
        npz_files = []
        for wav_file in all_wav_files:
            file_index = all_wav_files.index(wav_file)
            if file_index % 10 in args.target:
                # Check if corresponding NPZ file exists
                npz_file = wav_file.replace('.WAV', '_spec.npz')
                if npz_file in all_npz_files:
                    npz_files.append(npz_file)
        
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
    start_time = time.time()
    
    for i, npz_file in enumerate(npz_files, 1):
        file_start_time = time.time()
        print(f"[{target_name}] [{i:4d}/{len(npz_files)}] {os.path.basename(npz_file)}...", end=" ")
        
        # Try to acquire file lock - skip immediately if locked
        lock_path = f"{npz_file}.lock"
        try:
            with FileLock(lock_path, timeout=0):
                result = create_ultra_fast_png(npz_file, config, args.force)
        except Timeout:
            # File is locked by another process, skip it
            result = "locked"
        
        file_end_time = time.time()
        file_duration = file_end_time - file_start_time
        
        if result == "created":
            created += 1
            print(f"✓ ({file_duration:.3f}s)")
        elif result == "exists":
            exists += 1
            print(f"(exists) ({file_duration:.3f}s)")
        elif result == "locked":
            print(f"(locked) ({file_duration:.3f}s)")
            continue
        else:
            errors += 1
            print(f"✗ {result} ({file_duration:.3f}s)")
    
    elapsed = time.time() - start_time
    rate = len(npz_files) / elapsed if elapsed > 0 else 0
    
    print(f"\n🎉 [{target_name}] Complete! {len(npz_files)} files in {elapsed:.1f}s ({rate:.1f} files/sec)")
    print(f"[{target_name}] Created: {created}, Exists: {exists}, Errors: {errors}")

if __name__ == "__main__":
    main()