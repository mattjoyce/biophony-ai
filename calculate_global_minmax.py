#!/usr/bin/env python3
"""
Calculate global min/max across all spectrogram files
Much simpler approach - just track the absolute range
"""

import os
import glob
import torch
import torchaudio
import torchaudio.transforms as T
import numpy as np
import argparse
import yaml
import sqlite3

def parse_arguments():
    parser = argparse.ArgumentParser(description="Calculate global min/max for spectrograms")
    parser.add_argument("--input", "-i", required=True, help="Input directory with audio files")
    parser.add_argument("--config", "-c", required=True, help="YAML configuration file")
    parser.add_argument("--target", type=int, nargs='+', help="Target subset(s): e.g. --target 0 1 2")
    parser.add_argument("--sample-pct", type=float, default=1.0, help="Percentage of files to process (default: 1.0 = all files)")
    parser.add_argument("--force", action="store_true", help="Force recalculation even if values exist in database")
    return parser.parse_args()

def check_existing_stats(db_path):
    """Check if global stats already exist in database"""
    if not os.path.exists(db_path):
        return None, None
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT stat_value FROM global_stats WHERE stat_name = 'global_min'")
        min_result = cursor.fetchone()
        cursor.execute("SELECT stat_value FROM global_stats WHERE stat_name = 'global_max'")
        max_result = cursor.fetchone()
        
        conn.close()
        
        if min_result and max_result:
            return float(min_result[0]), float(max_result[0])
        else:
            return None, None
            
    except sqlite3.OperationalError:
        return None, None

def main():
    args = parse_arguments()
    
    # Always process files to ensure per-file stats are complete
    db_path = "audiomoth.db"
    
    # Load config
    with open(args.config, 'r') as file:
        config = yaml.safe_load(file)
    
    # Setup GPU
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    # Add spectrogram columns to database if they don't exist
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Add columns for per-file spectrogram statistics
        try:
            cursor.execute('ALTER TABLE audio_files ADD COLUMN spectrogram_min REAL')
            print("✓ Added spectrogram_min column to database")
        except sqlite3.OperationalError:
            pass  # Column already exists
            
        try:
            cursor.execute('ALTER TABLE audio_files ADD COLUMN spectrogram_max REAL')
            print("✓ Added spectrogram_max column to database")
        except sqlite3.OperationalError:
            pass  # Column already exists
            
        conn.commit()
        conn.close()
    
    # Find files
    all_wavs = sorted(glob.glob(os.path.join(args.input, "**", "*.WAV"), recursive=True))
    
    # Filter by target if specified
    if args.target:
        wav_files = []
        for i, f in enumerate(all_wavs):
            if i % 10 in args.target:
                wav_files.append(f)
        all_wavs = wav_files
        target_str = "_".join(map(str, args.target))
        print(f"Processing target subset {target_str}: {len(all_wavs)} files")
    else:
        print(f"Processing all files: {len(all_wavs)} files")
    
    # Apply sample percentage if specified
    if args.sample_pct < 1.0:
        import random
        sample_size = max(1, int(len(all_wavs) * args.sample_pct))
        all_wavs = random.sample(all_wavs, sample_size)
        print(f"Sampling {args.sample_pct*100:.1f}%: {len(all_wavs)} files")
    
    print(f"Finding global min/max across {len(all_wavs)} files")
    
    # Create mel transform
    mel_transform = T.MelSpectrogram(
        sample_rate=48000,
        n_fft=config.get('n_fft', 2048),
        hop_length=config.get('hop_length', 256),
        n_mels=config.get('n_mels', 128),
        power=2.0
    ).to(device)
    
    global_min = float('inf')
    global_max = float('-inf')
    
    for i, f in enumerate(all_wavs, 1):
        try:
            print(f"[{i:4d}/{len(all_wavs)}] {os.path.basename(f)}...", end=" ")
            
            # Check if file already has spectrogram statistics (unless --force)
            if not args.force and os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute('''
                SELECT spectrogram_min, spectrogram_max 
                FROM audio_files 
                WHERE filepath = ? AND spectrogram_min IS NOT NULL AND spectrogram_max IS NOT NULL
                ''', (f,))
                existing = cursor.fetchone()
                conn.close()
                
                if existing:
                    file_min, file_max = existing
                    global_min = min(global_min, file_min)
                    global_max = max(global_max, file_max)
                    print(f"(cached) (min: {file_min:.1f}, max: {file_max:.1f})")
                    continue
            
            # Calculate spectrogram statistics using percentiles
            waveform, sr = torchaudio.load(f)
            waveform = waveform.to(device)
            
            mel = mel_transform(waveform)
            mel_db = T.AmplitudeToDB()(mel)
            
            # Use percentiles to avoid silence/padding affecting contrast
            mel_flat = mel_db.cpu().flatten().numpy()
            file_min = float(np.percentile(mel_flat, 2))   # 2nd percentile as noise floor
            file_max = float(np.percentile(mel_flat, 98))  # 98th percentile as max signal
            
            global_min = min(global_min, file_min)
            global_max = max(global_max, file_max)
            
            # Update database with per-file statistics
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Update the audio_files table with spectrogram min/max
                cursor.execute('''
                UPDATE audio_files 
                SET spectrogram_min = ?, spectrogram_max = ?
                WHERE filepath = ?
                ''', (file_min, file_max, f))
                
                conn.commit()
                conn.close()
            
            print(f"✓ (min: {file_min:.1f}, max: {file_max:.1f})")
            
            # Cleanup
            del waveform, mel, mel_db
            if device.type == "cuda":
                torch.cuda.empty_cache()
                
        except Exception as e:
            print(f"✗ {e}")
            continue
    
    print(f"\nGlobal Min/Max Statistics:")
    print(f"  Global minimum: {global_min:.2f} dB")
    print(f"  Global maximum: {global_max:.2f} dB")
    print(f"  Dynamic range: {global_max - global_min:.2f} dB")
    
    # Calculate percentile-based global statistics from ALL per-file values in database
    if os.path.exists(db_path):
        print(f"\nCalculating percentile-based global statistics from database...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all min/max values to calculate percentiles
        cursor.execute('''
        SELECT spectrogram_min, spectrogram_max 
        FROM audio_files 
        WHERE spectrogram_min IS NOT NULL AND spectrogram_max IS NOT NULL
        ''')
        all_values = cursor.fetchall()
        
        if all_values:
            # Flatten all min/max values into a single array for percentile calculation
            mins = [row[0] for row in all_values]
            maxs = [row[1] for row in all_values]
            all_db_values = mins + maxs
            
            # Calculate percentiles for better contrast
            p2 = np.percentile(all_db_values, 2)   # 2nd percentile for noise floor
            p98 = np.percentile(all_db_values, 98) # 98th percentile for max signal
            
            # Also show absolute range for comparison
            abs_min = min(all_db_values)
            abs_max = max(all_db_values)
            
            print(f"📊 Statistics from {len(all_values)} files:")
            print(f"  Absolute range: {abs_min:.2f} to {abs_max:.2f} dB ({abs_max - abs_min:.1f} dB)")
            print(f"  Percentile range (2%-98%): {p2:.2f} to {p98:.2f} dB ({p98 - p2:.1f} dB)")
            print(f"  Using percentile range for better contrast")
            
            db_global_min, db_global_max = p2, p98
            
            # Create or update global_stats table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS global_stats (
                id INTEGER PRIMARY KEY,
                stat_name TEXT UNIQUE,
                stat_value REAL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # Insert or update global min/max
            cursor.execute('''
            INSERT OR REPLACE INTO global_stats (id, stat_name, stat_value, updated_at)
            VALUES (1, 'global_min', ?, CURRENT_TIMESTAMP)
            ''', (db_global_min,))
            
            cursor.execute('''
            INSERT OR REPLACE INTO global_stats (id, stat_name, stat_value, updated_at)
            VALUES (2, 'global_max', ?, CURRENT_TIMESTAMP)
            ''', (db_global_max,))
            
            conn.commit()
            print(f"✓ Database updated with global statistics")
        else:
            print(f"⚠️  No per-file spectrogram data found in database")
        
        conn.close()
    else:
        print(f"\n⚠️  Database {db_path} not found")

if __name__ == "__main__":
    main()