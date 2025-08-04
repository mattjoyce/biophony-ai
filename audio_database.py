#!/usr/bin/env python3
"""
AudioMoth Database Management System
"""

import os
import sys
import sqlite3
import glob
from datetime import datetime
from pathlib import Path
import json

from metamoth import parse_metadata

class AudioDatabase:
    def __init__(self, db_path="audiomoth.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the SQLite database with required tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Audio files table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS audio_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL UNIQUE,
            file_size INTEGER,
            recording_datetime DATETIME,
            timezone TEXT,
            audiomoth_id TEXT,
            firmware_version TEXT,
            duration_seconds REAL,
            samplerate_hz INTEGER,
            channels INTEGER,
            samples INTEGER,
            gain TEXT,
            battery_voltage REAL,
            low_battery BOOLEAN,
            temperature_c REAL,
            recording_state TEXT,
            deployment_id TEXT,
            external_microphone BOOLEAN,
            comment TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Annotations table for Audacity labels/annotations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS annotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            audio_file_id INTEGER,
            start_time REAL,
            end_time REAL,
            label TEXT,
            annotation_type TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (audio_file_id) REFERENCES audio_files (id)
        )
        ''')
        
        # Create indexes for common queries
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_recording_datetime ON audio_files(recording_datetime)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_audiomoth_id ON audio_files(audiomoth_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_filepath ON audio_files(filepath)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_annotations_file ON annotations(audio_file_id)')
        
        conn.commit()
        conn.close()
    
    def add_audio_file(self, filepath):
        """Add an audio file to the database."""
        try:
            # Get file stats
            stat = os.stat(filepath)
            file_size = stat.st_size
            
            # Parse metadata using metamoth
            metadata = parse_metadata(filepath)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Insert or replace file record
            cursor.execute('''
            INSERT OR REPLACE INTO audio_files (
                filename, filepath, file_size, recording_datetime, timezone,
                audiomoth_id, firmware_version, duration_seconds, samplerate_hz,
                channels, samples, gain, battery_voltage, low_battery,
                temperature_c, recording_state, deployment_id, external_microphone,
                comment, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                os.path.basename(filepath),
                filepath,
                file_size,
                metadata.datetime.isoformat(),
                str(metadata.timezone),
                metadata.audiomoth_id,
                metadata.firmware_version,
                metadata.duration_s,
                metadata.samplerate_hz,
                metadata.channels,
                metadata.samples,
                str(metadata.gain) if metadata.gain else None,
                metadata.battery_state_v,
                metadata.low_battery,
                metadata.temperature_c,
                str(metadata.recording_state) if metadata.recording_state else None,
                metadata.deployment_id,
                metadata.external_microphone,
                metadata.comment
            ))
            
            conn.commit()
            file_id = cursor.lastrowid
            conn.close()
            
            return file_id
            
        except Exception as e:
            print(f"Error processing {filepath}: {e}")
            return None
    
    def scan_directory(self, directory):
        """Scan a directory for audio files and add them to the database."""
        pattern = os.path.join(directory, "**", "*.WAV")
        wav_files = glob.glob(pattern, recursive=True)
        
        print(f"Found {len(wav_files)} WAV files to process...")
        
        processed = 0
        errors = 0
        
        for i, filepath in enumerate(wav_files, 1):
            print(f"[{i:4d}/{len(wav_files)}] {os.path.basename(filepath)}...", end="")
            
            file_id = self.add_audio_file(filepath)
            if file_id:
                processed += 1
                print(" ✓")
            else:
                errors += 1
                print(" ✗")
        
        print(f"\nScan complete: {processed} files processed, {errors} errors")
        return processed, errors
    
    def get_file_count(self):
        """Get total number of files in database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM audio_files")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def get_date_range(self):
        """Get the date range of recordings."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
        SELECT 
            MIN(recording_datetime) as earliest,
            MAX(recording_datetime) as latest
        FROM audio_files
        """)
        result = cursor.fetchone()
        conn.close()
        return result
    
    def search_files(self, date_from=None, date_to=None, time_from=None, time_to=None, 
                    audiomoth_id=None, limit=100):
        """Search for audio files with various filters."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        cursor = conn.cursor()
        
        conditions = []
        params = []
        
        if date_from:
            conditions.append("DATE(recording_datetime) >= ?")
            params.append(date_from)
        
        if date_to:
            conditions.append("DATE(recording_datetime) <= ?")
            params.append(date_to)
        
        if time_from:
            conditions.append("TIME(recording_datetime) >= ?")
            params.append(time_from)
        
        if time_to:
            conditions.append("TIME(recording_datetime) <= ?")
            params.append(time_to)
        
        if audiomoth_id:
            conditions.append("audiomoth_id = ?")
            params.append(audiomoth_id)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        query = f"""
        SELECT * FROM audio_files 
        WHERE {where_clause}
        ORDER BY recording_datetime
        LIMIT ?
        """
        params.append(limit)
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in results]
    
    def add_annotation(self, filepath, start_time, end_time, label, annotation_type="manual"):
        """Add an annotation for an audio file."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get audio file ID
        cursor.execute("SELECT id FROM audio_files WHERE filepath = ?", (filepath,))
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return None
        
        audio_file_id = result[0]
        
        cursor.execute('''
        INSERT INTO annotations (audio_file_id, start_time, end_time, label, annotation_type)
        VALUES (?, ?, ?, ?, ?)
        ''', (audio_file_id, start_time, end_time, label, annotation_type))
        
        conn.commit()
        annotation_id = cursor.lastrowid
        conn.close()
        
        return annotation_id
    
    def import_audacity_labels(self, label_file, audio_filepath):
        """Import Audacity label file for a specific audio file."""
        if not os.path.exists(label_file):
            return False
        
        with open(label_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    # Audacity label format: start_time\tend_time\tlabel
                    parts = line.split('\t')
                    if len(parts) >= 3:
                        start_time = float(parts[0])
                        end_time = float(parts[1])
                        label = parts[2]
                        
                        self.add_annotation(audio_filepath, start_time, end_time, label, "audacity")
                except ValueError:
                    continue
        
        return True

