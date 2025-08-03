#!/usr/bin/env python3
"""
Batch ACI Overlay Generation
Generate ACI overlays for AudioMoth WAV files following existing batch processing patterns
"""

import os
import glob
import torch
import yaml
import argparse
import time
import gc
import sqlite3
from aci_processor import ACIProcessor
from spectrogram_utils import find_all_wav_files


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Generate ACI overlays for audio files")
    parser.add_argument("--input", "-i", required=True, help="Input directory with audio files")
    parser.add_argument("--config", "-c", required=True, help="YAML configuration file")
    parser.add_argument("--target", type=int, nargs='+', required=True, help="Target subset(s): e.g. --target 0 1 2")
    parser.add_argument("--sample-pct", type=float, default=1.0, help="Percentage of files to process (default: 1.0)")
    return parser.parse_args()


def load_config(config_path):
    """Load configuration from YAML file"""
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)
    
    # Add default ACI parameters if not present
    config.setdefault('chunk_duration_sec', 4.5)
    config.setdefault('aci_normalization', 'percentile')
    config.setdefault('aci_output_suffix', '_aci_overlay')
    
    return config


def setup_device():
    """Setup processing device with GPU if available"""
    if torch.cuda.is_available():
        device = torch.device("cuda")
        print(f"✓ Using GPU: {torch.cuda.get_device_name()}")
        print("  (Image processing on GPU, ACI computation on CPU)")
        torch.cuda.empty_cache()
    else:
        device = torch.device("cpu")
        print("✓ Using CPU for processing")
    
    return device




def setup_database():
    """Database setup placeholder - removed ACI column creation"""
    db_path = "audiomoth.db"
    if not os.path.exists(db_path):
        print("ℹ️  Database not found - no database operations needed")
        return
    
    print("ℹ️  Database operations disabled - will use separate indices aggregation table later")


def main():
    """Main batch processing function"""
    args = parse_arguments()
    
    print("🎵 ACI Overlay Generation Starting...")
    print(f"Input directory: {args.input}")
    print(f"Configuration: {args.config}")
    print(f"Target groups: {args.target}")
    
    # Setup
    device = setup_device()
    config = load_config(args.config)
    setup_database()
    
    # Create ACI processor
    processor = ACIProcessor(config, device)
    
    # Find all WAV files
    print("\n📁 Finding WAV files...")
    all_wav_files = find_all_wav_files(args.input)
    print(f"Found {len(all_wav_files)} total WAV files")
    
    # Select files based on target indices (following spectrogram script pattern)
    wav_files = []
    for i, f in enumerate(all_wav_files):
        if i % 10 in args.target:
            wav_files.append(f)
    
    # Apply sample percentage if specified
    if args.sample_pct < 1.0:
        import random
        sample_size = max(1, int(len(wav_files) * args.sample_pct))
        wav_files = random.sample(wav_files, sample_size)
        print(f"Sampling {args.sample_pct*100:.1f}%: {len(wav_files)} files")
    
    target_str = "_".join(map(str, args.target))
    target_name = f"ACI_GROUP_{target_str}"
    
    print(f"\n🎯 Processing {target_name}: {len(wav_files)}/{len(all_wav_files)} files")
    
    if not wav_files:
        print("No WAV files found to process!")
        return
    
    # Process files
    created = 0
    exists = 0
    errors = 0
    start_time = time.time()
    
    for i, wav_file in enumerate(wav_files, 1):
        file_start_time = time.time()
        print(f"[{target_name}] [{i:4d}/{len(wav_files)}] {os.path.basename(wav_file)}...", end=" ")
        
        result = processor.process_single_file(wav_file)
        
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
        
        # Show progress every 5 files
        if i % 5 == 0:
            elapsed_total = file_end_time - start_time
            current_rate = i / elapsed_total if elapsed_total > 0 else 0
            
            # Memory cleanup
            gc.collect()
            if device.type == "cuda":
                torch.cuda.empty_cache()
            
            # Progress report every 10 files
            if i % 10 == 0:
                eta = (len(wav_files) - i) / current_rate if current_rate > 0 else 0
                progress_pct = i / len(wav_files) * 100
                print(f"  [{target_name}] Rate: {current_rate:.2f} files/sec - Progress: {i}/{len(wav_files)} ({progress_pct:.1f}%) - ETA: {eta/60:.1f}min")
    
    # Final statistics
    elapsed = time.time() - start_time
    rate = len(wav_files) / elapsed if elapsed > 0 else 0
    
    print(f"\n🎉 [{target_name}] Complete!")
    print(f"  Processed: {len(wav_files)} files in {elapsed/60:.1f} minutes ({rate:.1f} files/sec)")
    print(f"  Results: Created: {created}, Exists: {exists}, Errors: {errors}")
    
    print(f"ℹ️  Database storage disabled - overlay generation complete")


if __name__ == "__main__":
    main()