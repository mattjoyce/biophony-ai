#!/usr/bin/env python3
"""
Files API endpoints for AudioMoth Spectrogram Viewer
Handles file-related API requests
"""

from flask import Blueprint, jsonify, request
from typing import Dict, Any

from services.file_service import FileService


files_bp = Blueprint('files', __name__)


def create_error_response(status_code: int, message: str) -> tuple:
    """Create standardized error response"""
    return jsonify({'success': False, 'error': message}), status_code


def create_success_response(data: Any) -> Dict[str, Any]:
    """Create standardized success response"""
    return jsonify({'success': True, 'data': data})


@files_bp.route('/api/dates')
def get_available_dates():
    """Get all dates that have audio files"""
    try:
        dates = FileService.get_available_dates()
        return create_success_response(dates)
    except Exception as e:
        return create_error_response(500, f"Failed to get available dates: {str(e)}")


@files_bp.route('/api/files/<date>')
def get_files_for_date(date: str):
    """Get all files for a specific date"""
    try:
        files = FileService.get_files_for_date(date)
        return create_success_response(files)
    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        return create_error_response(500, f"Failed to get files for date: {str(e)}")


@files_bp.route('/api/file/<date>/<time>')
def get_file_info(date: str, time: str):
    """Get specific file information"""
    try:
        file_info = FileService.get_file_by_datetime(date, time)
        if not file_info:
            return create_error_response(404, f'No file found for {date} {time}')
        return create_success_response(file_info)
    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        return create_error_response(500, f"Failed to get file info: {str(e)}")


@files_bp.route('/api/weather/<date>/<time>')
def get_weather_data(date: str, time: str):
    """Get weather data for specific recording"""
    try:
        weather_data = FileService.get_weather_for_datetime(date, time)
        if not weather_data:
            return create_error_response(404, f'No weather data found for {date} {time}')
        return create_success_response(weather_data)
    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        return create_error_response(500, f"Failed to get weather data: {str(e)}")


@files_bp.route('/api/files')
def search_files():
    """Search for audio files with filters"""
    try:
        # Validate limit parameter
        limit_str = request.args.get('limit', '100')
        try:
            limit = int(limit_str)
            if limit < 1 or limit > 1000:
                return create_error_response(400, 'Limit must be between 1 and 1000')
        except ValueError:
            return create_error_response(400, 'Invalid limit parameter')
        
        # Get filter parameters
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        time_from = request.args.get('time_from')
        time_to = request.args.get('time_to')
        
        # Search files
        files = FileService.search_files(
            date_from=date_from,
            date_to=date_to,
            time_from=time_from,
            time_to=time_to,
            limit=limit
        )
        
        return create_success_response(files)
        
    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        return create_error_response(500, f"Failed to search files: {str(e)}")


@files_bp.route('/api/navigation')
def get_navigation_file():
    """Get next/previous file info based on current date and time"""
    try:
        date = request.args.get('date')
        time = request.args.get('time')
        direction = request.args.get('direction', 'next')
        
        if not date or not time:
            return create_error_response(400, 'Date and time parameters are required')
        
        if direction not in ['next', 'prev']:
            return create_error_response(400, "Direction must be 'next' or 'prev'")
        
        print(f"Navigation API: date={date}, time={time}, direction={direction}")
        file_info = FileService.get_navigation_file(date, time, direction)
        print(f"Navigation API: Got result: {file_info}")
        
        if not file_info:
            return create_error_response(404, f'No {direction} file found')
        
        return create_success_response(file_info)
        
    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        return create_error_response(500, f"Failed to get navigation file: {str(e)}")


@files_bp.route('/api/available_times')
def get_available_times():
    """Get available dates and times from the database"""
    try:
        # Get all available dates
        dates = FileService.get_available_dates()
        
        # Build response with times for each date
        data = {}
        for date_str in dates:
            files = FileService.get_files_for_date(date_str)
            times = [file['time'] for file in files]
            data[date_str] = sorted(times)
        
        return jsonify(data)
        
    except Exception as e:
        return create_error_response(500, f"Failed to get available times: {str(e)}")