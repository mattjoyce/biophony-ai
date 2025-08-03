#!/usr/bin/env python3
"""
Optimized GPU spectrogram generation - raw spectral data only
Saves .npz files with unaltered mel spectrograms for scientific analysis
"""

import os
import glob
import torch
import torchaudio
import torchaudio.transforms as T
import numpy as np
import yaml
import argparse
import time
import gc
from spectrogram_utils import save_spectrogram, create_mel_frequency_vector, create_time_vector, find_all_wav_files

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Generate spectrograms using GPU (optimized)")
    parser.add_argument("--input", "-i", help="Input directory with audio files (overrides config)")
    parser.add_argument("--single-file", "-s", help="Process a single WAV file instead of directory")
    parser.add_argument("--config", "-c", required=True, help="YAML configuration file")
    parser.add_argument("--target", type=int, nargs='+', help="Target subset(s) (not used with --single-file)")
    parser.add_argument("--force", "-f", action="store_true", help="Force regeneration of existing NPZ files")
    return parser.parse_args()

def load_config(config_path):
    """Load configuration from YAML file"""
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)

def setup_gpu():
    """Setup GPU device"""
    if torch.cuda.is_available():
        device = torch.device("cuda")
        print(f"✓ Using GPU: {torch.cuda.get_device_name()}")
        torch.cuda.empty_cache()
        return device
    else:
        print("✗ CUDA not available, using CPU")
        return torch.device("cpu")


def process_single_file(audio_file, mel_transform, config, device, freq_vector, force=False):
    """Process one audio file - save raw spectral data"""
    
    # Check if NPZ already exists
    audio_dir = os.path.dirname(audio_file)
    audio_basename = os.path.basename(audio_file)
    npz_filename = audio_basename.replace('.WAV', '_spec.npz').replace('.wav', '_spec.npz')
    output_file = os.path.join(audio_dir, npz_filename)
    
    if os.path.exists(output_file) and not force:
        return "exists"
    
    try:
        # Load audio and move to GPU
        waveform, sample_rate = torchaudio.load(audio_file)
        waveform = waveform.to(device)
        
        # Generate spectrogram on GPU
        mel_spec = mel_transform(waveform)
        mel_spec_db = T.AmplitudeToDB()(mel_spec)
        
        # Move to CPU and convert to numpy
        mel_spec_db = mel_spec_db.cpu().numpy()
        if len(mel_spec_db.shape) == 3:
            mel_spec_db = mel_spec_db[0]  # Remove batch dimension
        
        # Create time vector
        hop_length = config.get('hop_length', 256)
        time_bins = create_time_vector(mel_spec_db.shape[1], hop_length, sample_rate)
        
        # Save using standardized utils
        save_spectrogram(
            output_path=output_file,
            spec=mel_spec_db,
            fn=freq_vector,
            time_bins=time_bins,
            sample_rate=sample_rate,
            n_fft=config.get('n_fft', 2048),
            hop_length=hop_length,
            n_mels=config.get('n_mels', 128),
            power=2.0,
            db_scale=True,
            normalization=False
        )
        
        # Cleanup
        del waveform, mel_spec, mel_spec_db
        
        return "created"
        
    except Exception as e:
        return f"error: {e}"


def main():
    args = parse_arguments()
    
    # Setup
    device = setup_gpu()
    config = load_config(args.config)
    
    # Create frequency vector for mel scale
    n_fft = config.get('n_fft', 2048)
    n_mels = config.get('n_mels', 128)
    freq_vector = create_mel_frequency_vector(48000, n_fft, n_mels)
    
    # Handle single file mode
    if args.single_file:
        if not os.path.exists(args.single_file):
            print(f"✗ File not found: {args.single_file}")
            return
        
        wav_files = [args.single_file]
        target_name = "SINGLE_FILE"
        print(f"Processing single file: {os.path.basename(args.single_file)}")
    
    else:
        # Directory mode (original logic)
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
        
        # Find files
        print("Finding WAV files...")
        all_wav_files = find_all_wav_files(input_dir)
        
        # Select files based on target indices
        wav_files = []
        for i, f in enumerate(all_wav_files):
            if i % 10 in args.target:
                wav_files.append(f)
        
        target_str = "_".join(map(str, args.target))
        target_name = f"GROUP_{target_str}"
        
        print(f"Processing {target_name}: {len(wav_files)}/{len(all_wav_files)} files")
    
    if not wav_files:
        print("No WAV files found!")
        return
    
    # Create mel transform
    mel_transform = T.MelSpectrogram(
        sample_rate=48000,
        n_fft=config.get('n_fft', 2048),
        hop_length=config.get('hop_length', 256),
        n_mels=config.get('n_mels', 128),
        power=2.0
    ).to(device)
    
    # Process files
    created = 0
    exists = 0
    errors = 0
    start_time = time.time()
    last_file_time = start_time
    
    for i, wav_file in enumerate(wav_files, 1):
        file_start_time = time.time()
        print(f"[{target_name}] [{i:4d}/{len(wav_files)}] {os.path.basename(wav_file)}...", end=" ")
        
        result = process_single_file(wav_file, mel_transform, config, device, freq_vector, args.force)
        
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
        
        # Show current rate every file
        elapsed_total = file_end_time - start_time
        current_rate = i / elapsed_total if elapsed_total > 0 else 0
        
        # Cleanup every 5 files
        if i % 5 == 0:
            if device.type == "cuda":
                torch.cuda.empty_cache()
            gc.collect()
            
            # Progress every 10 files
            if i % 10 == 0:
                eta = (len(wav_files) - i) / current_rate if current_rate > 0 else 0
                print(f"  [{target_name}] Rate: {current_rate:.2f} files/sec - Progress: {i}/{len(wav_files)} ({i/len(wav_files)*100:.1f}%) - ETA: {eta/60:.1f}min")
    
    elapsed = time.time() - start_time
    rate = len(wav_files) / elapsed
    
    print(f"\n🎉 [{target_name}] Complete! {len(wav_files)} files in {elapsed/60:.1f} minutes ({rate:.1f} files/sec)")
    print(f"[{target_name}] Created: {created} NPZ files, Exists: {exists}, Errors: {errors}")

if __name__ == "__main__":
    main()