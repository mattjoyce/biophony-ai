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
    parser.add_argument("--input", "-i", help="Input directory with files (optional - uses input_directory from config if not provided)")
    parser.add_argument("--config", "-c", required=True, help="YAML configuration file")
    parser.add_argument("--target", type=int, nargs='+', required=True, help="Target subset(s): e.g. --target 0 1 2")
    parser.add_argument("--force", action="store_true", help="Force reprocessing of existing files")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed without actually doing any work")
    
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


def create_dry_run_report(processing_type: str, config: dict, target_files: List[str], all_files: List[str]) -> None:
    """
    Create a detailed dry-run report showing what would be processed
    
    Args:
        processing_type: "temporal" or "spectral"
        config: Configuration dictionary
        target_files: Files that would be processed
        all_files: All files found
    """
    print(f"\n📊 DRY-RUN REPORT:")
    print(f"🎯 Processing type: {processing_type.upper()}")
    print(f"📁 Files found: {len(all_files)} total")
    print(f"🔍 Files in target: {len(target_files)} ({len(target_files)/len(all_files)*100:.1f}%)")
    
    # Get enabled indices from config
    indices_config = config.get('acoustic_indices', {}).get(processing_type, {})
    
    if 'enabled' in indices_config:
        # Legacy format
        enabled_indices = indices_config.get('enabled', [])
        print(f"📋 Indices (legacy format): {len(enabled_indices)}")
        for idx in enabled_indices:
            print(f"   - {idx}")
    else:
        # New generalized format
        named_indices = {k: v for k, v in indices_config.items() 
                        if isinstance(v, dict) and 'processor' in v}
        print(f"📋 Named indices (generalized format): {len(named_indices)}")
        for name, idx_config in named_indices.items():
            processor = idx_config['processor']
            params = idx_config.get('params', {})
            print(f"   - {name}: {processor} {params}")
    
    # Estimate processing time (rough estimate: 3-5 seconds per file per index)
    if target_files:
        indices_count = len(enabled_indices) if 'enabled' in indices_config else len(named_indices)
        if indices_count > 0:
            avg_time_per_file = 4.0  # seconds (rough estimate)
            total_time_sec = len(target_files) * avg_time_per_file
            total_time_min = total_time_sec / 60
            print(f"⏱️  Estimated processing time: {total_time_min:.1f} minutes")
        else:
            print(f"⚠️  No indices configured - nothing would be processed!")
    
    print(f"💾 Database writes: DISABLED (dry-run mode)")
    print(f"🚀 Use without --dry-run to execute actual processing")




def process_temporal_files(files: List[str], config: dict, target_name: str, force: bool = False, dry_run: bool = False) -> tuple:
    """Process temporal indices from WAV files"""
    processor = TemporalIndicesProcessor(config)
    db_manager = DatabaseManager()
    
    # Get the specific indices that would be created by this processor
    # Temporal indices typically use their cosmetic name as database name
    expected_indices = processor.get_enabled_indices()
    
    created = 0
    exists = 0
    errors = 0
    start_time = time.time()
    
    # Bulk preload existing indices for all target files (single database query)
    print(f"🔍 Preloading existing indices for {len(files)} files...")
    preload_start = time.time()
    existing_indices_bulk = db_manager.get_indices_for_files_bulk(files, "temporal", expected_indices)
    preload_time = time.time() - preload_start
    print(f"✓ Preloaded in {preload_time:.1f}s - found indices for {len(existing_indices_bulk)} files")
    
    for i, wav_file in enumerate(files, 1):
        file_start_time = time.time()
        print(f"[{target_name}] [{i:4d}/{len(files)}] {os.path.basename(wav_file)}...", end=" ")
        
        # Check if the specific indices we want to create already exist (using preloaded data)
        existing_indices = existing_indices_bulk.get(wav_file, {})
        indices_exist = len(existing_indices) > 0
        
        if indices_exist and not force:
            exists += 1
            file_duration = time.time() - file_start_time
            existing_names = list(existing_indices.keys())
            print(f"(exists: {existing_names}) ({file_duration:.1f}s)")
            continue
        elif indices_exist and force:
            if not dry_run:
                # Delete existing specific indices before reprocessing (only if not dry-run)
                for index_name in expected_indices:
                    if index_name in existing_indices:
                        # Note: delete_indices_for_file deletes ALL indices for file+type, not specific ones
                        # This is a limitation of the current DatabaseManager API
                        pass
        
        if dry_run:
            # Dry-run mode: just show what would be processed
            created += 1
            file_duration = time.time() - file_start_time
            enabled_indices = processor.get_enabled_indices()
            print(f"[DRY-RUN] would process {len(enabled_indices)} indices ({file_duration:.1f}s)")
        else:
            # Normal processing mode
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


def process_spectral_files(files: List[str], config: dict, device: torch.device, target_name: str, force: bool = False, dry_run: bool = False) -> tuple:
    """Process spectral indices from NPZ files"""
    processor = SpectralIndicesProcessor(config, device)
    db_manager = DatabaseManager()
    
    # Get the specific indices that would be created by this processor
    if hasattr(processor, 'named_indices') and processor.named_indices:
        # New format: get database names for named indices
        expected_indices = []
        for name, idx_config in processor.named_indices.items():
            processor_name = idx_config['processor']
            params = idx_config.get('params', {})
            db_name = processor._generate_database_name(name, processor_name, params)
            expected_indices.append(db_name)
    else:
        # Legacy format: get enabled indices with frequency encoding
        expected_indices = []
        for index_name in processor.enabled_indices:
            if index_name == 'bioacoustics_index':
                db_name = f"standard_bai_{int(processor.bioacoustics_freq_min)}-{int(processor.bioacoustics_freq_max)}"
            elif index_name == 'soundscape_index':
                db_name = f"standard_soundscape_{int(processor.bioacoustics_freq_min)}-{int(processor.bioacoustics_freq_max)}"
            else:
                db_name = index_name
            expected_indices.append(db_name)
    
    created = 0
    exists = 0
    errors = 0
    start_time = time.time()
    
    # Bulk preload existing indices for all target files (single database query)
    print(f"🔍 Preloading existing indices for {len(files)} files...")
    preload_start = time.time()
    existing_indices_bulk = db_manager.get_indices_for_files_bulk(files, "spectral", expected_indices)
    preload_time = time.time() - preload_start
    print(f"✓ Preloaded in {preload_time:.1f}s - found indices for {len(existing_indices_bulk)} files")
    
    for i, npz_file in enumerate(files, 1):
        file_start_time = time.time()
        print(f"[{target_name}] [{i:4d}/{len(files)}] {os.path.basename(npz_file)}...", end=" ")
        
        # Check if the specific indices we want to create already exist (using preloaded data)
        existing_indices = existing_indices_bulk.get(npz_file, {})
        indices_exist = len(existing_indices) > 0
        
        if indices_exist and not force:
            exists += 1
            file_duration = time.time() - file_start_time
            existing_names = list(existing_indices.keys())
            print(f"(exists: {existing_names}) ({file_duration:.1f}s)")
            continue
        elif indices_exist and force:
            if not dry_run:
                # Delete existing specific indices before reprocessing (only if not dry-run)
                for index_name in expected_indices:
                    if index_name in existing_indices:
                        # Note: delete_indices_for_file deletes ALL indices for file+type, not specific ones
                        # This is a limitation of the current DatabaseManager API
                        pass
        
        if dry_run:
            # Dry-run mode: just show what would be processed
            created += 1
            file_duration = time.time() - file_start_time
            enabled_indices = processor.get_enabled_indices()
            print(f"[DRY-RUN] would process {len(enabled_indices)} indices ({file_duration:.1f}s)")
        else:
            # Normal processing mode
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
    
    # Setup
    config = load_config(args.config)
    
    # Determine input directory: use --input if provided, otherwise fall back to config
    if args.input:
        input_directory = args.input
        input_source = "command line"
    else:
        input_directory = config.get('input_directory')
        if not input_directory:
            print("❌ No input directory specified. Use --input or set input_directory in config file.")
            return
        input_source = "config file"
    
    dry_run_text = " (DRY-RUN MODE)" if args.dry_run else ""
    print(f"🎵 Acoustic Indices Processing Starting...{dry_run_text}")
    print(f"Input directory: {input_directory} (from {input_source})")
    print(f"Configuration: {args.config}")
    print(f"Processing type: {processing_type.upper()}")
    print(f"Target groups: {args.target}")
    if args.dry_run:
        print(f"🔍 Dry-run mode: No actual processing or database writes will occur")
    device = setup_device()
    
    # Find and filter files
    print(f"\n📁 Finding {processing_type} files...")
    all_files = find_files_by_type(input_directory, processing_type)
    
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
    
    # Show dry-run report if in dry-run mode
    if args.dry_run:
        create_dry_run_report(processing_type, config, target_files, all_files)
    
    # Process files based on type
    if processing_type == "temporal":
        created, exists, errors = process_temporal_files(target_files, config, target_name, args.force, args.dry_run)
    else:  # spectral
        created, exists, errors = process_spectral_files(target_files, config, device, target_name, args.force, args.dry_run)
    
    dry_run_suffix = " (DRY-RUN)" if args.dry_run else ""
    print(f"\n🎉 [{target_name}] Complete{dry_run_suffix}!")
    if args.dry_run:
        print(f"  Results: Would create: {created}, Exists: {exists}, Errors: {errors}")
        print(f"  💡 Run without --dry-run to execute actual processing")
    else:
        print(f"  Results: Created: {created}, Exists: {exists}, Errors: {errors}")


if __name__ == "__main__":
    main()