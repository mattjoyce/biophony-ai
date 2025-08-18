#!/usr/bin/env python3
"""
Audio API endpoints for AudioMoth Spectrogram Viewer
Handles audio file serving with range support
"""

import os
from flask import Blueprint, send_file, jsonify

from services.file_service import FileService


audio_bp = Blueprint('audio', __name__)


def create_error_response(status_code: int, message: str) -> tuple:
    """Create standardized error response"""
    return jsonify({'success': False, 'error': message}), status_code


@audio_bp.route('/api/audio/<filename>')
def serve_audio(filename: str):
    """Serve audio files with range support for streaming"""
    try:
        # Get file information from database
        file_info = FileService.get_file_by_filename(filename)
        if not file_info:
            return create_error_response(404, 'Audio file not found in database')
        
        filepath = file_info['filepath']
        
        # Verify file exists on filesystem
        if not os.path.exists(filepath):
            return create_error_response(404, 'Audio file not accessible on filesystem')
        
        # Serve file with range support for audio streaming
        return send_file(
            filepath,
            mimetype='audio/wav',
            as_attachment=False,
            conditional=True,  # Enable range requests for seeking
            download_name=filename
        )
        
    except Exception as e:
        return create_error_response(500, f"Failed to serve audio file: {str(e)}")


@audio_bp.route('/api/audio/<date>/<time>')
def serve_audio_by_datetime(date: str, time: str):
    """Serve audio file by date and time"""
    try:
        # Get file information
        file_info = FileService.get_file_by_datetime(date, time)
        if not file_info:
            return create_error_response(404, f'No audio file found for {date} {time}')
        
        filepath = file_info['filepath']
        filename = file_info['filename']
        
        # Verify file exists
        if not os.path.exists(filepath):
            return create_error_response(404, 'Audio file not accessible on filesystem')
        
        # Serve file
        return send_file(
            filepath,
            mimetype='audio/wav',
            as_attachment=False,
            conditional=True,
            download_name=filename
        )
        
    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        return create_error_response(500, f"Failed to serve audio file: {str(e)}")