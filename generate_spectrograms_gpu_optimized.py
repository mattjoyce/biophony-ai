#!/usr/bin/env python3
"""
Optimized GPU spectrogram generation - raw spectral data only
Saves .npz files with unaltered mel spectrograms for scientific analysis
"""

import argparse
import gc
import glob
import os
import sqlite3
import time
from pathlib import Path

import numpy as np
import torch
import torchaudio
import torchaudio.transforms as T
import yaml
from filelock import FileLock, Timeout

from spectrogram_utils import (create_mel_frequency_vector, create_time_vector,
                               find_all_wav_files, save_spectrogram,
                               get_spectrogram_path_cross_platform)


def parse_arguments():
    """Parse command line arguments with comprehensive options"""
    parser = argparse.ArgumentParser(
        description="Generate spectrograms using GPU with integrated statistics calculation"
    )

    # Required arguments
    parser.add_argument("--config", "-c", required=True, help="YAML configuration file")

    # Input handling
    parser.add_argument(
        "--input",
        "-i",
        help="Input directory with audio files (optional - uses input_directory from config if not provided)",
    )
    parser.add_argument(
        "--single-file", "-s", help="Process a single WAV file instead of directory"
    )

    # Processing options
    parser.add_argument(
        "--target",
        type=int,
        nargs="+",
        help="Target subset(s): e.g. --target 0 1 2 (not used with --single-file)",
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force regeneration of existing NPZ files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without actually doing any work",
    )

    return parser.parse_args()


def load_config(config_path):
    """Load configuration from YAML file"""
    with open(config_path, "r") as file:
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


def setup_database_schema(config):
    """Add spectrogram statistics columns to database if they don't exist"""
    db_path = config.get("database_path")
    if not db_path:
        raise ValueError("❌ No database_path specified in config file")

    db_file = Path(db_path)
    if not db_file.exists():
        raise FileNotFoundError(f"❌ Database file not found: {db_path}")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Add columns for per-file spectrogram statistics
        columns_to_add = [
            ("spectrogram_min_abs", "REAL"),
            ("spectrogram_max_abs", "REAL"),
            ("spectrogram_min_p2", "REAL"),
            ("spectrogram_max_p98", "REAL"),
        ]

        for column_name, column_type in columns_to_add:
            try:
                cursor.execute(
                    f"ALTER TABLE audio_files ADD COLUMN {column_name} {column_type}"
                )
                print(f"✓ Added {column_name} column to database")
            except sqlite3.OperationalError:
                pass  # Column already exists

        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print(f"⚠️ Database schema update failed: {e}")


def store_file_statistics(filepath, stats, config, npz_path=None):
    """Store per-file spectrogram statistics and NPZ path in database"""
    db_path = config.get("database_path")
    if not db_path:
        raise ValueError("❌ No database_path specified in config file")

    db_file = Path(db_path)
    if not db_file.exists():
        raise FileNotFoundError(f"❌ Database file not found: {db_path}")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if npz_filepath column exists
        cursor.execute("PRAGMA table_info(audio_files)")
        columns = [col[1] for col in cursor.fetchall()]
        has_npz_column = 'npz_filepath' in columns
        
        if has_npz_column and npz_path:
            cursor.execute(
                """
            UPDATE audio_files 
            SET spectrogram_min = ?, spectrogram_max = ?, 
                npz_filepath = ?
            WHERE filepath = ?
            """,
                (
                    stats["min_abs"],
                    stats["max_abs"],
                    npz_path,
                    filepath,
                ),
            )
        else:
            # Fallback for databases without npz_filepath column or new schema
            cursor.execute(
                """
            UPDATE audio_files 
            SET spectrogram_min = ?, spectrogram_max = ?
            WHERE filepath = ?
            """,
                (
                    stats["min_abs"],
                    stats["max_abs"],
                    filepath,
                ),
            )

        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print(f"⚠️ Failed to store statistics for {os.path.basename(filepath)}: {e}")


def calculate_global_statistics(config):
    """Calculate and store global statistics from all per-file values"""
    db_path = config.get("database_path")
    if not db_path:
        raise ValueError("❌ No database_path specified in config file")

    db_file = Path(db_path)
    if not db_file.exists():
        raise FileNotFoundError(f"❌ Database file not found: {db_path}")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get all min/max values to calculate global percentiles
        cursor.execute(
            """
        SELECT spectrogram_min_abs, spectrogram_max_abs, spectrogram_min_p2, spectrogram_max_p98
        FROM audio_files 
        WHERE spectrogram_min_abs IS NOT NULL AND spectrogram_max_abs IS NOT NULL
        """
        )
        all_values = cursor.fetchall()

        if not all_values:
            print("⚠️ No per-file spectrogram statistics found")
            conn.close()
            return

        # Flatten all values for global percentile calculation
        all_db_values = []
        for row in all_values:
            all_db_values.extend(row)  # Add all 4 values from each file

        # Calculate global percentiles for better contrast
        global_min = np.percentile(all_db_values, 2)  # 2nd percentile
        global_max = np.percentile(all_db_values, 98)  # 98th percentile

        # Also calculate absolute range for comparison
        abs_min = min(all_db_values)
        abs_max = max(all_db_values)

        print(f"\n📊 Global Statistics from {len(all_values)} files:")
        print(
            f"  Absolute range: {abs_min:.2f} to {abs_max:.2f} dB ({abs_max - abs_min:.1f} dB)"
        )
        print(
            f"  Percentile range (2%-98%): {global_min:.2f} to {global_max:.2f} dB ({global_max - global_min:.1f} dB)"
        )

        # Create or update global_stats table
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS global_stats (
            id INTEGER PRIMARY KEY,
            stat_name TEXT UNIQUE,
            stat_value REAL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
        )

        # Insert or update global min/max
        cursor.execute(
            """
        INSERT OR REPLACE INTO global_stats (id, stat_name, stat_value, updated_at)
        VALUES (1, 'global_min', ?, CURRENT_TIMESTAMP)
        """,
            (global_min,),
        )

        cursor.execute(
            """
        INSERT OR REPLACE INTO global_stats (id, stat_name, stat_value, updated_at)
        VALUES (2, 'global_max', ?, CURRENT_TIMESTAMP)
        """,
            (global_max,),
        )

        conn.commit()
        conn.close()
        print("✓ Global statistics updated in database")

    except sqlite3.Error as e:
        print(f"⚠️ Failed to calculate global statistics: {e}")


def process_single_file(
    audio_file, mel_transform, config, device, freq_vector, force=False
):
    """Process one audio file - save raw spectral data"""

    # Generate NPZ output path using cross-platform logic
    try:
        output_file = get_spectrogram_path_cross_platform(config, audio_file)
    except Exception:
        # Fallback to original path construction if cross-platform fails
        audio_dir = os.path.dirname(audio_file)
        audio_basename = os.path.basename(audio_file)
        npz_filename = audio_basename.replace(".WAV", "_spec.npz").replace(
            ".wav", "_spec.npz"
        )
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

        # Calculate spectrogram statistics
        mel_flat = mel_spec_db.flatten()
        stats = {
            "min_abs": float(np.min(mel_flat)),
            "max_abs": float(np.max(mel_flat)),
            "min_p2": float(np.percentile(mel_flat, 2)),
            "max_p98": float(np.percentile(mel_flat, 98)),
        }

        # Create time vector
        hop_length = config.get("hop_length", 256)
        time_bins = create_time_vector(mel_spec_db.shape[1], hop_length, sample_rate)

        # Save using standardized utils
        save_spectrogram(
            output_path=output_file,
            spec=mel_spec_db,
            fn=freq_vector,
            time_bins=time_bins,
            sample_rate=sample_rate,
            n_fft=config.get("n_fft", 2048),
            hop_length=hop_length,
            n_mels=config.get("n_mels", 128),
            power=2.0,
            db_scale=True,
            normalization=False,
        )

        # Store statistics in database
        store_file_statistics(audio_file, stats, config, npz_path=output_file)

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

    # Setup database schema for statistics
    setup_database_schema(config)

    # Create frequency vector for mel scale
    n_fft = config.get("n_fft", 2048)
    n_mels = config.get("n_mels", 128)
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
            print("❌ --target is required when processing directories")
            return

        # Determine input directory: use --input if provided, otherwise fall back to config
        if args.input:
            input_dir = args.input
            input_source = "command line"
        else:
            input_dir = config.get("input_directory")
            if not input_dir:
                print(
                    "❌ No input directory specified. Use --input or set input_directory in config file."
                )
                return
            input_source = "config file"

        print(f"Input directory: {input_dir} (from {input_source})")

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

    # Show dry-run information if enabled
    if args.dry_run:
        print(f"\n🔍 DRY-RUN MODE: {len(wav_files)} files would be processed")
        print("  Operations that would be performed:")
        print("  - Generate mel spectrograms using GPU")
        print("  - Calculate 4 statistics per file (abs min/max, 2nd/98th percentiles)")
        print("  - Save NPZ files with spectral data")
        print("  - Store statistics in database")
        print("  - Calculate global statistics")
        print("🚀 Use without --dry-run to execute actual processing")
        return

    # Create mel transform
    mel_transform = T.MelSpectrogram(
        sample_rate=48000,
        n_fft=config.get("n_fft", 2048),
        hop_length=config.get("hop_length", 256),
        n_mels=config.get("n_mels", 128),
        power=2.0,
    ).to(device)

    # Process files
    created = 0
    exists = 0
    errors = 0
    start_time = time.time()
    last_file_time = start_time

    for i, wav_file in enumerate(wav_files, 1):
        file_start_time = time.time()
        print(
            f"[{target_name}] [{i:4d}/{len(wav_files)}] {os.path.basename(wav_file)}...",
            end=" ",
        )

        # Try to acquire file lock - skip immediately if locked
        lock_path = f"{wav_file}.lock"
        try:
            with FileLock(lock_path, timeout=0):
                result = process_single_file(
                    wav_file, mel_transform, config, device, freq_vector, args.force
                )
        except Timeout:
            # File is locked by another process, skip it
            result = "locked"

        file_end_time = time.time()
        file_duration = file_end_time - file_start_time

        if result == "created":
            created += 1
            print(f"✓ ({file_duration:.1f}s)")
        elif result == "exists":
            exists += 1
            print(f"(exists) ({file_duration:.1f}s)")
        elif result == "locked":
            print(f"(locked) ({file_duration:.3f}s)")
            continue
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
                print(
                    f"  [{target_name}] Rate: {current_rate:.2f} files/sec - Progress: {i}/{len(wav_files)} ({i/len(wav_files)*100:.1f}%) - ETA: {eta/60:.1f}min"
                )

    elapsed = time.time() - start_time
    rate = len(wav_files) / elapsed

    print(
        f"\n🎉 [{target_name}] Complete! {len(wav_files)} files in {elapsed/60:.1f} minutes ({rate:.1f} files/sec)"
    )
    print(
        f"[{target_name}] Created: {created} NPZ files, Exists: {exists}, Errors: {errors}"
    )

    # Calculate global statistics from all processed files
    if created > 0:
        print(f"\n📊 Calculating global statistics...")
        calculate_global_statistics(config)


if __name__ == "__main__":
    main()
