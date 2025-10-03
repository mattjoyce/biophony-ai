#!/usr/bin/env python3
"""
Database Manager for Acoustic Indices
Unified storage for temporal and spectral indices data
"""

import os
import sqlite3
import numpy as np
import json
import hashlib
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime

# Import cross-platform path utilities
try:
    from spectrogram_utils import (
        get_volume_prefix,
        split_path_for_database,
        reconstruct_path_from_database,
        resolve_cross_platform_path,
        get_spectrogram_path_cross_platform
    )
    CROSS_PLATFORM_AVAILABLE = True
except ImportError:
    CROSS_PLATFORM_AVAILABLE = False


class DatabaseManager:
    """Manages database operations for acoustic indices storage"""
    
    def __init__(self, db_path: str = "audiomoth.db", config: Optional[Dict[str, Any]] = None):
        """
        Initialize database manager
        
        Args:
            db_path: Path to SQLite database file
            config: Configuration dictionary for cross-platform path resolution
        """
        self.db_path = db_path
        self.config = config
        self.setup_database()
    
    def setup_database(self) -> None:
        """Setup database schema for acoustic indices"""
        if not os.path.exists(self.db_path):
            print(f"ℹ️  Database not found - indices will not be stored")
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if acoustic_indices_core table exists
        cursor.execute("PRAGMA table_info(acoustic_indices_core)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if not columns:
            # Table doesn't exist, create acoustic_indices_core table
            cursor.execute('''
            CREATE TABLE acoustic_indices_core (
                id INTEGER PRIMARY KEY,
                file_id INTEGER NOT NULL REFERENCES audio_files(id),
                index_name TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                start_time_sec REAL NOT NULL,
                value REAL,
                processing_type TEXT NOT NULL,
                computed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(file_id, index_name, chunk_index)
            )
            ''')
            
            # Create indexes for performance
            cursor.execute('''
            CREATE INDEX idx_core_file_id ON acoustic_indices_core(file_id)
            ''')
            
            cursor.execute('''
            CREATE INDEX idx_core_file_index ON acoustic_indices_core(file_id, index_name)
            ''')
            
            cursor.execute('''
            CREATE INDEX idx_core_type ON acoustic_indices_core(processing_type)
            ''')
            
            cursor.execute('''
            CREATE INDEX idx_core_name ON acoustic_indices_core(index_name)
            ''')
            
            print(f"✓ Created new acoustic_indices_core schema")
        else:
            print(f"✓ acoustic_indices_core table exists")
        
        # Create index_configurations table
        self._create_index_configurations_table(cursor)

        # Create v_acoustic_indices view for webapp API
        cursor.execute('''
            CREATE VIEW IF NOT EXISTS v_acoustic_indices AS
            SELECT
                ai.id,
                ai.file_id,
                af.filepath as wav_filepath,
                af.recording_datetime,
                ai.index_name,
                ai.chunk_index,
                ai.start_time_sec,
                ai.value,
                ai.processing_type,
                ai.computed_at
            FROM acoustic_indices_core ai
            JOIN audio_files af ON ai.file_id = af.id
        ''')
        print(f"✓ Created/verified v_acoustic_indices view")

        conn.commit()
        conn.close()
    
    def _create_index_configurations_table(self, cursor: sqlite3.Cursor) -> None:
        """Create index_configurations table to store acoustic index parameters"""
        # Check if table already exists
        cursor.execute('''
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='index_configurations'
        ''')
        
        if cursor.fetchone():
            return  # Table already exists
        
        # Create the table
        cursor.execute('''
        CREATE TABLE index_configurations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_name TEXT NOT NULL,
            index_name TEXT NOT NULL,
            processor_name TEXT NOT NULL,
            config_fragment TEXT NOT NULL,
            config_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            
            UNIQUE(config_name, index_name, config_hash)
        )
        ''')
        
        # Create index for efficient lookups
        cursor.execute('''
        CREATE INDEX idx_config_index_name 
        ON index_configurations (config_name, index_name)
        ''')
        
        print(f"✓ Created index_configurations table")
    
    def store_indices(self, filepath: str, processing_type: str, 
                     indices_data: Dict[str, np.ndarray], 
                     chunk_timestamps: np.ndarray,
                     npz_filepath: str = None) -> None:
        """
        Store acoustic indices data for a single file
        
        Args:
            filepath: Path to the source file (WAV for temporal, NPZ for spectral)
            processing_type: "temporal" or "spectral"
            indices_data: Dict mapping index_name -> values array
            chunk_timestamps: Array of start times for each chunk
            npz_filepath: Path to NPZ file (required for spectral, optional for temporal)
        """
        if not os.path.exists(self.db_path):
            print(f"⚠️  Database not found - skipping storage for {os.path.basename(filepath)}")
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Enable WAL mode for better concurrent access during sharded processing
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")  # 30 second timeout for locked database
        
        # Determine WAV and NPZ paths based on processing type
        if processing_type == "temporal":
            wav_path = filepath
            npz_path = npz_filepath  # Optional for temporal
        elif processing_type == "spectral":
            npz_path = filepath
            # Derive WAV path from NPZ path using cross-platform logic
            wav_path = self._derive_wav_from_npz(filepath)
        else:
            raise ValueError(f"Unknown processing type: {processing_type}")
        
        # Get file_id using filename-based lookup
        file_id = self._get_file_id(cursor, wav_path)
        
        # Prepare data for INSERT OR REPLACE (safe for concurrent processing)
        rows_to_insert = []
        
        for index_name, values in indices_data.items():
            if len(values) != len(chunk_timestamps):
                raise ValueError(f"Values length {len(values)} != timestamps length {len(chunk_timestamps)} for {index_name}")
            
            for chunk_index, (timestamp, value) in enumerate(zip(chunk_timestamps, values)):
                rows_to_insert.append((
                    file_id,
                    index_name,
                    chunk_index,
                    float(timestamp),
                    float(value),
                    processing_type
                ))
        
        cursor.executemany('''
        INSERT OR REPLACE INTO acoustic_indices_core 
        (file_id, index_name, chunk_index, start_time_sec, value, processing_type)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', rows_to_insert)
        
        conn.commit()
        conn.close()
        
        total_values = sum(len(values) for values in indices_data.items())
        print(f"✓ Stored {total_values} index values for {os.path.basename(filepath)} ({processing_type})")
    
    def _derive_wav_from_npz(self, npz_filepath: str) -> str:
        """
        Derive WAV file path from NPZ file path with cross-platform support
        
        Args:
            npz_filepath: NPZ file path
            
        Returns:
            str: Corresponding WAV file path
        """
        if CROSS_PLATFORM_AVAILABLE and self.config:
            # Use cross-platform path resolution
            if not os.path.isabs(npz_filepath):
                # If relative path, resolve it first
                npz_filepath = resolve_cross_platform_path(self.config, npz_filepath)
            
            # Convert NPZ to WAV using volume-aware logic
            wav_path = npz_filepath.replace('_spec.npz', '.WAV')
            return wav_path
        else:
            # Fallback to simple string replacement
            return npz_filepath.replace('_spec.npz', '.WAV')
    
    def _get_file_id(self, cursor: sqlite3.Cursor, wav_filepath: str) -> Optional[int]:
        """
        Get file_id from audio_files table with cross-platform support
        
        Args:
            cursor: Database cursor
            wav_filepath: WAV file path to look up
            
        Returns:
            Optional[int]: File ID if found, None otherwise
        """
        # Check if audio_files table exists
        cursor.execute('''
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='audio_files'
        ''')
        
        if not cursor.fetchone():
            return None
        
        # Try cross-platform lookup first if available
        if CROSS_PLATFORM_AVAILABLE and self.config:
            try:
                # Extract relative path for cross-platform lookup
                volume_prefix, relative_path = split_path_for_database(self.config, wav_filepath)
                
                # Try to find by relative_path first
                cursor.execute('SELECT id FROM audio_files WHERE relative_path = ?', (relative_path,))
                result = cursor.fetchone()
                if result:
                    return result[0]
            except Exception:
                pass  # Fall back to filename lookup
        
        # Fallback to filename-based lookup for backward compatibility
        filename = os.path.basename(wav_filepath)
        cursor.execute('SELECT id FROM audio_files WHERE filename = ?', (filename,))
        result = cursor.fetchone()
        return result[0] if result else None
    
    def get_indices_for_file(self, filepath: str, 
                           processing_type: Optional[str] = None,
                           index_names: Optional[List[str]] = None) -> Dict[str, np.ndarray]:
        """
        Retrieve stored indices for a file
        
        Args:
            filepath: Path to the file (WAV for temporal, NPZ for spectral)
            processing_type: Filter by "temporal" or "spectral" (optional)
            index_names: List of specific indices to retrieve (optional)
            
        Returns:
            Dict[str, np.ndarray]: Mapping of index_name -> values array
        """
        if not os.path.exists(self.db_path):
            return {}
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Convert NPZ path to WAV path for spectral processing
        if processing_type == "spectral" and filepath.endswith('_spec.npz'):
            wav_filepath = self._derive_wav_from_npz(filepath)
        else:
            wav_filepath = filepath
        
        # Get file_id from wav_filepath 
        file_id = self._get_file_id(cursor, wav_filepath)
        if not file_id:
            conn.close()
            return {}
        
        # Build query with optional filters using core table
        query = '''
        SELECT index_name, chunk_index, value 
        FROM acoustic_indices_core 
        WHERE file_id = ?
        '''
        params = [file_id]
        
        if processing_type:
            query += ' AND processing_type = ?'
            params.append(processing_type)
        
        if index_names:
            placeholders = ','.join('?' * len(index_names))
            query += f' AND index_name IN ({placeholders})'
            params.extend(index_names)
        
        query += ' ORDER BY index_name, chunk_index'
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        
        # Group results by index_name
        indices_data = {}
        current_index = None
        current_values = []
        
        for index_name, chunk_index, value in results:
            if index_name != current_index:
                if current_index is not None:
                    indices_data[current_index] = np.array(current_values)
                current_index = index_name
                current_values = []
            
            current_values.append(value)
        
        # Add the last index
        if current_index is not None:
            indices_data[current_index] = np.array(current_values)
        
        return indices_data
    
    def get_files_with_indices(self, processing_type: Optional[str] = None) -> List[str]:
        """
        Get list of files that have stored indices
        
        Args:
            processing_type: Filter by "temporal" or "spectral" (optional)
            
        Returns:
            List[str]: List of file paths with stored indices
        """
        if not os.path.exists(self.db_path):
            return []
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get cross-platform path info if available
        if CROSS_PLATFORM_AVAILABLE and self.config:
            query = '''
            SELECT DISTINCT af.filepath, af.volume_prefix, af.relative_path
            FROM acoustic_indices_core aic
            JOIN audio_files af ON aic.file_id = af.id
            '''
        else:
            query = '''
            SELECT DISTINCT af.filepath 
            FROM acoustic_indices_core aic
            JOIN audio_files af ON aic.file_id = af.id
            '''
        
        params = []
        if processing_type:
            query += ' WHERE aic.processing_type = ?'
            params.append(processing_type)
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        
        # Resolve paths using cross-platform logic if available
        file_paths = []
        for row in results:
            if CROSS_PLATFORM_AVAILABLE and self.config and len(row) >= 3:
                # Try to use cross-platform resolution
                filepath, volume_prefix, relative_path = row
                if volume_prefix and relative_path:
                    try:
                        current_volume = get_volume_prefix(self.config)
                        resolved_path = reconstruct_path_from_database(current_volume, relative_path)
                        file_paths.append(resolved_path)
                        continue
                    except Exception:
                        pass  # Fall back to original filepath
                
            # Use original filepath as fallback
            file_paths.append(row[0])
        
        return file_paths
    
    def get_index_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about stored indices
        
        Returns:
            Dict[str, Any]: Statistics about indices in database
        """
        if not os.path.exists(self.db_path):
            return {'error': 'Database not found'}
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get counts by processing type and index name
        cursor.execute('''
        SELECT aic.processing_type, aic.index_name, COUNT(*) as count, COUNT(DISTINCT aic.file_id) as files
        FROM acoustic_indices_core aic
        GROUP BY aic.processing_type, aic.index_name
        ORDER BY aic.processing_type, aic.index_name
        ''')
        
        stats = {
            'by_type_and_index': cursor.fetchall(),
            'total_files': 0,
            'total_values': 0
        }
        
        # Get totals
        cursor.execute('SELECT COUNT(DISTINCT file_id) FROM acoustic_indices_core')
        stats['total_files'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM acoustic_indices_core')
        stats['total_values'] = cursor.fetchone()[0]
        
        conn.close()
        return stats
    
    def clear_indices(self, filepath: Optional[str] = None, 
                     processing_type: Optional[str] = None) -> int:
        """
        Clear stored indices (for testing or reprocessing)
        
        Args:
            filepath: Clear indices for specific file (optional)
            processing_type: Clear specific processing type (optional)
            
        Returns:
            int: Number of rows deleted
        """
        if not os.path.exists(self.db_path):
            return 0
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = 'DELETE FROM acoustic_indices_core'
        params = []
        conditions = []
        
        if filepath:
            # Convert filepath to file_id
            cursor.execute('SELECT id FROM audio_files WHERE filename = ?', (os.path.basename(filepath),))
            result = cursor.fetchone()
            if result:
                conditions.append('file_id = ?')
                params.append(result[0])
            else:
                conn.close()
                return 0  # File not found
        
        if processing_type:
            conditions.append('processing_type = ?')
            params.append(processing_type)
        
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
        
        cursor.execute(query, params)
        deleted_count = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        return deleted_count
    
    def delete_indices_for_file(self, filepath: str, processing_type: str) -> int:
        """
        Delete indices for a specific file and processing type
        
        Args:
            filepath: Path to the file
            processing_type: "temporal" or "spectral"
            
        Returns:
            int: Number of rows deleted
        """
        return self.clear_indices(filepath, processing_type)
    
    def get_indices_for_files_bulk(self, file_paths: List[str], processing_type: str, 
                                   index_names: Optional[List[str]] = None) -> Dict[str, Dict[str, np.ndarray]]:
        """
        Retrieve stored indices for multiple files in a single query (shard-friendly)
        
        Args:
            file_paths: List of file paths to query
            processing_type: "temporal" or "spectral"
            index_names: List of specific indices to retrieve (optional)
            
        Returns:
            Dict[str, Dict[str, np.ndarray]]: Mapping of file_path -> {index_name -> values array}
        """
        if not os.path.exists(self.db_path) or not file_paths:
            return {}
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Convert file paths to WAV paths for consistent lookup
        wav_file_paths = []
        path_mapping = {}  # original_path -> wav_path
        
        for filepath in file_paths:
            if processing_type == "spectral" and filepath.endswith('_spec.npz'):
                wav_filepath = filepath.replace('_spec.npz', '.WAV')
            else:
                wav_filepath = filepath
            wav_file_paths.append(wav_filepath)
            path_mapping[wav_filepath] = filepath
        
        # Get file_ids for wav_file_paths
        file_id_mapping = {}  # wav_path -> file_id
        placeholders = ','.join('?' * len(wav_file_paths))
        cursor.execute(f'''
            SELECT id, filepath FROM audio_files 
            WHERE filepath IN ({placeholders})
        ''', wav_file_paths)
        
        for file_id, filepath in cursor.fetchall():
            file_id_mapping[filepath] = file_id
        
        if not file_id_mapping:
            conn.close()
            return {}
        
        # Build query with file_ids
        file_ids = list(file_id_mapping.values())
        placeholders = ','.join('?' * len(file_ids))
        query = f'''
        SELECT af.filepath, aic.index_name, aic.chunk_index, aic.value 
        FROM acoustic_indices_core aic
        JOIN audio_files af ON aic.file_id = af.id
        WHERE aic.file_id IN ({placeholders}) AND aic.processing_type = ?
        '''
        params = file_ids + [processing_type]
        
        if index_names:
            index_placeholders = ','.join('?' * len(index_names))
            query += f' AND aic.index_name IN ({index_placeholders})'
            params.extend(index_names)
        
        query += ' ORDER BY af.filepath, aic.index_name, aic.chunk_index'
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        
        # Group results by file and index
        file_indices = {}
        current_file = None
        current_index = None
        current_values = []
        
        for wav_filepath, index_name, chunk_index, value in results:
            original_filepath = path_mapping.get(wav_filepath, wav_filepath)
            
            if wav_filepath != current_file:
                # Save previous index if exists
                if current_file is not None and current_index is not None:
                    prev_original = path_mapping.get(current_file, current_file)
                    if prev_original not in file_indices:
                        file_indices[prev_original] = {}
                    file_indices[prev_original][current_index] = np.array(current_values)
                
                current_file = wav_filepath
                current_index = index_name
                current_values = [value]
            elif index_name != current_index:
                # Save previous index
                if current_index is not None:
                    if original_filepath not in file_indices:
                        file_indices[original_filepath] = {}
                    file_indices[original_filepath][current_index] = np.array(current_values)
                
                current_index = index_name
                current_values = [value]
            else:
                current_values.append(value)
        
        # Save the last index
        if current_file is not None and current_index is not None:
            original_filepath = path_mapping.get(current_file, current_file)
            if original_filepath not in file_indices:
                file_indices[original_filepath] = {}
            file_indices[original_filepath][current_index] = np.array(current_values)
        
        return file_indices
    
    def get_weather_for_filename(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        Get weather data for a file using filename lookup
        
        Args:
            filename: AudioMoth filename (e.g., "20250706_013000.WAV")
            
        Returns:
            Optional[Dict[str, Any]]: Weather data dictionary or None if not found
        """
        if not os.path.exists(self.db_path):
            return None
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if weather tables exist
        cursor.execute('''
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name IN ('weather_data', 'weather_sites', 'audio_files')
        ''')
        
        tables = [row[0] for row in cursor.fetchall()]
        if len(tables) < 3:
            conn.close()
            return None
        
        # Get weather data using filename lookup through audio_files
        cursor.execute('''
        SELECT wd.datetime, wd.temperature_2m, wd.relative_humidity_2m,
               wd.precipitation, wd.wind_speed_10m, wd.weather_code,
               wd.cloud_cover, wd.pressure_msl,
               ws.name as site_name, ws.latitude, ws.longitude,
               af.recorded_at
        FROM audio_files af
        JOIN weather_data wd ON af.weather_id = wd.id  
        JOIN weather_sites ws ON wd.site_id = ws.id
        WHERE af.filename = ?
        ''', (filename,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'weather_datetime': result[0],
                'temperature_2m': result[1],
                'relative_humidity_2m': result[2], 
                'precipitation': result[3],
                'wind_speed_10m': result[4],
                'weather_code': result[5],
                'cloud_cover': result[6],
                'pressure_msl': result[7],
                'site_name': result[8],
                'site_latitude': result[9],
                'site_longitude': result[10],
                'recording_datetime': result[11]
            }
        
        return None
    
    def store_index_configuration(self, config_name: str, config_data: Dict[str, Any]) -> None:
        """
        Store acoustic index configuration parameters in database
        
        Args:
            config_name: Name of the configuration file (e.g., 'config_multi_species_frogs.yaml')
            config_data: Dictionary containing the full config loaded from YAML
        """
        if not os.path.exists(self.db_path):
            print(f"⚠️  Database not found - skipping config storage")
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Extract acoustic indices configuration
            acoustic_indices = config_data.get('acoustic_indices', {})
            spectral_config = acoustic_indices.get('spectral', {})
            temporal_config = acoustic_indices.get('temporal', {})
            
            configurations_stored = 0
            
            # Process spectral indices
            for index_name, index_config in spectral_config.items():
                if index_name == 'chunk_duration_sec':  # Skip non-index parameters
                    continue
                
                if isinstance(index_config, dict) and 'processor' in index_config:
                    processor_name = index_config['processor']
                    
                    # Create config fragment
                    config_fragment = {
                        'processor': processor_name,
                        'params': index_config.get('params', {}),
                        'processing_type': 'spectral'
                    }
                    
                    # Calculate hash for duplicate detection
                    config_json = json.dumps(config_fragment, sort_keys=True)
                    config_hash = hashlib.sha256(config_json.encode()).hexdigest()[:16]
                    
                    # Store configuration (ignore duplicates)
                    try:
                        cursor.execute('''
                        INSERT OR IGNORE INTO index_configurations 
                        (config_name, index_name, processor_name, config_fragment, config_hash)
                        VALUES (?, ?, ?, ?, ?)
                        ''', (config_name, index_name, processor_name, config_json, config_hash))
                        
                        if cursor.rowcount > 0:
                            configurations_stored += 1
                    except sqlite3.IntegrityError:
                        pass  # Duplicate entry, skip
            
            # Process temporal indices
            for index_name, index_config in temporal_config.items():
                if index_name == 'chunk_duration_sec':  # Skip non-index parameters
                    continue
                    
                if isinstance(index_config, dict) and 'processor' in index_config:
                    processor_name = index_config['processor']
                    
                    # Create config fragment
                    config_fragment = {
                        'processor': processor_name,
                        'params': index_config.get('params', {}),
                        'processing_type': 'temporal'
                    }
                    
                    # Calculate hash for duplicate detection
                    config_json = json.dumps(config_fragment, sort_keys=True)
                    config_hash = hashlib.sha256(config_json.encode()).hexdigest()[:16]
                    
                    # Store configuration (ignore duplicates)
                    try:
                        cursor.execute('''
                        INSERT OR IGNORE INTO index_configurations 
                        (config_name, index_name, processor_name, config_fragment, config_hash)
                        VALUES (?, ?, ?, ?, ?)
                        ''', (config_name, index_name, processor_name, config_json, config_hash))
                        
                        if cursor.rowcount > 0:
                            configurations_stored += 1
                    except sqlite3.IntegrityError:
                        pass  # Duplicate entry, skip
            
            conn.commit()
            
            if configurations_stored > 0:
                print(f"✓ Stored {configurations_stored} index configurations from {config_name}")
            
        except Exception as e:
            print(f"⚠️  Error storing configuration: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def get_index_configuration(self, index_name: str, 
                              config_name: str = None) -> Optional[Dict[str, Any]]:
        """
        Retrieve stored configuration for an acoustic index
        
        Args:
            index_name: Name of the index (e.g., 'eastern_froglet_bai_2500-3500')
            config_name: Specific config file name to search (optional)
            
        Returns:
            Optional[Dict[str, Any]]: Configuration dictionary or None if not found
        """
        if not os.path.exists(self.db_path):
            return None
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = '''
        SELECT config_name, processor_name, config_fragment, created_at
        FROM index_configurations 
        WHERE index_name = ?
        '''
        params = [index_name]
        
        if config_name:
            query += ' AND config_name = ?'
            params.append(config_name)
        
        query += ' ORDER BY created_at DESC LIMIT 1'
        
        cursor.execute(query, params)
        result = cursor.fetchone()
        conn.close()
        
        if result:
            config_fragment = json.loads(result[2])
            return {
                'config_name': result[0],
                'processor_name': result[1],
                'config_fragment': config_fragment,
                'created_at': result[3],
                'index_name': index_name
            }
        
        return None
    
    def get_all_configurations(self, config_name: str = None) -> List[Dict[str, Any]]:
        """
        Retrieve all stored configurations
        
        Args:
            config_name: Filter by specific config file (optional)
            
        Returns:
            List[Dict[str, Any]]: List of all configurations
        """
        if not os.path.exists(self.db_path):
            return []
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = '''
        SELECT config_name, index_name, processor_name, config_fragment, config_hash, created_at
        FROM index_configurations
        '''
        params = []
        
        if config_name:
            query += ' WHERE config_name = ?'
            params.append(config_name)
        
        query += ' ORDER BY config_name, index_name'
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        
        configurations = []
        for row in results:
            config_fragment = json.loads(row[3])
            configurations.append({
                'config_name': row[0],
                'index_name': row[1],
                'processor_name': row[2],
                'config_fragment': config_fragment,
                'config_hash': row[4],
                'created_at': row[5]
            })
        
        return configurations