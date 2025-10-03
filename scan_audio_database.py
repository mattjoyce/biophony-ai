#!/usr/bin/env python3
"""
AudioMoth Database Scanner
Scans directories for WAV files and populates database with AudioMoth metadata
"""

import os
import sys
import argparse
import yaml
import sqlite3
from pathlib import Path
from filelock import FileLock, Timeout
from audio_database import AudioDatabase


def parse_arguments():
    """Parse command line arguments with clear descriptions"""
    parser = argparse.ArgumentParser(description="Scan directories for AudioMoth WAV files and populate database")
    
    # Required arguments first
    parser.add_argument("--config", "-c", required=True, help="YAML configuration file")
    
    # Optional arguments
    parser.add_argument("--input", "-i", help="Input directory (optional - uses input_directory from config if not provided)")
    parser.add_argument("--force", "-f", action="store_true", help="Force reprocessing of existing files")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed without actually doing any work")
    
    # Processing modes
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--init", action="store_true", help="Initialize/create database only")
    mode_group.add_argument("--scan", action="store_true", help="Scan directory and add new files to database")
    mode_group.add_argument("--rescan", action="store_true", help="Rescan all files, updating existing records")
    mode_group.add_argument("--stats", action="store_true", help="Show database statistics only")
    
    return parser.parse_args()


def load_config(config_path):
    """Load configuration from YAML file"""
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)


def create_dry_run_report(mode, config, input_directory):
    """Create a dry-run report showing what would be processed"""
    print(f"\n🔍 DRY-RUN MODE: {mode.upper()} operation")
    print("=" * 50)
    print(f"Input directory: {input_directory}")
    
    db_path = config.get('database_path')
    if not db_path:
        print("❌ No database_path specified in config file")
        return
    print(f"Database: {db_path}")
    
    if mode == "scan":
        print("Operations that would be performed:")
        print("  - Recursively find all *.WAV files")
        print("  - Extract AudioMoth metadata using metamoth library")
        print("  - Add new files to database (skip existing)")
        print("  - Report processing statistics")
        
    elif mode == "rescan":
        print("Operations that would be performed:")
        print("  - Recursively find all *.WAV files")
        print("  - Extract AudioMoth metadata using metamoth library") 
        print("  - Update ALL file records (existing and new)")
        print("  - Report processing statistics")
        
    elif mode == "stats":
        print("Operations that would be performed:")
        print("  - Query database for file counts")
        print("  - Show AudioMoth device statistics")
        print("  - Display date range coverage")
    
    print("\n🚀 Use without --dry-run to execute actual processing")


def scan_directory_with_filelock(db, directory):
    """Scan directory with filelock protection for concurrent processing"""
    import glob
    
    pattern = os.path.join(directory, "**", "*.WAV")
    wav_files = glob.glob(pattern, recursive=True)
    
    print(f"Found {len(wav_files)} WAV files to process...")
    
    processed = 0
    errors = 0
    locked = 0
    
    for i, filepath in enumerate(wav_files, 1):
        print(f"[{i:4d}/{len(wav_files)}] {os.path.basename(filepath)}...", end=" ")
        
        # Try to acquire file lock - skip immediately if locked
        lock_path = f"{filepath}.lock"
        try:
            with FileLock(lock_path, timeout=0):
                file_id = db.add_audio_file(filepath)
                if file_id:
                    processed += 1
                    print("✓")
                else:
                    errors += 1
                    print("✗")
        except Timeout:
            # File is locked by another process, skip it
            locked += 1
            print("(locked)")
            continue
    
    print(f"\nScan Results:")
    print(f"  Processed: {processed}")
    print(f"  Errors: {errors}")
    print(f"  Locked (skipped): {locked}")
    
    return processed, errors


def show_database_stats(db):
    """Display database statistics"""
    print("\n📊 Database Statistics")
    print("=" * 30)
    
    file_count = db.get_file_count()
    print(f"Total files: {file_count}")
    
    if file_count > 0:
        # Get some sample metadata to show what's available
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()
        
        # Get unique AudioMoth devices
        cursor.execute("SELECT DISTINCT audiomoth_id FROM audio_files WHERE audiomoth_id IS NOT NULL")
        devices = [row[0] for row in cursor.fetchall()]
        print(f"AudioMoth devices: {len(devices)}")
        if devices:
            print(f"  Device IDs: {', '.join(devices[:5])}")
            if len(devices) > 5:
                print(f"  ... and {len(devices) - 5} more")
        
        # Get date range
        cursor.execute("SELECT MIN(recording_datetime), MAX(recording_datetime) FROM audio_files WHERE recording_datetime IS NOT NULL")
        date_range = cursor.fetchone()
        if date_range[0] and date_range[1]:
            print(f"Date range: {date_range[0]} to {date_range[1]}")
        
        # Get total duration
        cursor.execute("SELECT SUM(duration_seconds) FROM audio_files WHERE duration_seconds IS NOT NULL")
        total_duration = cursor.fetchone()[0]
        if total_duration:
            hours = total_duration / 3600
            print(f"Total duration: {hours:.1f} hours")
        
        # Show cross-platform statistics
        cursor.execute("SELECT COUNT(*) FROM audio_files WHERE volume_prefix IS NOT NULL")
        cross_platform_count = cursor.fetchone()[0]
        if cross_platform_count > 0:
            print(f"Cross-platform records: {cross_platform_count} ({cross_platform_count/file_count*100:.1f}%)")
            
            cursor.execute("SELECT DISTINCT volume_prefix FROM audio_files WHERE volume_prefix IS NOT NULL")
            volumes = [row[0] for row in cursor.fetchall()]
            print(f"  Volume prefixes: {', '.join(volumes)}")
        
        conn.close()


def main():
    args = parse_arguments()
    
    # Load configuration
    config = load_config(args.config)
    
    # Get database path from config - fail hard if missing
    db_path = config.get('database_path')
    if not db_path:
        print("❌ No database_path specified in config file")
        return
    
    # Determine input directory: use --input if provided, otherwise fall back to config
    if args.input:
        input_directory = args.input
        input_source = "command line"
    else:
        input_directory = config.get('input_directory')
        if not input_directory and not args.stats:
            print("❌ No input directory specified. Use --input or set input_directory in config file.")
            return
        input_source = "config file"
    
    if not args.stats:
        print(f"Input directory: {input_directory} (from {input_source})")
    
    # Determine processing mode
    if args.init:
        mode = "init"
    elif args.scan:
        mode = "scan"
    elif args.rescan:
        mode = "rescan"  
    elif args.stats:
        mode = "stats"
    
    # Show dry-run information if enabled
    if args.dry_run:
        create_dry_run_report(mode, config, input_directory)
        return
    
    # Initialize database - this will fail if database_path is wrong
    print(f"Database: {db_path}")
    
    # Check if database file exists for operations that require existing database
    db_file = Path(db_path) 
    if mode not in ["stats", "init"] and not db_file.exists():
        print(f"❌ Database file not found: {db_path}")
        print("💡 Create database first by running this script with --init")
        return
    
    db = AudioDatabase(db_path, config=config)
    
    # Show cross-platform info if config has input_directory
    if config.get('input_directory') and mode != "stats":
        from spectrogram_utils import get_volume_prefix
        try:
            volume_prefix = get_volume_prefix(config)
            print(f"🌐 Cross-platform mode: Volume prefix = {volume_prefix}")
        except Exception:
            pass  # Fallback mode if volume prefix detection fails
    
    # Execute based on mode
    if mode == "init":
        print(f"✓ Database initialized at: {db_path}")
        show_database_stats(db)
        
    elif mode == "stats":
        show_database_stats(db)
        
    elif mode == "scan":
        print(f"\n🔍 Scanning for new AudioMoth files...")
        current_count = db.get_file_count()
        print(f"Current files in database: {current_count}")
        
        # Scan directory for new files with filelock protection
        processed, errors = scan_directory_with_filelock(db, input_directory)
        
        new_count = db.get_file_count()
        added = new_count - current_count
        
        print(f"\n✓ Scan complete!")
        print(f"  New files added: {added}")
        print(f"  Total files in database: {new_count}")
        
    elif mode == "rescan":
        if not args.force:
            print("❌ Rescan mode requires --force flag to confirm you want to update existing records")
            return
            
        print(f"\n🔄 Rescanning ALL AudioMoth files...")
        current_count = db.get_file_count()
        print(f"Current files in database: {current_count}")
        
        # Rescan directory with filelock protection
        # Note: AudioDatabase.add_audio_file always does INSERT OR REPLACE, so it updates existing files
        processed, errors = scan_directory_with_filelock(db, input_directory)
        
        new_count = db.get_file_count()
        
        print(f"\n✓ Rescan complete!")
        print(f"  Total files in database: {new_count}")


if __name__ == "__main__":
    main()