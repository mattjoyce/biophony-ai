#!/usr/bin/env python3
"""
Generate mel-scale PNG images from linear-scale NPZ spectrograms
Converts linear spectrograms to mel scale for better visualization while preserving linear data for indices
"""

import os
import numpy as np
import argparse
import time
from PIL import Image
from pathlib import Path
import torch
import torchaudio.transforms as T
from config_utils import load_config
from spectrogram_utils import find_all_spectrogram_files, load_spectrogram, create_mel_frequency_vector

def parse_arguments():
    parser = argparse.ArgumentParser(description="Generate mel-scale PNG spectrograms from linear NPZ data")
    parser.add_argument("--config", "-c", required=True, help="YAML configuration file")
    parser.add_argument("--input", "-i", help="Input directory with NPZ files (overrides config)")
    parser.add_argument("--single-file", "-s", help="Process single NPZ file")
    parser.add_argument("--target", type=int, nargs='+', help="Target subset(s) (not used with --single-file)")
    parser.add_argument("--force", "-f", action="store_true", help="Force regeneration of existing PNGs")
    return parser.parse_args()

def setup_gpu():
    """Setup GPU device for mel conversion"""
    if torch.cuda.is_available():
        device = torch.device("cuda")
        print(f"✓ Using GPU: {torch.cuda.get_device_name()}")
        return device
    else:
        print("✓ Using CPU for mel conversion")
        return torch.device("cpu")

def linear_to_mel_conversion(linear_spec_db, sample_rate, n_fft, n_mels, device):
    """Convert linear spectrogram to mel scale using PyTorch"""
    
    # Convert back to power scale for mel conversion
    linear_spec_power = 10 ** (linear_spec_db / 10.0)
    
    # Create mel filterbank
    mel_fb = torchaudio.functional.melscale_fbanks(
        n_freqs=linear_spec_power.shape[0],
        f_min=0.0,
        f_max=sample_rate / 2.0,
        n_mels=n_mels,
        sample_rate=sample_rate
    ).T.to(device)
    
    # Apply mel filterbank to linear spectrogram
    linear_tensor = torch.tensor(linear_spec_power, device=device, dtype=torch.float32)
    mel_spec_power = torch.matmul(mel_fb, linear_tensor)
    
    # Convert back to dB
    mel_spec_db = 10 * torch.log10(mel_spec_power + 1e-10)  # Add epsilon to avoid log(0)
    
    return mel_spec_db.cpu().numpy()

def create_mel_png_from_linear(npz_path, config, device, force=False):
    """Create mel-scale PNG from linear NPZ spectrogram"""
    
    png_path = npz_path.replace('_spec.npz', '_mel_spec.png')
    if os.path.exists(png_path) and not force:
        return "exists"
    
    try:
        # Load linear spectrogram data
        data = load_spectrogram(npz_path, validate=False)
        linear_spec_db = data['spec']  # Shape: [n_freqs, time_steps]
        sample_rate = data['sample_rate']
        n_fft = data['n_fft']
        
        # Get mel parameters from config
        n_mels = config.get('n_mels', 128)
        
        # Convert linear to mel scale
        mel_spec_db = linear_to_mel_conversion(
            linear_spec_db, sample_rate, n_fft, n_mels, device
        )
        
        # Get config values for visualization
        vmin = config.get('global_min', -40)
        vmax = config.get('global_max', 40)
        width_px = config.get('width-px', 1000)
        height_px = config.get('height-px', 300)
        
        # Flip vertically for proper frequency orientation (high freq on top)
        mel_spec_db = np.flipud(mel_spec_db)
        
        # Clip and normalize to 0-255 in one step
        spec_norm = np.clip((mel_spec_db - vmin) / (vmax - vmin) * 255, 0, 255).astype(np.uint8)
        
        # Create PIL image and resize
        img = Image.fromarray(spec_norm, mode='L')  # 'L' = grayscale
        img_resized = img.resize((width_px, height_px), Image.LANCZOS)  # Use LANCZOS for better quality
        
        # Save PNG
        img_resized.save(png_path, 'PNG', compress_level=1)
        
        return "created"
        
    except Exception as e:
        return f"error: {e}"

def main():
    args = parse_arguments()
    config = load_config(args.config)
    device = setup_gpu()
    
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
            
        # Determine input directory
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
        
        # Select files based on target indices (matching the pattern from other scripts)
        npz_files = []
        for i, f in enumerate(all_npz_files):
            if i % 10 in args.target:
                npz_files.append(f)
        
        target_str = "_".join(map(str, args.target))
        target_name = f"GROUP_{target_str}"
        
        print(f"Processing {target_name}: {len(npz_files)}/{len(all_npz_files)} files")

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

        result = create_mel_png_from_linear(npz_file, config, device, args.force)
        
        file_end_time = time.time()
        file_duration = file_end_time - file_start_time

        if result == "created":
            created += 1
            print(f"✓ ({file_duration:.1f}s)")
        elif result == "exists":
            exists += 1
            print(f"(exists) ({file_duration:.1f}s)")
        else:
            errors += 1
            print(f"✗ {result} ({file_duration:.1f}s)")

        # Progress every 20 files
        if i % 20 == 0:
            elapsed = file_end_time - start_time
            rate = i / elapsed if elapsed > 0 else 0
            eta = (len(npz_files) - i) / rate if rate > 0 else 0
            print(f"  [{target_name}] Rate: {rate:.2f} files/sec - Progress: {i}/{len(npz_files)} ({i/len(npz_files)*100:.1f}%) - ETA: {eta/60:.1f}min")

    elapsed = time.time() - start_time
    rate = len(npz_files) / elapsed if elapsed > 0 else 0

    print(f"\n🎉 [{target_name}] Complete! {len(npz_files)} files in {elapsed/60:.1f} minutes ({rate:.1f} files/sec)")
    print(f"[{target_name}] Created: {created} mel PNGs, Exists: {exists}, Errors: {errors}")

if __name__ == "__main__":
    main()
