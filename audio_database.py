#!/usr/bin/env python3
"""
AudioMoth Database Management System
"""

import glob
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

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
        cursor.execute(
            """
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
        """
        )

        # Annotations table for Audacity labels/annotations
        cursor.execute(
            """
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
        """
        )

        # Research goals table for POI feature
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS research_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
        )

        # Points of interest table
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS points_of_interest (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_id INTEGER REFERENCES research_goals(id),
            label TEXT NOT NULL,
            notes TEXT,
            confidence REAL CHECK (confidence >= 0 AND confidence <= 1),
            anchor_index_name TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
        )

        # POI spans table for time ranges
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS poi_spans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            poi_id INTEGER NOT NULL REFERENCES points_of_interest(id) ON DELETE CASCADE,
            file_id INTEGER NOT NULL REFERENCES audio_files(id),
            start_time_sec INTEGER NOT NULL,
            end_time_sec INTEGER NOT NULL,
            chunk_start INTEGER,
            chunk_end INTEGER,
            config_name TEXT,
            processing_type TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            CHECK (start_time_sec < end_time_sec)
        )
        """
        )

        # Processing scales registry
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS processing_scales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_name TEXT NOT NULL,
            processing_type TEXT NOT NULL,
            chunk_duration_sec REAL NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(config_name, processing_type)
        )
        """
        )

        # Create indexes for common queries
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_recording_datetime ON audio_files(recording_datetime)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_audiomoth_id ON audio_files(audiomoth_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_filepath ON audio_files(filepath)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_annotations_file ON annotations(audio_file_id)"
        )
        
        # POI indexes for performance
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_poi_spans_file_time ON poi_spans(file_id, start_time_sec, end_time_sec)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_poi_spans_poi ON poi_spans(poi_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_points_of_interest_goal ON points_of_interest(goal_id)"
        )

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
            cursor.execute(
                """
            INSERT OR REPLACE INTO audio_files (
                filename, filepath, file_size, recording_datetime, timezone,
                audiomoth_id, firmware_version, duration_seconds, samplerate_hz,
                channels, samples, gain, battery_voltage, low_battery,
                temperature_c, recording_state, deployment_id, external_microphone,
                comment, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (
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
                    metadata.comment,
                ),
            )

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
        cursor.execute(
            """
        SELECT 
            MIN(recording_datetime) as earliest,
            MAX(recording_datetime) as latest
        FROM audio_files
        """
        )
        result = cursor.fetchone()
        conn.close()
        return result

    def search_files(
        self,
        date_from=None,
        date_to=None,
        time_from=None,
        time_to=None,
        audiomoth_id=None,
        limit=100,
    ):
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

    def add_annotation(
        self, filepath, start_time, end_time, label, annotation_type="manual"
    ):
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

        cursor.execute(
            """
        INSERT INTO annotations (audio_file_id, start_time, end_time, label, annotation_type)
        VALUES (?, ?, ?, ?, ?)
        """,
            (audio_file_id, start_time, end_time, label, annotation_type),
        )

        conn.commit()
        annotation_id = cursor.lastrowid
        conn.close()

        return annotation_id

    def import_audacity_labels(self, label_file, audio_filepath):
        """Import Audacity label file for a specific audio file."""
        if not os.path.exists(label_file):
            return False

        with open(label_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    # Audacity label format: start_time\tend_time\tlabel
                    parts = line.split("\t")
                    if len(parts) >= 3:
                        start_time = float(parts[0])
                        end_time = float(parts[1])
                        label = parts[2]

                        self.add_annotation(
                            audio_filepath, start_time, end_time, label, "audacity"
                        )
                except ValueError:
                    continue

        return True

    # POI (Points of Interest) Management Methods
    
    def create_goal(self, title, description=None):
        """Create a new research goal."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            """
        INSERT INTO research_goals (title, description)
        VALUES (?, ?)
        """,
            (title, description),
        )
        
        conn.commit()
        goal_id = cursor.lastrowid
        conn.close()
        
        return goal_id
    
    def get_goals(self):
        """Get all research goals."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM research_goals ORDER BY created_at DESC")
        results = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in results]
    
    def get_goal(self, goal_id):
        """Get a specific research goal by ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM research_goals WHERE id = ?", (goal_id,))
        result = cursor.fetchone()
        conn.close()
        
        return dict(result) if result else None
    
    def update_goal(self, goal_id, title=None, description=None):
        """Update a research goal."""
        if not title and not description:
            return False
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if title:
            updates.append("title = ?")
            params.append(title)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        
        params.append(goal_id)
        
        cursor.execute(
            f"UPDATE research_goals SET {', '.join(updates)} WHERE id = ?",
            params
        )
        
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        
        return success
    
    def delete_goal(self, goal_id):
        """Delete a research goal and all associated POIs."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Delete POI spans first (cascade will handle this, but being explicit)
        cursor.execute("""
            DELETE FROM poi_spans 
            WHERE poi_id IN (SELECT id FROM points_of_interest WHERE goal_id = ?)
        """, (goal_id,))
        
        # Delete POIs
        cursor.execute("DELETE FROM points_of_interest WHERE goal_id = ?", (goal_id,))
        
        # Delete goal
        cursor.execute("DELETE FROM research_goals WHERE id = ?", (goal_id,))
        
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        
        return success
    
    def create_poi(self, goal_id, label, notes=None, confidence=None, anchor_index_name=None):
        """Create a new point of interest."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            """
        INSERT INTO points_of_interest (goal_id, label, notes, confidence, anchor_index_name)
        VALUES (?, ?, ?, ?, ?)
        """,
            (goal_id, label, notes, confidence, anchor_index_name),
        )
        
        conn.commit()
        poi_id = cursor.lastrowid
        conn.close()
        
        return poi_id
    
    def get_pois(self, goal_id=None, file_id=None, date_from=None, date_to=None, limit=100):
        """Get POIs with optional filtering."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        conditions = []
        params = []
        
        if goal_id:
            conditions.append("poi.goal_id = ?")
            params.append(goal_id)
        
        if file_id:
            conditions.append("EXISTS (SELECT 1 FROM poi_spans ps WHERE ps.poi_id = poi.id AND ps.file_id = ?)")
            params.append(file_id)
        
        if date_from:
            conditions.append("DATE(poi.created_at) >= ?")
            params.append(date_from)
        
        if date_to:
            conditions.append("DATE(poi.created_at) <= ?")
            params.append(date_to)
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        query = f"""
        SELECT poi.*, g.title as goal_title 
        FROM points_of_interest poi
        LEFT JOIN research_goals g ON poi.goal_id = g.id
        {where_clause}
        ORDER BY poi.created_at DESC
        LIMIT ?
        """
        params.append(limit)
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in results]
    
    def get_poi(self, poi_id):
        """Get a specific POI with its spans."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get POI details
        cursor.execute("""
            SELECT poi.*, g.title as goal_title
            FROM points_of_interest poi
            LEFT JOIN research_goals g ON poi.goal_id = g.id
            WHERE poi.id = ?
        """, (poi_id,))
        
        poi = cursor.fetchone()
        if not poi:
            conn.close()
            return None
        
        poi_dict = dict(poi)
        
        # Get spans
        cursor.execute("""
            SELECT ps.*, af.filename, af.filepath
            FROM poi_spans ps
            LEFT JOIN audio_files af ON ps.file_id = af.id
            WHERE ps.poi_id = ?
            ORDER BY ps.start_time_sec
        """, (poi_id,))
        
        spans = cursor.fetchall()
        poi_dict['spans'] = [dict(span) for span in spans]
        
        conn.close()
        return poi_dict
    
    def update_poi(self, poi_id, **kwargs):
        """Update POI properties."""
        if not kwargs:
            return False
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        valid_fields = ['label', 'notes', 'confidence', 'anchor_index_name']
        updates = []
        params = []
        
        for field, value in kwargs.items():
            if field in valid_fields:
                updates.append(f"{field} = ?")
                params.append(value)
        
        if not updates:
            conn.close()
            return False
        
        params.append(poi_id)
        
        cursor.execute(
            f"UPDATE points_of_interest SET {', '.join(updates)} WHERE id = ?",
            params
        )
        
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        
        return success
    
    def delete_poi(self, poi_id):
        """Delete a POI and all its spans."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Delete spans first (cascade should handle this)
        cursor.execute("DELETE FROM poi_spans WHERE poi_id = ?", (poi_id,))
        
        # Delete POI
        cursor.execute("DELETE FROM points_of_interest WHERE id = ?", (poi_id,))
        
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        
        return success
    
    def add_poi_span(self, poi_id, file_id, start_time_sec, end_time_sec, 
                     chunk_start=None, chunk_end=None, config_name=None, processing_type=None):
        """Add a time span to an existing POI."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            """
        INSERT INTO poi_spans (poi_id, file_id, start_time_sec, end_time_sec, 
                              chunk_start, chunk_end, config_name, processing_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (poi_id, file_id, start_time_sec, end_time_sec, 
             chunk_start, chunk_end, config_name, processing_type),
        )
        
        conn.commit()
        span_id = cursor.lastrowid
        conn.close()
        
        return span_id
    
    def get_poi_spans(self, poi_id):
        """Get all spans for a POI."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT ps.*, af.filename, af.filepath
            FROM poi_spans ps
            LEFT JOIN audio_files af ON ps.file_id = af.id
            WHERE ps.poi_id = ?
            ORDER BY ps.start_time_sec
        """, (poi_id,))
        
        results = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in results]
    
    def delete_poi_span(self, span_id):
        """Delete a specific POI span."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM poi_spans WHERE id = ?", (span_id,))
        
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        
        return success
    
    def register_scale(self, config_name, processing_type, chunk_duration_sec):
        """Register a processing scale from config."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            """
        INSERT OR REPLACE INTO processing_scales (config_name, processing_type, chunk_duration_sec)
        VALUES (?, ?, ?)
        """,
            (config_name, processing_type, chunk_duration_sec),
        )
        
        conn.commit()
        scale_id = cursor.lastrowid
        conn.close()
        
        return scale_id
    
    def get_scale(self, config_name, processing_type):
        """Get chunk duration for a config/processing type."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM processing_scales WHERE config_name = ? AND processing_type = ?",
            (config_name, processing_type)
        )
        
        result = cursor.fetchone()
        conn.close()
        
        return dict(result) if result else None
    
    def populate_scales_from_config(self, config_data, config_name=None):
        """Parse config YAML and register all processing scales."""
        if not config_name:
            config_name = 'config_mac.yaml'  # default fallback
            
        acoustic_indices = config_data.get('acoustic_indices', {})
        
        # Register temporal scale
        temporal_config = acoustic_indices.get('temporal', {})
        if 'chunk_duration_sec' in temporal_config:
            self.register_scale(config_name, 'temporal', temporal_config['chunk_duration_sec'])
        
        # Register spectral scale  
        spectral_config = acoustic_indices.get('spectral', {})
        if 'chunk_duration_sec' in spectral_config:
            self.register_scale(config_name, 'spectral', spectral_config['chunk_duration_sec'])
    
    def calculate_chunks(self, start_sec, end_sec, config_name, processing_type):
        """Calculate chunk indices for a time span."""
        scale = self.get_scale(config_name, processing_type)
        if scale:
            chunk_duration = scale['chunk_duration_sec']
            chunk_start = int(start_sec / chunk_duration)
            chunk_end = int(end_sec / chunk_duration)
            return chunk_start, chunk_end
        return None, None
    
    def search_files_by_path_pattern(self, pattern):
        """Find files matching a pattern."""
        import fnmatch
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM audio_files")
        all_files = cursor.fetchall()
        conn.close()
        
        matching_files = []
        for file_row in all_files:
            if fnmatch.fnmatch(file_row['filepath'], pattern):
                matching_files.append(dict(file_row))
        
        return matching_files
    
    def get_indices_for_span(self, file_id, start_time_sec, end_time_sec):
        """Get acoustic indices that intersect with a time span."""
        # This would need to connect to acoustic indices table when it exists
        # For now, return empty list as placeholder
        return []
    
    def export_poi_audacity_labels(self, poi_id, output_path):
        """Export POI spans as Audacity label file."""
        poi = self.get_poi(poi_id)
        if not poi:
            return False
            
        with open(output_path, 'w') as f:
            for span in poi['spans']:
                f.write(f"{span['start_time_sec']}\t{span['end_time_sec']}\t{poi['label']}\n")
        
        return True
