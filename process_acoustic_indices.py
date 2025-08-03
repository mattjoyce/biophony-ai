#!/usr/bin/env python3
"""
Acoustic Indices Processing Script
Separate processing for temporal (WAV) and spectral (NPZ) indices with sharding support
"""

import torch
import yaml
import argparse
import time
import gc
import os
from typing import List

from indices import TemporalIndicesProcessor, SpectralIndicesProcessor, DatabaseManager
from spectrogram_utils import find_all_wav_files


def parse_arguments():
    """Parse command line arguments with mutually exclusive processing types"""
    parser = argparse.ArgumentParser(description="Process acoustic indices from audio/spectrogram files")
    parser.add_argument("--input", "-i", required=True, help="Input directory with files")
    parser.add_argument("--config", "-c", required=True, help="YAML configuration file")
    parser.add_argument("--target", type=int, nargs='+', required=True, help="Target subset(s): e.g. --target 0 1 2")
    parser.add_argument("--force", action="store_true", help="Force reprocessing of existing files")
    
    # Mutually exclusive processing type flags
    processing_group = parser.add_mutually_exclusive_group(required=True)
    processing_group.add_argument("--TEMPORAL", action="store_true", 
                                help="Process temporal indices from WAV files")
    processing_group.add_argument("--SPECTRAL", action="store_true", 
                                help="Process spectral indices from NPZ spectrogram files")
    
    return parser.parse_args()


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file"""
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)


def setup_device() -> torch.device:
    """Setup processing device with GPU if available"""
    if torch.cuda.is_available():
        device = torch.device("cuda")
        print(f"✓ Using GPU: {torch.cuda.get_device_name()}")
        torch.cuda.empty_cache()
    else:
        device = torch.device("cpu")
        print("✓ Using CPU for processing")
    
    return device


def find_files_by_type(root_dir: str, processing_type: str) -> List[str]:
    """Find files based on processing type"""
    if processing_type == "temporal":
        files = find_all_wav_files(root_dir)
        print(f"Found {len(files)} WAV files for temporal processing")
        return files
    elif processing_type == "spectral":
        files = find_all_npz_files(root_dir)
        print(f"Found {len(files)} NPZ files for spectral processing")
        return files
    else:
        raise ValueError(f"Unknown processing type: {processing_type}")


def find_all_npz_files(root_dir: str) -> List[str]:
    """Find all NPZ spectrogram files recursively"""
    import glob
    pattern = os.path.join(root_dir, "**", "*_spec.npz")
    files = glob.glob(pattern, recursive=True)
    return sorted(files)


def filter_files_by_target(files: List[str], target_indices: List[int]) -> List[str]:
    """Filter files based on target subset indices"""
    filtered_files = []
    for i, file_path in enumerate(files):
        if i % 10 in target_indices:
            filtered_files.append(file_path)
    
    return filtered_files




def process_temporal_files(files: List[str], config: dict, target_name: str, force: bool = False) -> tuple:
    """Process temporal indices from WAV files"""
    processor = TemporalIndicesProcessor(config)
    db_manager = DatabaseManager()
    
    created = 0
    exists = 0
    errors = 0
    start_time = time.time()
    
    for i, wav_file in enumerate(files, 1):
        file_start_time = time.time()
        print(f"[{target_name}] [{i:4d}/{len(files)}] {os.path.basename(wav_file)}...", end=" ")
        
        # Check if indices already exist in database (unless force is enabled)
        existing_indices = db_manager.get_indices_for_file(wav_file, "temporal")
        if existing_indices and not force:
            exists += 1
            file_duration = time.time() - file_start_time
            print(f"(exists) ({file_duration:.1f}s)")
            continue
        elif existing_indices and force:
            # Delete existing data before reprocessing
            db_manager.delete_indices_for_file(wav_file, "temporal")
        
        # Process file
        indices_data = processor.process_file(wav_file)
        timestamps = processor.get_chunk_timestamps()
        
        # Store in database
        db_manager.store_indices(wav_file, "temporal", indices_data, timestamps)
        
        created += 1
        file_duration = time.time() - file_start_time
        print(f"✓ ({file_duration:.1f}s)")
        
        # Progress reporting and cleanup
        if i % 5 == 0:
            elapsed_total = time.time() - start_time
            current_rate = i / elapsed_total if elapsed_total > 0 else 0
            gc.collect()
            
            if i % 10 == 0:
                eta = (len(files) - i) / current_rate if current_rate > 0 else 0
                progress_pct = i / len(files) * 100
                print(f"  [{target_name}] Rate: {current_rate:.2f} files/sec - Progress: {i}/{len(files)} ({progress_pct:.1f}%) - ETA: {eta/60:.1f}min")
    
    return created, exists, errors


def process_spectral_files(files: List[str], config: dict, device: torch.device, target_name: str, force: bool = False) -> tuple:
    """Process spectral indices from NPZ files"""
    processor = SpectralIndicesProcessor(config, device)
    db_manager = DatabaseManager()
    
    created = 0
    exists = 0
    errors = 0
    start_time = time.time()
    
    for i, npz_file in enumerate(files, 1):
        file_start_time = time.time()
        print(f"[{target_name}] [{i:4d}/{len(files)}] {os.path.basename(npz_file)}...", end=" ")
        
        # Check if indices already exist in database (unless force is enabled)
        existing_indices = db_manager.get_indices_for_file(npz_file, "spectral")
        if existing_indices and len(existing_indices) > 0 and not force:
            exists += 1
            file_duration = time.time() - file_start_time
            print(f"(exists) ({file_duration:.1f}s)")
            continue
        elif existing_indices and len(existing_indices) > 0 and force:
            # Delete existing data before reprocessing
            db_manager.delete_indices_for_file(npz_file, "spectral")
        
        # Process file
        indices_data = processor.process_file(npz_file)
        timestamps = processor.get_chunk_timestamps()
        
        # Store in database
        db_manager.store_indices(npz_file, "spectral", indices_data, timestamps)
        
        created += 1
        file_duration = time.time() - file_start_time
        print(f"✓ ({file_duration:.1f}s)")
        
        # Progress reporting and cleanup
        if i % 5 == 0:
            elapsed_total = time.time() - start_time
            current_rate = i / elapsed_total if elapsed_total > 0 else 0
            
            # GPU cleanup for spectral processing
            if device.type == "cuda":
                torch.cuda.empty_cache()
            gc.collect()
            
            if i % 10 == 0:
                eta = (len(files) - i) / current_rate if current_rate > 0 else 0
                progress_pct = i / len(files) * 100
                print(f"  [{target_name}] Rate: {current_rate:.2f} files/sec - Progress: {i}/{len(files)} ({progress_pct:.1f}%) - ETA: {eta/60:.1f}min")
    
    return created, exists, errors


def main():
    """Main processing function"""
    args = parse_arguments()
    
    # Determine processing type
    processing_type = "temporal" if args.TEMPORAL else "spectral"
    
    print(f"🎵 Acoustic Indices Processing Starting...")
    print(f"Input directory: {args.input}")
    print(f"Configuration: {args.config}")
    print(f"Processing type: {processing_type.upper()}")
    print(f"Target groups: {args.target}")
    
    # Setup
    config = load_config(args.config)
    device = setup_device()
    
    # Find and filter files
    print(f"\n📁 Finding {processing_type} files...")
    all_files = find_files_by_type(args.input, processing_type)
    
    if not all_files:
        print(f"No {processing_type} files found!")
        return
    
    # Apply target filtering
    target_files = filter_files_by_target(all_files, args.target)
    
    target_str = "_".join(map(str, args.target))
    target_name = f"{processing_type.upper()}_GROUP_{target_str}"
    
    print(f"\n🎯 Processing {target_name}: {len(target_files)}/{len(all_files)} files")
    
    if not target_files:
        print("No files to process!")
        return
    
    # Process files based on type
    if processing_type == "temporal":
        created, exists, errors = process_temporal_files(target_files, config, target_name, args.force)
    else:  # spectral
        created, exists, errors = process_spectral_files(target_files, config, device, target_name, args.force)
    
    print(f"\n🎉 [{target_name}] Complete!")
    print(f"  Results: Created: {created}, Exists: {exists}, Errors: {errors}")


if __name__ == "__main__":
    main()