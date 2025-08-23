#!/usr/bin/env python3
"""
File service for AudioMoth Spectrogram Viewer
Handles all file-related business logic
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, date
from sqlalchemy import func, and_, or_

from database import get_db_session
from models.audio_file import AudioFile, WeatherData


class FileService:
    """Service for file operations and queries"""
    
    @staticmethod
    def get_available_dates() -> List[str]:
        """Return list of dates that have audio files (YYYY-MM-DD format)"""
        with get_db_session() as session:
            # Get distinct dates from audio files
            dates = session.query(
                func.date(AudioFile.recording_datetime).label('date')
            ).distinct().order_by('date').all()
            
            # Convert date objects to string format
            result = []
            for d in dates:
                if hasattr(d.date, 'isoformat'):
                    result.append(d.date.isoformat())
                else:
                    # Handle string dates from SQLite
                    result.append(str(d.date))
            
            return result
    
    @staticmethod
    def get_files_for_date(date_str: str) -> List[Dict[str, Any]]:
        """Return all files for a specific date with time and metadata"""
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            raise ValueError(f"Invalid date format: {date_str}. Expected YYYY-MM-DD")
        
        with get_db_session() as session:
            files = session.query(AudioFile).filter(
                func.date(AudioFile.recording_datetime) == target_date
            ).order_by(AudioFile.recording_datetime).all()
            
            return [file.to_dict() for file in files]
    
    @staticmethod
    def get_file_by_datetime(date_str: str, time_str: str) -> Optional[Dict[str, Any]]:
        """Get specific file by date and time"""
        # Use raw SQL like the original audio_database.py
        from database import execute_raw_query
        
        # Add seconds if not provided
        if len(time_str.split(':')) == 2:
            time_str = f"{time_str}:00"
        
        query = """
            SELECT * FROM audio_files 
            WHERE DATE(recording_datetime) = ? 
            AND TIME(recording_datetime) = ?
            LIMIT 1
        """
        
        results = execute_raw_query(query, (date_str, time_str))
        
        if results:
            row = results[0]
            return {
                'id': row[0],  # id
                'filename': row[1],  # filename
                'filepath': row[2],  # filepath
                'recording_datetime': row[4],  # recording_datetime
                'date': date_str,
                'time': time_str[:5],  # Remove seconds for frontend
                'duration_seconds': row[8],  # duration_seconds
                'audiomoth_id': row[6],  # audiomoth_id
                'weather_id': row[27] if len(row) > 27 else None  # weather_id
            }
        
        return None
    
    @staticmethod
    def get_weather_for_datetime(date_str: str, time_str: str) -> Optional[Dict[str, Any]]:
        """Get weather data for specific recording time"""
        try:
            # Parse date and time - add seconds if not provided
            if len(time_str.split(':')) == 2:
                time_str = f"{time_str}:00"
            target_datetime = datetime.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M:%S')
        except ValueError:
            raise ValueError(f"Invalid date/time format: {date_str} {time_str}")
        
        with get_db_session() as session:
            # First try to get weather data from audio file's weather_id
            audio_file = session.query(AudioFile).filter(
                AudioFile.recording_datetime == target_datetime
            ).first()
            
            if audio_file and audio_file.weather_id:
                weather = session.query(WeatherData).filter(
                    WeatherData.id == audio_file.weather_id
                ).first()
                if weather:
                    return weather.to_dict()
            
            # Fallback: find closest weather data by datetime
            weather = session.query(WeatherData).filter(
                WeatherData.datetime <= target_datetime
            ).order_by(
                func.abs(func.julianday(WeatherData.datetime) - func.julianday(target_datetime))
            ).first()
            
            return weather.to_dict() if weather else None
    
    @staticmethod
    def get_file_by_filename(filename: str) -> Optional[Dict[str, Any]]:
        """Get file information by filename for audio serving"""
        with get_db_session() as session:
            file = session.query(AudioFile).filter(
                AudioFile.filename == filename
            ).first()
            
            return file.to_dict() if file else None
    
    @staticmethod
    def get_file_by_id(file_id: int) -> Optional[Dict[str, Any]]:
        """Get file information by file_id"""
        with get_db_session() as session:
            file = session.query(AudioFile).filter(
                AudioFile.id == file_id
            ).first()
            
            return file.to_dict() if file else None
    
    @staticmethod
    def search_files(
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        time_from: Optional[str] = None,
        time_to: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Search files with date and time filters"""
        with get_db_session() as session:
            query = session.query(AudioFile)
            
            # Apply date filters
            if date_from:
                try:
                    from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
                    query = query.filter(func.date(AudioFile.recording_datetime) >= from_date)
                except ValueError:
                    raise ValueError(f"Invalid date_from format: {date_from}")
            
            if date_to:
                try:
                    to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
                    query = query.filter(func.date(AudioFile.recording_datetime) <= to_date)
                except ValueError:
                    raise ValueError(f"Invalid date_to format: {date_to}")
            
            # Apply time filters
            if time_from:
                try:
                    from_time = datetime.strptime(time_from, '%H:%M').time()
                    query = query.filter(func.time(AudioFile.recording_datetime) >= from_time)
                except ValueError:
                    raise ValueError(f"Invalid time_from format: {time_from}")
            
            if time_to:
                try:
                    to_time = datetime.strptime(time_to, '%H:%M').time()
                    query = query.filter(func.time(AudioFile.recording_datetime) <= to_time)
                except ValueError:
                    raise ValueError(f"Invalid time_to format: {time_to}")
            
            # Apply limit and order
            files = query.order_by(AudioFile.recording_datetime).limit(limit).all()
            
            return [file.to_dict() for file in files]
    
    @staticmethod
    def get_navigation_file(date_str: str, time_str: str, direction: str) -> Optional[Dict[str, Any]]:
        """Get next/previous file info based on current date and time"""
        try:
            # Parse date and time - add seconds if not provided
            if len(time_str.split(':')) == 2:
                time_str = f"{time_str}:00"
            current_datetime = datetime.strptime(f"{date_str}T{time_str}", '%Y-%m-%dT%H:%M:%S')
        except ValueError:
            raise ValueError(f"Invalid date/time format: {date_str} {time_str}")
        
        if direction not in ['next', 'prev']:
            raise ValueError("Direction must be 'next' or 'prev'")
        
        with get_db_session() as session:
            # Debug: print current datetime being used
            print(f"Navigation: Looking for {direction} file after/before {current_datetime}")
            
            if direction == 'next':
                # Convert datetime to ISO string for proper comparison with database
                current_datetime_str = current_datetime.strftime('%Y-%m-%dT%H:%M:%S')
                query = session.query(AudioFile).filter(
                    AudioFile.recording_datetime > current_datetime_str
                ).order_by(AudioFile.recording_datetime.asc())
                print(f"Navigation: SQL Query: {query}")
                print(f"Navigation: Searching for datetime > {current_datetime_str}")
                file = query.first()
            else:  # prev
                current_datetime_str = current_datetime.strftime('%Y-%m-%dT%H:%M:%S')
                file = session.query(AudioFile).filter(
                    AudioFile.recording_datetime < current_datetime_str
                ).order_by(AudioFile.recording_datetime.desc()).first()
            
            if file:
                print(f"Navigation: Found {direction} file: {file.recording_datetime}")
                result = file.to_dict()
                return result
            else:
                print(f"Navigation: No {direction} file found")
                return None
    
    @staticmethod
    def get_pois_for_file(date_str: str, time_str: str) -> List[Dict[str, Any]]:
        """Get POI spans for a specific file"""
        from database import execute_raw_query
        
        # Add seconds if not provided
        if len(time_str.split(':')) == 2:
            time_str = f"{time_str}:00"
        
        query = """
            SELECT 
                p.id, p.label, p.notes, p.confidence, p.anchor_index_name, p.created_at,
                ps.id as span_id, ps.start_time_sec, ps.end_time_sec, ps.chunk_start, ps.chunk_end,
                ps.config_name, ps.processing_type
            FROM points_of_interest p
            JOIN poi_spans ps ON p.id = ps.poi_id
            JOIN audio_files af ON ps.file_id = af.id
            WHERE DATE(af.recording_datetime) = ? 
            AND TIME(af.recording_datetime) = ?
            ORDER BY ps.start_time_sec, p.id
        """
        
        results = execute_raw_query(query, (date_str, time_str))
        
        pois = []
        for row in results:
            poi = {
                'id': row[0],  # p.id
                'label': row[1],  # p.label
                'notes': row[2] if row[2] else '',  # p.notes
                'confidence': row[3] if row[3] else 0.0,  # p.confidence
                'anchor_index_name': row[4] if row[4] else '',  # p.anchor_index_name
                'created_at': row[5],  # p.created_at
                'span_id': row[6],  # ps.id
                'start_time_sec': row[7],  # ps.start_time_sec
                'end_time_sec': row[8],  # ps.end_time_sec
                'chunk_start': row[9],  # ps.chunk_start
                'chunk_end': row[10],  # ps.chunk_end
                'config_name': row[11] if row[11] else '',  # ps.config_name
                'processing_type': row[12] if row[12] else ''  # ps.processing_type
            }
            pois.append(poi)
        
        return pois