#!/usr/bin/env python3
"""
Acoustic Indices API endpoints for AudioMoth Spectrogram Viewer
Handles acoustic indices data requests and RGB mapping
"""

from flask import Blueprint, request, jsonify, current_app
from typing import Dict, List, Optional, Any
import sqlite3
import os

indices_bp = Blueprint('indices', __name__)


def create_error_response(status_code: int, message: str) -> tuple:
    """Create standardized error response"""
    return jsonify({'success': False, 'error': message}), status_code


def get_db_connection() -> sqlite3.Connection:
    """Get database connection using app config"""
    db_path = current_app.config.get('DATABASE_PATH')
    if not db_path or not os.path.exists(db_path):
        raise RuntimeError(f"Database not found at: {db_path}")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_file_by_datetime(date: str, time: str) -> Optional[Dict[str, Any]]:
    """Get audio file info by date and time"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Format time with seconds if not provided (HH:MM -> HH:MM:SS)
        if len(time) == 5:  # HH:MM format
            time_formatted = f"{time}:00"
        else:
            time_formatted = time
        
        cursor.execute("""
            SELECT id, filename, filepath, duration_seconds
            FROM audio_files 
            WHERE DATE(recording_datetime) = ? 
            AND TIME(recording_datetime) = ?
        """, (date, time_formatted))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row['id'],
                'filename': row['filename'],
                'filepath': row['filepath'],
                'duration_seconds': row['duration_seconds']
            }
        return None
        
    except Exception as e:
        print(f"Error getting file by datetime: {e}")
        return None


@indices_bp.route('/api/indices/available')
def get_available_indices():
    """Get list of all available acoustic index types"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT index_name 
            FROM v_acoustic_indices 
            ORDER BY index_name
        """)
        
        indices = [row['index_name'] for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({
            'success': True,
            'data': indices
        })
        
    except Exception as e:
        return create_error_response(500, f"Failed to get available indices: {str(e)}")


@indices_bp.route('/api/indices/<date>/<time>')
def get_file_indices(date: str, time: str):
    """Get all acoustic indices data for a specific file"""
    try:
        # Get file info first
        file_info = get_file_by_datetime(date, time)
        if not file_info:
            return create_error_response(404, f'No file found for {date} {time}')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT index_name, chunk_index, start_time_sec, value
            FROM v_acoustic_indices
            WHERE file_id = ?
            ORDER BY index_name, chunk_index
        """, (file_info['id'],))
        
        rows = cursor.fetchall()
        conn.close()
        
        # Group data by index name
        indices_data = {}
        for row in rows:
            index_name = row['index_name']
            if index_name not in indices_data:
                indices_data[index_name] = []
            
            indices_data[index_name].append({
                'chunk_index': row['chunk_index'],
                'start_time_sec': row['start_time_sec'],
                'value': row['value']
            })
        
        return jsonify({
            'success': True,
            'data': {
                'file_info': file_info,
                'indices': indices_data
            }
        })
        
    except Exception as e:
        return create_error_response(500, f"Failed to get indices data: {str(e)}")


@indices_bp.route('/api/indices/<date>/<time>/rgb')
def get_rgb_indices(date: str, time: str):
    """Get RGB-mapped indices data for visualization"""
    try:
        # Get query parameters for RGB channel assignments
        red_index = request.args.get('red')
        green_index = request.args.get('green') 
        blue_index = request.args.get('blue')
        
        if not any([red_index, green_index, blue_index]):
            return create_error_response(400, 'At least one RGB channel must be specified')
        
        # Get file info
        file_info = get_file_by_datetime(date, time)
        if not file_info:
            return create_error_response(404, f'No file found for {date} {time}')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Build query for requested indices
        requested_indices = [idx for idx in [red_index, green_index, blue_index] if idx]
        placeholders = ','.join(['?' for _ in requested_indices])
        
        cursor.execute(f"""
            SELECT index_name, chunk_index, start_time_sec, value
            FROM v_acoustic_indices
            WHERE file_id = ? AND index_name IN ({placeholders})
            ORDER BY chunk_index, index_name
        """, [file_info['id']] + requested_indices)
        
        rows = cursor.fetchall()
        conn.close()
        
        # Group by chunk_index and organize RGB data
        chunks_data = {}
        indices_ranges = {}
        
        # First pass: collect all data and calculate ranges for normalization
        for row in rows:
            chunk_idx = row['chunk_index']
            index_name = row['index_name']
            value = row['value']
            
            if chunk_idx not in chunks_data:
                chunks_data[chunk_idx] = {
                    'start_time_sec': row['start_time_sec'],
                    'values': {}
                }
            
            chunks_data[chunk_idx]['values'][index_name] = value
            
            # Track min/max for normalization
            if index_name not in indices_ranges:
                indices_ranges[index_name] = {'min': value, 'max': value}
            else:
                indices_ranges[index_name]['min'] = min(indices_ranges[index_name]['min'], value)
                indices_ranges[index_name]['max'] = max(indices_ranges[index_name]['max'], value)
        
        # Second pass: normalize to 0-255 and create RGB array
        rgb_data = []
        for chunk_idx in sorted(chunks_data.keys()):
            chunk = chunks_data[chunk_idx]
            
            # Normalize each channel to 0-255
            r = g = b = 0
            
            if red_index and red_index in chunk['values']:
                range_info = indices_ranges[red_index]
                if range_info['max'] > range_info['min']:
                    r = int(255 * (chunk['values'][red_index] - range_info['min']) / 
                           (range_info['max'] - range_info['min']))
                else:
                    r = 128  # Default to mid-range if no variation
            
            if green_index and green_index in chunk['values']:
                range_info = indices_ranges[green_index]
                if range_info['max'] > range_info['min']:
                    g = int(255 * (chunk['values'][green_index] - range_info['min']) / 
                           (range_info['max'] - range_info['min']))
                else:
                    g = 128
            
            if blue_index and blue_index in chunk['values']:
                range_info = indices_ranges[blue_index]
                if range_info['max'] > range_info['min']:
                    b = int(255 * (chunk['values'][blue_index] - range_info['min']) / 
                           (range_info['max'] - range_info['min']))
                else:
                    b = 128
            
            rgb_data.append({
                'chunk_index': chunk_idx,
                'start_time_sec': chunk['start_time_sec'],
                'rgb': [r, g, b],
                'raw_values': {
                    'red': chunk['values'].get(red_index) if red_index else None,
                    'green': chunk['values'].get(green_index) if green_index else None,
                    'blue': chunk['values'].get(blue_index) if blue_index else None
                }
            })
        
        return jsonify({
            'success': True,
            'data': {
                'file_info': file_info,
                'rgb_data': rgb_data,
                'channel_assignments': {
                    'red': red_index,
                    'green': green_index,
                    'blue': blue_index
                },
                'normalization_ranges': indices_ranges
            }
        })
        
    except Exception as e:
        return create_error_response(500, f"Failed to get RGB indices data: {str(e)}")